import secrets
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import HOMN_KEY

# Même convention que l'API OpenAI : "Authorization: Bearer <clé>".
_bearer = HTTPBearer(auto_error=False)

async def verify_token(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    """
    Vérifie la clé Homn passée dans l'en-tête Authorization.
    Lève une erreur 401 si elle est manquante ou invalide.
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Clé Homn manquante (en-tête Authorization: Bearer <clé>).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not HOMN_KEY or not secrets.compare_digest(credentials.credentials, HOMN_KEY):
        raise HTTPException(
            status_code=401,
            detail="Clé Homn invalide.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
