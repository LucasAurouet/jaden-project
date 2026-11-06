from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict
from src.api.dependencies import bearer_token, get_current_user
from src.api.services import auth
from src.schemas import LoginRequest, LoginResponse, UserOut

router = APIRouter(prefix="/auth", tags=["Authentification"])


@router.post("/login")
async def login(request: LoginRequest) -> LoginResponse:
    try:
        token, user = await auth.login(request.username, request.password)
    except auth.AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return LoginResponse(token=token, user=UserOut(**user))


@router.post("/logout", status_code=204)
async def logout(token: str = Depends(bearer_token)):
    await auth.logout(token)


@router.get("/me")
async def me(user: Dict[str, Any] = Depends(get_current_user)) -> UserOut:
    return UserOut(**user)
