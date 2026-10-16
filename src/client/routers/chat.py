from fastapi import APIRouter
from src.client.services import homn
from src.schemas import ComputeRequest, ComputeResponse

router = APIRouter(tags=["Conversations"])

@router.post("/compute", response_model=ComputeResponse)
async def compute(request: ComputeRequest) -> ComputeResponse:
    return await homn.compute(
        session_id=request.session_id,
        prompt=request.prompt
    )
