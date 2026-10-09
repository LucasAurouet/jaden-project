import sqlite3
from pathlib import Path
from typing import List, Dict

# Base locale du poste client : src/client/data/homn.db
DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "homn.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    DATA_DIR.mkdir(exist_ok=True)

    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT DEFAULT 'Nouvelle discussion',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Uniquement les tours de conversation (user / assistant).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)


def save_exchange(session_id: str, prompt: str, answer: str):
    """Enregistre un tour complet (question + réponse) dans une seule transaction."""
    with _connect() as conn:
        conn.execute("INSERT OR IGNORE INTO sessions (id) VALUES (?)", (session_id,))
        conn.executemany(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            [(session_id, "user", prompt), (session_id, "assistant", answer)],
        )


def get_chat_history(session_id: str) -> List[Dict[str, str]]:
    """Récupère l'historique complet d'une session sous forme utilisable par le LLM."""
    with _connect() as conn:
        rows = conn.execute(
            # created_at n'a qu'une précision d'une seconde : on trie par id.
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]

