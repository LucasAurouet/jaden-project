from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader
from config import MAIA_KEY

# Déclaration de l'en-tête de sécurité
_api_key_header = APIKeyHeader(name="maia-token", auto_error=False)

async def verify_token(api_key: str = Depends(_api_key_header)) -> str:
    """
    Vérifie la validité du token d'API Maia passé dans les en-têtes HTTP.
    Lève une erreur 403 si le jeton est manquant ou invalide.
    """
    if not api_key:
        raise HTTPException(
            status_code=403, 
            detail="Clé de sécurité MAIA manquante dans les en-têtes (maia-token)."
        )
    if api_key != MAIA_KEY:
        raise HTTPException(
            status_code=403, 
            detail="Clé MAIA invalide ou expirée."
        )
    return api_key