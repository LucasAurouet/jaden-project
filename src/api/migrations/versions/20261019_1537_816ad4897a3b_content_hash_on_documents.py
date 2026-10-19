"""content hash on documents

Revision ID: 816ad4897a3b
Revises: 49d588e4c8b6
Create Date: 2026-10-19 15:37:42.629362+00:00

Empreinte SHA-256 du fichier envoyé, pour refuser un fichier déjà indexé.
Les documents existants n'en ont pas (le fichier d'origine n'est pas conservé) :
la colonne reste vide pour eux, et l'index unique accepte plusieurs NULL.
"""
from typing import Sequence, Union

from alembic import op

revision: str = '816ad4897a3b'
down_revision: Union[str, Sequence[str], None] = '49d588e4c8b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE documents ADD COLUMN sha256 TEXT")
    op.execute("CREATE UNIQUE INDEX documents_sha256_idx ON documents (sha256)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS documents_sha256_idx")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS sha256")
