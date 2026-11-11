import secrets
from typing import Any, Dict
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import JADEN_KEY
from src.api.services.auth import user_from_token

# Même convention que l'API OpenAI : "Authorization: Bearer <clé>".
_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


async def verify_token(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    """
    Vérifie la clé Jaden passée dans l'en-tête Authorization (accès machine au
    proxy OpenAI brut). Lève une erreur 401 si elle est manquante ou invalide.
    """
    if credentials is None:
        raise _unauthorized("Clé Jaden manquante (en-tête Authorization: Bearer <clé>).")
    if not JADEN_KEY or not secrets.compare_digest(credentials.credentials, JADEN_KEY):
        raise _unauthorized("Clé Jaden invalide.")
    return credentials.credentials


async def bearer_token(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    if credentials is None:
        raise _unauthorized("Connexion requise.")
    return credentials.credentials


async def get_current_user(token: str = Depends(bearer_token)) -> Dict[str, Any]:
    """Utilisateur du jeton de connexion ; 401 s'il est inconnu, expiré ou révoqué."""
    user = await user_from_token(token)
    if user is None:
        raise _unauthorized("Session expirée : reconnectez-vous.")
    return user
