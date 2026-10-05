import secrets
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import MAIA_KEY

# Même convention que l'API OpenAI : "Authorization: Bearer <clé>".
# N'importe quelle bibliothèque compatible OpenAI peut ainsi s'authentifier.
_bearer = HTTPBearer(auto_error=False)

async def verify_token(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    """
    Vérifie la clé Maia passée dans l'en-tête Authorization.
    Lève une erreur 401 si elle est manquante ou invalide.
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Clé MAIA manquante (en-tête Authorization: Bearer <clé>).",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # compare_digest prend un temps constant : on ne peut pas deviner la clé
    # caractère par caractère en mesurant le temps de réponse.
    if not MAIA_KEY or not secrets.compare_digest(credentials.credentials, MAIA_KEY):
        raise HTTPException(
            status_code=401,
            detail="Clé MAIA invalide.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
