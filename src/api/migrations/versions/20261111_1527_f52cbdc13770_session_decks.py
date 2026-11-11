"""session decks

Revision ID: f52cbdc13770
Revises: a9b3822bfe8b
Create Date: 2026-11-11 15:27:48+00:00

Decklist importée dans une conversation (une au plus par session). Son contenu
est injecté dans le prompt système à chaque tour, sans tool calling.

cards : [{"card_id": int, "qty": int, "section": "main" | "extra" | "side"}].
Pas de clé étrangère vers cards : sync-cards peut supprimer une carte retirée
de YGOPRODeck, elle est alors simplement ignorée à la lecture.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f52cbdc13770"
down_revision: Union[str, Sequence[str], None] = "a9b3822bfe8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE session_decks (
            session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            cards JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS session_decks")
