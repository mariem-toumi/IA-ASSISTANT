"""
Cœur de l'agent : boucle de tool calling avec Groq.
Gère l'appel au LLM, l'exécution des outils demandés,
et la synthèse de la réponse finale avec vérification.
"""
import json
import logging
from groq import Groq

from config import Config
from tools import TOOLS_DEFINITION, AVAILABLE_TOOLS
from verification import VERIFICATION_SYSTEM_PROMPT, build_verification_context, check_source_agreement

logger = logging.getLogger(__name__)

client = Groq(api_key=Config.GROQ_API_KEY)


def _call_groq_with_retry(messages, tools=None, tool_choice=None, max_attempts=2):
    """
    Appelle Groq avec retry automatique en cas d'échec de génération
    (bug connu: le modèle peut mal formater un tool_call, notamment
    quand la requête contient des caractères spéciaux comme des apostrophes).
    Au 2e essai, la température est abaissée pour stabiliser la sortie.
    """
    last_error = None

    for attempt in range(max_attempts):
        try:
            kwargs = {
                "model": Config.AGENT_MODEL,
                "messages": messages,
                "temperature": 0.1 if attempt > 0 else 0.3,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = tool_choice or "auto"

            response = client.chat.completions.create(**kwargs)
            return response, None

        except Exception as e:
            last_error = e
            logger.warning(f"Tentative {attempt + 1}/{max_attempts} échouée: {e}")

    return None, last_error


def run_agent(user_message: str, history: list) -> dict:
    """
    Exécute la boucle agentique complète :
    1. Envoie la question + historique au LLM avec les outils disponibles
    2. Si le LLM demande un outil -> l'exécute -> renvoie le résultat au LLM
    3. Répète jusqu'à obtenir une réponse finale (ou limite d'itérations atteinte)

    Retourne un dict avec la réponse finale ET les métadonnées (sources, confiance).
    """
    messages = (
        [{"role": "system", "content": VERIFICATION_SYSTEM_PROMPT}]
        + history
        + [{"role": "user", "content": user_message}]
    )

    sources_used = []
    tool_was_used = False

    for iteration in range(Config.MAX_TOOL_ITERATIONS):
        response, error = _call_groq_with_retry(
            messages, tools=TOOLS_DEFINITION, tool_choice="auto"
        )

        if error is not None:
            logger.error(f"Erreur API Groq après retry: {error}")
            return {
                "response": "Désolé, une erreur technique est survenue. Peux-tu reformuler ta question ?",
                "sources": sources_used,
                "confidence": "unknown",
                "error": str(error),
                "tool_used": tool_was_used
            }

        msg = response.choices[0].message

        # Cas 1 : le modèle ne demande pas d'outil -> réponse finale
        if not msg.tool_calls:
            return {
                "response": msg.content,
                "sources": sources_used,
                "confidence": _estimate_confidence(sources_used),
                "tool_used": tool_was_used
            }

        # Cas 2 : le modèle demande d'exécuter un ou plusieurs outils
        tool_was_used = True
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                }
                for tc in msg.tool_calls
            ]
        })

        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name
            try:
                tool_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            tool_function = AVAILABLE_TOOLS.get(tool_name)

            if tool_function is None:
                tool_result = {"error": f"Outil inconnu: {tool_name}"}
            else:
                tool_result = tool_function(**tool_args)

                # Collecte les sources pour les métadonnées de réponse
                if tool_name == "search_web" and "sources" in tool_result:
                    sources_used.extend(tool_result["sources"])

            verification_context = build_verification_context(tool_result)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": verification_context
            })

    # Limite d'itérations atteinte sans réponse finale claire
    logger.warning("Limite d'itérations d'outils atteinte")
    return {
        "response": "Je n'ai pas pu obtenir une réponse fiable après plusieurs recherches. Peux-tu reformuler ta question ?",
        "sources": sources_used,
        "confidence": "low",
        "tool_used": tool_was_used
    }


def _estimate_confidence(sources: list) -> str:
    """Estimation simple de la confiance basée sur le nombre de sources croisées."""
    if len(sources) == 0:
        return "n/a"
    elif len(sources) == 1:
        return "moyenne"
    else:
        return "haute"


def run_agent_stream(user_message: str, history: list):
    """
    Version streaming de l'agent, sous forme de générateur.
    Yield des événements structurés :
    - {"type": "status", "data": "..."}       -> statut en cours (recherche, etc.)
    - {"type": "sources", "data": [...]}      -> sources trouvées, une fois dispo
    - {"type": "token", "data": "..."}        -> fragment de texte de la réponse finale
    - {"type": "done", "data": {...}}         -> fin, avec métadonnées complètes
    - {"type": "error", "data": "..."}        -> erreur
    """
    messages = (
        [{"role": "system", "content": VERIFICATION_SYSTEM_PROMPT}]
        + history
        + [{"role": "user", "content": user_message}]
    )

    sources_used = []
    tool_was_used = False

    # --- Phase 1 : décider si un outil est nécessaire ---
    for iteration in range(Config.MAX_TOOL_ITERATIONS):
        response, error = _call_groq_with_retry(
            messages, tools=TOOLS_DEFINITION, tool_choice="auto"
        )

        if error is not None:
            logger.error(f"Erreur API Groq après retry: {error}")
            yield {
                "type": "error",
                "data": "Le modèle a rencontré une difficulté technique. Réessaie ta question, éventuellement reformulée."
            }
            return

        msg = response.choices[0].message

        # Pas d'appel d'outil -> on peut streamer directement cette réponse
        if not msg.tool_calls:
            break

        # Un outil est demandé
        tool_was_used = True
        yield {"type": "status", "data": "Recherche d'informations en cours..."}

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                }
                for tc in msg.tool_calls
            ]
        })

        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name
            try:
                tool_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            tool_function = AVAILABLE_TOOLS.get(tool_name)

            try:
                tool_result = (
                    tool_function(**tool_args) if tool_function
                    else {"error": f"Outil inconnu: {tool_name}"}
                )
            except Exception as e:
                logger.error(f"Erreur lors de l'exécution de l'outil {tool_name}: {e}")
                tool_result = {"error": f"Erreur technique lors de l'exécution de {tool_name}: {str(e)}"}

            if tool_name == "search_web" and "sources" in tool_result:
                sources_used.extend(tool_result["sources"])
                yield {"type": "sources", "data": tool_result["sources"]}

            verification_context = build_verification_context(tool_result)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": verification_context
            })

        # On repart en boucle pour voir si le modèle veut une réponse finale ou un autre outil
        continue

    # --- Phase 2 : streamer la réponse finale token par token ---
    yield {"type": "status", "data": "Génération de la réponse..."}

    try:
        stream = client.chat.completions.create(
            model=Config.SYNTHESIS_MODEL,
            messages=messages,
            temperature=0.3,
            stream=True,
        )

        full_response = ""
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                full_response += delta
                yield {"type": "token", "data": delta}

        yield {
            "type": "done",
            "data": {
                "response": full_response,
                "sources": sources_used,
                "confidence": _estimate_confidence(sources_used),
                "tool_used": tool_was_used
            }
        }

    except Exception as e:
        logger.error(f"Erreur streaming Groq: {e}")
        yield {"type": "error", "data": "Erreur lors de la génération de la réponse finale."}