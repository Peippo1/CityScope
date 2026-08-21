from fastapi import APIRouter

from ..agent.schemas import InvestigationRequest, InvestigationResult
from ..agent.service import InvestigationService

router = APIRouter(tags=["investigations"])


@router.post("/investigate", response_model=InvestigationResult)
async def investigate(request: InvestigationRequest) -> InvestigationResult:
    return await InvestigationService().investigate(request)

