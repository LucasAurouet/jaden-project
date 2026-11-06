from fastapi import APIRouter, Depends
from typing import Any, Dict, List
from src.client.dependencies import relay_error, session_token
from src.client.services import homn
from src.client.services.homn import ServerError

router = APIRouter(tags=["Conversations"])


@router.get("/sessions")
async def list_sessions(token: str = Depends(session_token)) -> List[Dict[str, Any]]:
    try:
        return await homn.list_sessions(token)
    except ServerError as e:
        raise relay_error(e)


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, token: str = Depends(session_token)) -> List[Dict[str, Any]]:
    try:
        return await homn.get_messages(token, session_id)
    except ServerError as e:
        raise relay_error(e)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, token: str = Depends(session_token)):
    try:
        await homn.delete_session(token, session_id)
    except ServerError as e:
        raise relay_error(e)
