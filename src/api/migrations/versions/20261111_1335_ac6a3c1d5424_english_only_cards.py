"""english only cards

Revision ID: ac6a3c1d5424
Revises: f1da39dda438
Create Date: 2026-11-11 13:35:21+00:00

Jaden ne gère que l'anglais : les noms, les textes et la recherche plein
texte en français sont retirés de la base de cartes, et les colonnes anglaises
perdent leur suffixe _en (desc_en devient description : desc est réservé en SQL).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "ac6a3c1d5424"
down_revision: Union[str, Sequence[str], None] = "f1da39dda438"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Les index sur ces colonnes disparaissent avec elles.
    op.execute("ALTER TABLE cards DROP COLUMN search_fr, DROP COLUMN name_key_fr, DROP COLUMN name_fr, DROP COLUMN desc_fr")
    # La colonne générée search_en suit le renommage des colonnes qu'elle utilise.
    op.execute("ALTER TABLE cards RENAME COLUMN name_en TO name")
    op.execute("ALTER TABLE cards RENAME COLUMN desc_en TO description")
    op.execute("ALTER TABLE cards RENAME COLUMN name_key_en TO name_key")
    op.execute("ALTER TABLE cards RENAME COLUMN search_en TO search")
    op.execute("ALTER INDEX cards_name_key_en_trgm_idx RENAME TO cards_name_key_trgm_idx")
    op.execute("ALTER INDEX cards_search_en_idx RENAME TO cards_search_idx")


def downgrade() -> None:
    op.execute("ALTER INDEX cards_search_idx RENAME TO cards_search_en_idx")
    op.execute("ALTER INDEX cards_name_key_trgm_idx RENAME TO cards_name_key_en_trgm_idx")
    op.execute("ALTER TABLE cards RENAME COLUMN search TO search_en")
    op.execute("ALTER TABLE cards RENAME COLUMN name_key TO name_key_en")
    op.execute("ALTER TABLE cards RENAME COLUMN description TO desc_en")
    op.execute("ALTER TABLE cards RENAME COLUMN name TO name_en")
    # Les colonnes reviennent vides : relancer python main.py sync-cards --force
    # avec une version de sync.py qui télécharge le français.
    op.execute("ALTER TABLE cards ADD COLUMN name_fr TEXT, ADD COLUMN desc_fr TEXT, ADD COLUMN name_key_fr TEXT")
    op.execute("""
        ALTER TABLE cards ADD COLUMN search_fr tsvector GENERATED ALWAYS AS (
            setweight(to_tsvector('french', coalesce(name_fr, '')), 'A')
            || setweight(to_tsvector('french', coalesce(desc_fr, '')), 'B')
        ) STORED
    """)
    op.execute("CREATE INDEX cards_name_key_fr_trgm_idx ON cards USING gin (name_key_fr gin_trgm_ops)")
    op.execute("CREATE INDEX cards_search_fr_idx ON cards USING gin (search_fr)")
