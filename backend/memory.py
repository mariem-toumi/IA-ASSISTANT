"""
Gestion de la mémoire de conversation, avec persistance SQLite.
- Historique complet stocké sur disque (survit aux redémarrages du serveur).
- Fournit le contexte court terme pour l'agent (get_history).
- Chaque conversation est rattachée à un visitor_id (identifiant anonyme
  généré côté navigateur) pour que chaque visiteur ne voie QUE son propre
  historique, jamais celui des autres.
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

MAX_HISTORY_MESSAGES = 20
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
                visitor_id TEXT,
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
        # Migration douce : ajoute visitor_id si la table existait déjà sans cette colonne
        existing_cols = [row["name"] for row in conn.execute("PRAGMA table_info(conversations)")]
        if "visitor_id" not in existing_cols:
            conn.execute("ALTER TABLE conversations ADD COLUMN visitor_id TEXT")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_content ON messages(content)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_visitor ON conversations(visitor_id)")
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


def append_message(session_id: str, role: str, content: str, visitor_id: str = None) -> None:
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
                "INSERT INTO conversations (session_id, visitor_id, title, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, visitor_id, title, now, now)
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


def clear_session(session_id: str, visitor_id: str = None) -> bool:
    """
    Supprime une conversation et ses messages.
    Si visitor_id est fourni, la suppression n'a lieu que si le visiteur
    est bien le propriétaire de la conversation (protection anti-suppression
    par un tiers qui devinerait un session_id).
    Retourne True si une suppression a bien eu lieu.
    """
    with _lock, _get_connection() as conn:
        if visitor_id is not None:
            owner = conn.execute(
                "SELECT visitor_id FROM conversations WHERE session_id = ?", (session_id,)
            ).fetchone()
            if owner is None or owner["visitor_id"] != visitor_id:
                return False

        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cursor = conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
        deleted = cursor.rowcount > 0

    if deleted:
        logger.info(f"Conversation {session_id} supprimée")
    return deleted


def list_conversations(visitor_id: str, limit: int = 50) -> list:
    """Liste les conversations d'UN visiteur précis, les plus récentes en premier."""
    if not visitor_id:
        return []

    with _lock, _get_connection() as conn:
        rows = conn.execute("""
            SELECT c.session_id, c.title, c.created_at, c.updated_at,
                   COUNT(m.id) as message_count
            FROM conversations c
            LEFT JOIN messages m ON m.session_id = c.session_id
            WHERE c.visitor_id = ?
            GROUP BY c.session_id
            ORDER BY c.updated_at DESC
            LIMIT ?
        """, (visitor_id, limit)).fetchall()

    return [dict(r) for r in rows]


def get_conversation_messages(session_id: str, visitor_id: str) -> list:
    """
    Tous les messages d'une conversation, dans l'ordre chronologique.
    Ne retourne rien si le visitor_id ne correspond pas au propriétaire
    (empêche un visiteur de lire l'historique d'un autre en devinant un ID).
    """
    if not visitor_id:
        return []

    with _lock, _get_connection() as conn:
        owner = conn.execute(
            "SELECT visitor_id FROM conversations WHERE session_id = ?", (session_id,)
        ).fetchone()
        if owner is None or owner["visitor_id"] != visitor_id:
            return []

        rows = conn.execute(
            "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def search_conversations(query: str, visitor_id: str, limit: int = 30) -> list:
    """Recherche par mot-clé, restreinte aux conversations du visiteur courant."""
    query = query.strip()
    if not query or not visitor_id:
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
            WHERE c.visitor_id = ? AND (c.title LIKE ? OR m.content LIKE ?)
            ORDER BY c.updated_at DESC
            LIMIT ?
        """, (like_pattern, visitor_id, like_pattern, like_pattern, limit)).fetchall()

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


init_db()
