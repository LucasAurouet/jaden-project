from datetime import datetime
from typing import List
from pydantic import BaseModel, Field

class ComputeRequest(BaseModel):
    prompt: str
    # Généré par le navigateur (UUID) : la session est créée au premier échange.
    session_id: str = Field(min_length=1, max_length=64)

class LoginRequest(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool

class LoginResponse(BaseModel):
    token: str
    user: UserOut

class SessionOut(BaseModel):
    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime

class MessageOut(BaseModel):
    role: str
    content: str
    created_at: datetime

class DeckImport(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    # Contenu du fichier .ydk.
    content: str = Field(min_length=1, max_length=50_000)

class DeckCardOut(BaseModel):
    id: int
    name: str
    qty: int
    section: str
    frame_type: str

class DeckOut(BaseModel):
    name: str
    main: int
    extra: int
    side: int
    # Taille estimée du deck dans le prompt système.
    tokens: int
    cards: List[DeckCardOut]
    # Ids du .ydk introuvables dans la base (renseigné à l'import seulement).
    unresolved: List[str] = []
