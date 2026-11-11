import asyncio
import hashlib
import secrets
from typing import Any, Dict, Tuple
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from config import AUTH_TOKEN_TTL_DAYS
from src.api.services import database

_hasher = PasswordHasher()

# Vérifié quand le compte n'existe pas : la réponse prend le même temps,
# et ne révèle donc pas quels noms d'utilisateur existent.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))

# Pause après un échec, pour freiner les essais de mots de passe en série.
FAILED_LOGIN_DELAY = 1.0

MIN_PASSWORD_LENGTH = 8


class AuthError(Exception):
    """Identifiants refusés."""


async def hash_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"The password must be at least {MIN_PASSWORD_LENGTH} characters long.")
    # argon2 est volontairement lent : hors de la boucle asyncio.
    return await asyncio.to_thread(_hasher.hash, password)


async def _verify_password(password_hash: str, password: str) -> bool:
    try:
        return await asyncio.to_thread(_hasher.verify, password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def login(username: str, password: str) -> Tuple[str, Dict[str, Any]]:
    """Renvoie un nouveau jeton et l'utilisateur ; lève AuthError sinon."""
    user = await database.get_user_credentials(username)
    valid = await _verify_password(user["password_hash"] if user else _DUMMY_HASH, password)
    if not (user and valid):
        await asyncio.sleep(FAILED_LOGIN_DELAY)
        raise AuthError("Wrong username or password.")

    token = secrets.token_urlsafe(32)
    await database.create_token(user["id"], _token_hash(token), AUTH_TOKEN_TTL_DAYS)
    del user["password_hash"]
    return token, user


async def logout(token: str):
    await database.delete_token(_token_hash(token))


async def user_from_token(token: str) -> Dict[str, Any] | None:
    return await database.get_user_by_token(_token_hash(token))
