"""
Gestion de la mémoire de conversation.
- Court terme : historique en mémoire, par session (dictionnaire simple).
- Peut être étendu plus tard avec ChromaDB pour de la mémoire long terme.
"""
import logging

logger = logging.getLogger(__name__)

# Stockage en mémoire : { session_id: [messages] }
# Pour un vrai déploiement, remplacer par Redis ou une base de données.
_sessions = {}

MAX_HISTORY_MESSAGES = 20  # limite pour éviter de saturer le contexte du LLM


def get_history(session_id: str) -> list:
    return _sessions.get(session_id, [])


def append_message(session_id: str, role: str, content: str):
    if session_id not in _sessions:
        _sessions[session_id] = []

    _sessions[session_id].append({"role": role, "content": content})

    # Tronque l'historique si trop long
    if len(_sessions[session_id]) > MAX_HISTORY_MESSAGES:
        _sessions[session_id] = _sessions[session_id][-MAX_HISTORY_MESSAGES:]


def clear_session(session_id: str):
    if session_id in _sessions:
        del _sessions[session_id]
        logger.info(f"Session {session_id} effacée")