"""users, auth tokens and ownership

Revision ID: 1b3603054a1b
Revises: 816ad4897a3b
Create Date: 2026-10-19 16:00:00.000000+00:00

Comptes utilisateurs et jetons de connexion, et rattachement des données à un
utilisateur. Les sessions existantes restent sans propriétaire jusqu'à la
création du premier admin (python main.py adduser --admin), qui les récupère.
Les documents existants deviennent partagés (owner_id NULL), ce qui garde
leur comportement actuel : visibles de tous.
"""
from typing import Sequence, Union

from alembic import op

revision: str = '1b3603054a1b'
down_revision: Union[str, Sequence[str], None] = '816ad4897a3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE users (
            id BIGSERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_admin BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # Seule l'empreinte SHA-256 du jeton est stockée : une fuite de la base ne
    # donne pas de jeton utilisable.
    op.execute("""
        CREATE TABLE auth_tokens (
            token_hash TEXT PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute("CREATE INDEX auth_tokens_user_id_idx ON auth_tokens (user_id)")

    op.execute("ALTER TABLE sessions ADD COLUMN user_id BIGINT REFERENCES users(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE sessions ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now()")
    op.execute("""
        UPDATE sessions s SET updated_at = m.last
        FROM (SELECT session_id, max(created_at) AS last FROM messages GROUP BY session_id) m
        WHERE m.session_id = s.id AND m.last IS NOT NULL
    """)
    op.execute("CREATE INDEX sessions_user_updated_idx ON sessions (user_id, updated_at DESC)")
    # Les sessions antérieures gardaient le titre par défaut : on prend leur
    # première question, comme save_exchange pour les nouvelles (60 caractères).
    op.execute("""
        UPDATE sessions s SET title = CASE WHEN length(m.q) > 60 THEN rtrim(left(m.q, 59)) || '…' ELSE m.q END
        FROM (
            SELECT DISTINCT ON (session_id) session_id,
                   regexp_replace(trim(content), '[[:space:]]+', ' ', 'g') AS q
            FROM messages WHERE role = 'user' ORDER BY session_id, id
        ) m
        WHERE m.session_id = s.id AND (s.title IS NULL OR s.title = 'Nouvelle discussion')
    """)

    # owner_id NULL : document partagé, visible de tous et géré par l'admin.
    op.execute("ALTER TABLE documents ADD COLUMN owner_id BIGINT REFERENCES users(id) ON DELETE CASCADE")
    op.execute("CREATE INDEX documents_owner_id_idx ON documents (owner_id)")
    # Un même fichier peut être indexé une fois par propriétaire (et une fois en partagé).
    op.execute("DROP INDEX documents_sha256_idx")
    op.execute("CREATE UNIQUE INDEX documents_owner_sha256_idx ON documents (COALESCE(owner_id, 0), sha256)")


def downgrade() -> None:
    # Les documents privés redeviennent globaux ; un doublon entre propriétaires
    # ferait échouer la recréation de l'index unique global.
    op.execute("DROP INDEX IF EXISTS documents_owner_sha256_idx")
    op.execute("CREATE UNIQUE INDEX documents_sha256_idx ON documents (sha256)")
    op.execute("DROP INDEX IF EXISTS documents_owner_id_idx")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS owner_id")
    op.execute("DROP INDEX IF EXISTS sessions_user_updated_idx")
    op.execute("ALTER TABLE sessions DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE sessions DROP COLUMN IF EXISTS user_id")
    op.execute("DROP TABLE IF EXISTS auth_tokens, users")
