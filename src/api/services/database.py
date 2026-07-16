import sqlite3
from pathlib import Path
from typing import List, Dict

SERVER_DIR = Path(__file__).parent.parent
DATA_DIR = SERVER_DIR / "data"
DB_PATH = DATA_DIR / "maia.db"

def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT DEFAULT 'Nouvelle discussion',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)
        conn.commit()

def create_session_if_not_exists(session_id: str):
    """Crée une session si elle n'existe pas encore dans la base."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO sessions (id) VALUES (?)",
            (session_id,)
        )
        conn.commit()

def save_message(session_id: str, role: str, content: str):
    """Enregistre un message (user ou assistant) lié à une session."""
    create_session_if_not_exists(session_id)
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        conn.commit()

def get_chat_history(session_id: str) -> List[Dict[str, str]]:
    """Récupère l'historique complet d'une session sous forme utilisable par le LLM."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,)
        )
        rows = cursor.fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]