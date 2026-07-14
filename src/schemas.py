from pydantic import BaseModel

class ComputeRequest(BaseModel):
    prompt: str
    session_id: str

class ComputeResponse(BaseModel):
    session_id: str
    response: str
    status: str = "success"

