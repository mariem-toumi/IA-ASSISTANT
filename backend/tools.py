"""
Définition des outils (tools) que l'agent peut appeler.
Chaque outil a : sa définition JSON (pour le LLM) + sa fonction d'exécution réelle.
"""
import logging
import time
from tavily import TavilyClient
from config import Config

logger = logging.getLogger(__name__)

tavily_client = TavilyClient(api_key=Config.TAVILY_API_KEY)

SEARCH_MAX_ATTEMPTS = 3
SEARCH_RETRY_DELAY_SECONDS = 1.5


# --- Définitions des outils (format attendu par Groq/OpenAI function calling) ---

TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Recherche des informations récentes et à jour sur le web. "
                "Utilise cet outil pour toute question portant sur l'actualité, "
                "des faits récents, des données changeantes (prix, statistiques, "
                "événements) ou toute information que tu n'es pas certain de connaître."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "La requête de recherche, formulée clairement et de façon concise."
                    }
                },
                "required": ["query"]
            }
        }
    }
]


# --- Implémentation réelle des outils ---

def search_web(query: str) -> dict:
    """
    Exécute une recherche web via Tavily et retourne des résultats structurés.
    Réessaie automatiquement en cas d'incident réseau transitoire
    (coupure de connexion, timeout) avant d'abandonner proprement.
    """
    last_error = None

    for attempt in range(1, SEARCH_MAX_ATTEMPTS + 1):
        try:
            logger.info(f"[TOOL] search_web appelé avec query='{query}' (tentative {attempt}/{SEARCH_MAX_ATTEMPTS})")
            results = tavily_client.search(
                query=query,
                max_results=Config.MAX_SEARCH_RESULTS,
                include_answer=True,
                search_depth="advanced"
            )

            return {
                "query": query,
                "answer_summary": results.get("answer", ""),
                "sources": [
                    {
                        "title": r.get("title"),
                        "url": r.get("url"),
                        "content": r.get("content"),
                        "score": r.get("score")
                    }
                    for r in results.get("results", [])
                ]
            }

        except Exception as e:
            last_error = e
            logger.warning(f"search_web tentative {attempt}/{SEARCH_MAX_ATTEMPTS} échouée: {e}")
            if attempt < SEARCH_MAX_ATTEMPTS:
                time.sleep(SEARCH_RETRY_DELAY_SECONDS)

    # Toutes les tentatives ont échoué : on ne renvoie jamais l'exception brute,
    # seulement un message clair et exploitable par le modèle.
    logger.error(f"search_web définitivement échoué après {SEARCH_MAX_ATTEMPTS} tentatives: {last_error}")
    return {
        "error": "network_unavailable",
        "error_message": "La recherche web est temporairement indisponible (problème de connexion réseau).",
        "query": query,
        "sources": []
    }


# --- Registre pour dispatcher dynamiquement les appels d'outils ---

AVAILABLE_TOOLS = {
    "search_web": search_web
}
