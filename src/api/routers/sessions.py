from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict, List
from src.api.dependencies import get_current_user
from src.api.services import database
from src.schemas import MessageOut, SessionOut

router = APIRouter(prefix="/sessions", tags=["Conversations"])


@router.get("")
async def list_sessions(user: Dict[str, Any] = Depends(get_current_user)) -> List[SessionOut]:
    return [SessionOut(**row) for row in await database.list_sessions(user["id"])]


@router.get("/{session_id}/messages")
async def get_messages(session_id: str, user: Dict[str, Any] = Depends(get_current_user)) -> List[MessageOut]:
    messages = await database.get_messages(session_id, user["id"])
    if messages is None:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    return [MessageOut(**row) for row in messages]


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    if not await database.delete_session(session_id, user["id"]):
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
