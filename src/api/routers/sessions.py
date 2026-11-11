from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict, List
from src.api.dependencies import get_current_user
from src.api.cards import decks
from src.api.cards.decks import DeckError
from src.api.services import database
from src.schemas import DeckImport, DeckOut, MessageOut, SessionOut

router = APIRouter(prefix="/sessions", tags=["Conversations"])


@router.get("")
async def list_sessions(user: Dict[str, Any] = Depends(get_current_user)) -> List[SessionOut]:
    return [SessionOut(**row) for row in await database.list_sessions(user["id"])]


@router.get("/{session_id}/messages")
async def get_messages(session_id: str, user: Dict[str, Any] = Depends(get_current_user)) -> List[MessageOut]:
    messages = await database.get_messages(session_id, user["id"])
    if messages is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return [MessageOut(**row) for row in messages]


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    if not await database.delete_session(session_id, user["id"]):
        raise HTTPException(status_code=404, detail="Conversation not found.")


# ─── Deck de la session ─────────────────────────────────────────────────────

@router.get("/{session_id}/deck")
async def get_deck(session_id: str, user: Dict[str, Any] = Depends(get_current_user)) -> DeckOut:
    deck = await decks.load_deck(session_id, user["id"])
    if deck is None:
        raise HTTPException(status_code=404, detail="No deck in this conversation.")
    return DeckOut(**deck.summary())


@router.put("/{session_id}/deck")
async def import_deck(
    session_id: str, request: DeckImport, user: Dict[str, Any] = Depends(get_current_user)
) -> DeckOut:
    """Importe (ou remplace) le deck ; crée la session si elle n'existe pas encore."""
    if len(session_id) > 64:
        raise HTTPException(status_code=422, detail="Invalid conversation id.")
    try:
        deck = await decks.import_deck(user["id"], session_id, request.name.strip(), request.content)
    except DeckError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except database.SessionOwnershipError:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return DeckOut(**deck.summary())


@router.delete("/{session_id}/deck", status_code=204)
async def delete_deck(session_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    if not await database.delete_deck(session_id, user["id"]):
        raise HTTPException(status_code=404, detail="No deck in this conversation.")
