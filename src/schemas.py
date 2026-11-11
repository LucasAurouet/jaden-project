from datetime import datetime
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
