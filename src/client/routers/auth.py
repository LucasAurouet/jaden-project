from fastapi import APIRouter, Depends, Request, Response
from typing import Any, Dict
from src.client.dependencies import (
    COOKIE_NAME, clear_session_cookie, relay_error, session_token, set_session_cookie,
)
from src.client.services import jaden
from src.client.services.jaden import ServerError
from src.schemas import LoginRequest

router = APIRouter(tags=["Authentification"])


@router.post("/login")
async def login(request: LoginRequest, response: Response) -> Dict[str, Any]:
    try:
        result = await jaden.login(request.username, request.password)
    except ServerError as e:
        raise relay_error(e)
    # Le jeton reste dans le cookie : la page ne reçoit que l'utilisateur.
    set_session_cookie(response, result["token"])
    return result["user"]


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        try:
            await jaden.logout(token)
        except ServerError:
            pass   # Jeton déjà expiré ou serveur injoignable : le cookie est effacé quand même.
    clear_session_cookie(response)


@router.get("/me")
async def me(token: str = Depends(session_token)) -> Dict[str, Any]:
    try:
        return await jaden.me(token)
    except ServerError as e:
        raise relay_error(e)
