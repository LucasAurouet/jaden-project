"""cards

Revision ID: 758ab11eda6f
Revises: 314a7f32d679
Create Date: 2026-11-11 13:16:31+00:00

Base de cartes Yu-Gi-Oh!, copie locale de l'API YGOPRODeck remplie par
python main.py sync-cards : une ligne par carte (textes anglais et français),
ses artworks (ids alternatifs utilisés par les fichiers .ydk) et l'état de la
dernière synchronisation.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "758ab11eda6f"
down_revision: Union[str, Sequence[str], None] = "314a7f32d679"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Les codes (type, race, attribute...) restent ceux de l'API, en anglais.
    # atk / def valent -1 pour « ? ». name_key_en / name_key_fr : noms en
    # minuscules, sans accents ni ponctuation (cards/text.py), pour la recherche floue.
    op.execute("""
        CREATE TABLE cards (
            id BIGINT PRIMARY KEY,
            konami_id INT,
            name_en TEXT NOT NULL,
            name_fr TEXT,
            name_key_en TEXT NOT NULL,
            name_key_fr TEXT,
            desc_en TEXT NOT NULL,
            desc_fr TEXT,
            type TEXT NOT NULL,
            frame_type TEXT NOT NULL,
            typeline TEXT[] NOT NULL DEFAULT '{}',
            race TEXT,
            attribute TEXT,
            archetype TEXT,
            level INT,
            atk INT,
            def INT,
            scale INT,
            link_rating INT,
            link_markers TEXT[],
            formats TEXT[] NOT NULL DEFAULT '{}',
            md_rarity TEXT,
            raw JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            search_en tsvector GENERATED ALWAYS AS (
                setweight(to_tsvector('english', name_en), 'A') || setweight(to_tsvector('english', desc_en), 'B')
            ) STORED,
            search_fr tsvector GENERATED ALWAYS AS (
                setweight(to_tsvector('french', coalesce(name_fr, '')), 'A')
                || setweight(to_tsvector('french', coalesce(desc_fr, '')), 'B')
            ) STORED
        )
    """)
    op.execute("CREATE INDEX cards_name_key_en_trgm_idx ON cards USING gin (name_key_en gin_trgm_ops)")
    op.execute("CREATE INDEX cards_name_key_fr_trgm_idx ON cards USING gin (name_key_fr gin_trgm_ops)")
    op.execute("CREATE INDEX cards_search_en_idx ON cards USING gin (search_en)")
    op.execute("CREATE INDEX cards_search_fr_idx ON cards USING gin (search_fr)")
    op.execute("CREATE INDEX cards_formats_idx ON cards USING gin (formats)")
    op.execute("CREATE INDEX cards_archetype_idx ON cards (lower(archetype))")

    # Un id par artwork : l'id principal de la carte en fait partie.
    op.execute("""
        CREATE TABLE card_artworks (
            id BIGINT PRIMARY KEY,
            card_id BIGINT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
            position INT NOT NULL
        )
    """)
    op.execute("CREATE INDEX card_artworks_card_id_idx ON card_artworks (card_id)")

    op.execute("""
        CREATE TABLE sync_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    # L'extension pg_trgm est laissée en place.
    op.execute("DROP TABLE IF EXISTS card_artworks, cards, sync_state")
