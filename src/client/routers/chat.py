from fastapi import APIRouter
from src.client.services.chat import ChatService
from src.schemas import ComputeRequest, ComputeResponse

router = APIRouter(tags=["Conversations"])

@router.post("/compute", response_model=ComputeResponse)
async def compute(request: ComputeRequest) -> ComputeResponse:
    return await ChatService.process_compute(
        session_id=request.session_id,
        prompt=request.prompt
    )
