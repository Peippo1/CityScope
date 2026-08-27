import asyncio

from fastapi import APIRouter, Depends, HTTPException, status

from .. import config
from ..admission import AdmissionLease, admission
from ..agent.schemas import InvestigationRequest, InvestigationResult
from ..agent.service import InvestigationService

router = APIRouter(tags=["investigations"])


@router.post("/investigate", response_model=InvestigationResult)
async def investigate(request: InvestigationRequest, lease: AdmissionLease = Depends(admission.acquire)) -> InvestigationResult:
    try:
        async with lease:
            return await asyncio.wait_for(InvestigationService().investigate(request), timeout=config.INVESTIGATION_TIMEOUT_SECONDS)
    except TimeoutError:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Investigation timed out. Try a narrower question.") from None
