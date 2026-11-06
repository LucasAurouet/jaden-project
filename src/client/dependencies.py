from fastapi import HTTPException, Request
from fastapi.responses import Response
from config import AUTH_TOKEN_TTL_DAYS, COOKIE_SECURE
from src.client.services.homn import ServerError

# Jeton de connexion du navigateur. HttpOnly : invisible au JavaScript de la page.
# SameSite=Strict : jamais envoyé par une requête venue d'un autre site (CSRF).
COOKIE_NAME = "homn_session"


def session_token(request: Request) -> str:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Connexion requise.")
    return token


def set_session_cookie(response: Response, token: str):
    response.set_cookie(
        COOKIE_NAME, token,
        max_age=AUTH_TOKEN_TTL_DAYS * 86400,
        httponly=True, samesite="strict", secure=COOKIE_SECURE,
    )


def clear_session_cookie(response: Response):
    response.delete_cookie(COOKIE_NAME, httponly=True, samesite="strict", secure=COOKIE_SECURE)


def relay_error(e: ServerError) -> HTTPException:
    return HTTPException(status_code=e.status, detail=str(e))
