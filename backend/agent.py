"""
Cœur de l'agent : boucle de tool calling avec Groq.
Gère l'appel au LLM, l'exécution des outils demandés,
la synthèse de la réponse finale avec vérification,
et un filet de sécurité si le modèle échoue à générer un tool call proprement.
"""
import json
import logging
from groq import Groq

from config import Config
from tools import TOOLS_DEFINITION, AVAILABLE_TOOLS, search_web
from verification import VERIFICATION_SYSTEM_PROMPT, build_verification_context, check_source_agreement

logger = logging.getLogger(__name__)

client = Groq(api_key=Config.GROQ_API_KEY)


def _call_groq_with_retry(messages, tools=None, tool_choice=None, max_attempts=2):
    """
    Appelle Groq avec retry automatique en cas d'échec de génération
    (bug connu: le modèle peut mal formater un tool_call, notamment
    quand la requête contient des caractères spéciaux comme des apostrophes
    ou des accents). Au 2e essai, la température est abaissée pour stabiliser.
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


def _fallback_direct_search(user_message: str) -> dict:
    """
    Filet de sécurité : si le modèle échoue à générer un tool_call proprement
    (erreur tool_use_failed persistante), on exécute nous-mêmes une recherche
    web sur la question brute, sans passer par la décision du modèle.
    """
    logger.info("Fallback: recherche web directe (contournement du tool calling)")
    return search_web(user_message)


def _synthesize_from_context(user_message: str, history: list, search_result: dict, stream: bool = False):
    """
    Demande au modèle de rédiger la réponse finale à partir d'un contexte
    de recherche déjà obtenu, SANS lui redonner la possibilité d'appeler un outil.
    Cela évite de retomber dans le même bug de génération de tool_call.
    """
    verification_context = build_verification_context(search_result)

    messages = (
        [{"role": "system", "content": VERIFICATION_SYSTEM_PROMPT}]
        + history
        + [
            {"role": "user", "content": user_message},
            {
                "role": "system",
                "content": (
                    "Voici des résultats de recherche web récents pour répondre à la question "
                    f"ci-dessus:\n\n{verification_context}\n\n"
                    "Rédige ta réponse UNIQUEMENT à partir de ces résultats, en citant tes sources."
                )
            }
        ]
    )

    if not stream:
        response = client.chat.completions.create(
            model=Config.SYNTHESIS_MODEL,
            messages=messages,
            temperature=0.3
        )
        return response.choices[0].message.content

    return client.chat.completions.create(
        model=Config.SYNTHESIS_MODEL,
        messages=messages,
        temperature=0.3,
        stream=True
    )


def run_agent(user_message: str, history: list) -> dict:
    """
    Exécute la boucle agentique complète :
    1. Envoie la question + historique au LLM avec les outils disponibles
    2. Si le LLM demande un outil -> l'exécute -> renvoie le résultat au LLM
    3. Répète jusqu'à obtenir une réponse finale (ou limite d'itérations atteinte)
    4. Si le tool calling échoue de façon persistante, bascule sur une recherche directe

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
            # Filet de sécurité : recherche directe + synthèse sans tool calling
            logger.warning(f"Tool calling définitivement échoué, bascule en mode direct: {error}")
            search_result = _fallback_direct_search(user_message)
            sources_used = search_result.get("sources", [])
            answer = _synthesize_from_context(user_message, history, search_result, stream=False)
            return {
                "response": answer,
                "sources": sources_used,
                "confidence": _estimate_confidence(sources_used),
                "tool_used": True
            }

        msg = response.choices[0].message

        if not msg.tool_calls:
            return {
                "response": msg.content,
                "sources": sources_used,
                "confidence": _estimate_confidence(sources_used),
                "tool_used": tool_was_used
            }

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

            verification_context = build_verification_context(tool_result)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": verification_context
            })

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
    fallback_triggered = False

    # --- Phase 1 : décider si un outil est nécessaire ---
    for iteration in range(Config.MAX_TOOL_ITERATIONS):
        response, error = _call_groq_with_retry(
            messages, tools=TOOLS_DEFINITION, tool_choice="auto"
        )

        if error is not None:
            # Filet de sécurité : recherche directe, puis on streame la synthèse
            logger.warning(f"Tool calling définitivement échoué, bascule en mode direct: {error}")
            yield {"type": "status", "data": "Recherche directe en cours..."}

            search_result = _fallback_direct_search(user_message)
            sources_used = search_result.get("sources", [])
            if sources_used:
                yield {"type": "sources", "data": sources_used}

            tool_was_used = True
            fallback_triggered = True

            yield {"type": "status", "data": "Génération de la réponse..."}
            try:
                stream = _synthesize_from_context(user_message, history, search_result, stream=True)
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
                        "tool_used": True
                    }
                }
            except Exception as e:
                logger.error(f"Erreur lors de la synthèse de secours: {e}")
                yield {"type": "error", "data": "Impossible de générer une réponse pour le moment."}
            return

        msg = response.choices[0].message

        if not msg.tool_calls:
            break

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

        continue

    if fallback_triggered:
        return

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
