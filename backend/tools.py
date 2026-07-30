"""
Définition des outils (tools) que l'agent peut appeler.
Chaque outil a : sa définition JSON (pour le LLM) + sa fonction d'exécution réelle.
"""
import logging
from tavily import TavilyClient
from config import Config

logger = logging.getLogger(__name__)

tavily_client = TavilyClient(api_key=Config.TAVILY_API_KEY)


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
    """
    try:
        logger.info(f"[TOOL] search_web appelé avec query='{query}'")
        results = tavily_client.search(
            query=query,
            max_results=Config.MAX_SEARCH_RESULTS,
            include_answer=True,
            search_depth="advanced"
        )

        formatted = {
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
        return formatted

    except Exception as e:
        logger.error(f"Erreur lors de la recherche web: {e}")
        return {"error": str(e), "query": query, "sources": []}


# --- Registre pour dispatcher dynamiquement les appels d'outils ---

AVAILABLE_TOOLS = {
    "search_web": search_web
}