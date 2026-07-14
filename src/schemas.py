from pydantic import BaseModel

class ComputeRequest(BaseModel):
    prompt: str
    session_id: str

