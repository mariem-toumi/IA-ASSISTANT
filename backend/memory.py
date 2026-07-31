"""
Gestion de la mémoire de conversation, avec persistance SQLite.
- Historique complet stocké sur disque (survit aux redémarrages du serveur).
- Fournit le contexte court terme pour l'agent (get_history).
- Fournit la liste des conversations + une recherche par mot-clé pour le frontend.
"""
import sqlite3
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DB_DIR = Path(__file__).parent / "data"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "history.db"

MAX_HISTORY_MESSAGES = 20   # nb de messages renvoyés à l'agent pour le contexte court terme
TITLE_MAX_LENGTH = 60

_lock = threading.Lock()


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    with _lock, _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                session_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES conversations(session_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_content ON messages(content)")
    logger.info(f"Base de données initialisée: {DB_PATH}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_title(first_user_message: str) -> str:
    text = first_user_message.strip().replace("\n", " ")
    if len(text) <= TITLE_MAX_LENGTH:
        return text
    return text[:TITLE_MAX_LENGTH].rstrip() + "…"


def get_history(session_id: str) -> list:
    """Retourne les derniers messages d'une session, au format attendu par Groq."""
    with _lock, _get_connection() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        ).fetchall()

    messages = [{"role": r["role"], "content": r["content"]} for r in rows]
    return messages[-MAX_HISTORY_MESSAGES:]


def append_message(session_id: str, role: str, content: str) -> None:
    if not content:
        return

    with _lock, _get_connection() as conn:
        existing = conn.execute(
            "SELECT session_id FROM conversations WHERE session_id = ?", (session_id,)
        ).fetchone()

        now = _now()

        if existing is None:
            title = _make_title(content) if role == "user" else "Nouvelle conversation"
            conn.execute(
                "INSERT INTO conversations (session_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, title, now, now)
            )
        else:
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE session_id = ?",
                (now, session_id)
            )

        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, now)
        )


def clear_session(session_id: str) -> None:
    """Supprime définitivement une conversation et ses messages."""
    with _lock, _get_connection() as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
    logger.info(f"Conversation {session_id} supprimée")


def list_conversations(limit: int = 50) -> list:
    """Liste des conversations, les plus récentes en premier."""
    with _lock, _get_connection() as conn:
        rows = conn.execute("""
            SELECT c.session_id, c.title, c.created_at, c.updated_at,
                   COUNT(m.id) as message_count
            FROM conversations c
            LEFT JOIN messages m ON m.session_id = c.session_id
            GROUP BY c.session_id
            ORDER BY c.updated_at DESC
            LIMIT ?
        """, (limit,)).fetchall()

    return [dict(r) for r in rows]


def get_conversation_messages(session_id: str) -> list:
    """Tous les messages d'une conversation, dans l'ordre chronologique."""
    with _lock, _get_connection() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def search_conversations(query: str, limit: int = 30) -> list:
    """
    Recherche par mot-clé dans les titres ET le contenu des messages.
    Retourne les conversations correspondantes avec un court extrait.
    """
    query = query.strip()
    if not query:
        return []

    like_pattern = f"%{query}%"

    with _lock, _get_connection() as conn:
        rows = conn.execute("""
            SELECT DISTINCT c.session_id, c.title, c.updated_at,
                (
                    SELECT m2.content FROM messages m2
                    WHERE m2.session_id = c.session_id AND m2.content LIKE ?
                    ORDER BY m2.id ASC LIMIT 1
                ) as snippet
            FROM conversations c
            LEFT JOIN messages m ON m.session_id = c.session_id
            WHERE c.title LIKE ? OR m.content LIKE ?
            ORDER BY c.updated_at DESC
            LIMIT ?
        """, (like_pattern, like_pattern, like_pattern, limit)).fetchall()

    results = []
    for r in rows:
        snippet = r["snippet"] or ""
        if len(snippet) > 120:
            snippet = snippet[:120].rstrip() + "…"
        results.append({
            "session_id": r["session_id"],
            "title": r["title"],
            "updated_at": r["updated_at"],
            "snippet": snippet
        })
    return results


# Initialise la base au chargement du module
init_db()
