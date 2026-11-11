from fastapi import APIRouter, Depends
from typing import Any, Dict, List
from src.client.dependencies import relay_error, session_token
from src.client.services import jaden
from src.client.services.jaden import ServerError
from src.schemas import DeckImport

router = APIRouter(tags=["Conversations"])


@router.get("/sessions")
async def list_sessions(token: str = Depends(session_token)) -> List[Dict[str, Any]]:
    try:
        return await jaden.list_sessions(token)
    except ServerError as e:
        raise relay_error(e)


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, token: str = Depends(session_token)) -> List[Dict[str, Any]]:
    try:
        return await jaden.get_messages(token, session_id)
    except ServerError as e:
        raise relay_error(e)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, token: str = Depends(session_token)):
    try:
        await jaden.delete_session(token, session_id)
    except ServerError as e:
        raise relay_error(e)


@router.get("/sessions/{session_id}/deck")
async def get_deck(session_id: str, token: str = Depends(session_token)) -> Dict[str, Any]:
    try:
        return await jaden.get_deck(token, session_id)
    except ServerError as e:
        raise relay_error(e)


@router.put("/sessions/{session_id}/deck")
async def import_deck(session_id: str, request: DeckImport, token: str = Depends(session_token)) -> Dict[str, Any]:
    try:
        return await jaden.import_deck(token, session_id, request.name, request.content)
    except ServerError as e:
        raise relay_error(e)


@router.delete("/sessions/{session_id}/deck", status_code=204)
async def delete_deck(session_id: str, token: str = Depends(session_token)):
    try:
        await jaden.delete_deck(token, session_id)
    except ServerError as e:
        raise relay_error(e)
