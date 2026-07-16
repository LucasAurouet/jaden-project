from fastapi import APIRouter, Depends
from src.schemas import ComputeRequest, ComputeResponse
from src.api.dependencies import verify_token
from api.services.chat import ChatService

router = APIRouter(tags=["Conversations"])

@router.post("/compute", response_model=ComputeResponse)
async def compute(
    request: ComputeRequest,
    _token: str = Depends(verify_token),
) -> ComputeResponse:

    return await ChatService.process_compute(
        session_id=request.session_id,
        prompt=request.prompt
    )