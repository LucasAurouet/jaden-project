"""card embeddings

Revision ID: f1da39dda438
Revises: 758ab11eda6f
Create Date: 2026-11-11 13:24:58+00:00

Vecteur de chaque carte (nom, ligne de type et effet en anglais), pour la
recherche hybride de cards/repository.py. embedding_hash est l'empreinte du
texte vectorisé : sync-cards ne revectorise que les cartes dont le texte a changé.

Pas d'index HNSW : avec ~15 000 cartes, le parcours exact reste rapide, et il
renvoie toujours le bon nombre de résultats quand des filtres s'appliquent.
"""
from typing import Sequence, Union

from alembic import op
from config import EMBEDDING_DIM

revision: str = "f1da39dda438"
down_revision: Union[str, Sequence[str], None] = "758ab11eda6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(f"ALTER TABLE cards ADD COLUMN embedding vector({EMBEDDING_DIM})")
    op.execute("ALTER TABLE cards ADD COLUMN embedding_hash TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE cards DROP COLUMN IF EXISTS embedding_hash")
    op.execute("ALTER TABLE cards DROP COLUMN IF EXISTS embedding")
