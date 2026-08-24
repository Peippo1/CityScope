from fastapi import APIRouter, Depends, HTTPException, Response, status

from ..auth import CurrentUser, get_current_user
from ..history import InvestigationStore, SavedInvestigation, SavedInvestigationCreate, get_history_store


router = APIRouter(prefix="/me/investigations", tags=["saved investigations"])


@router.post("", response_model=SavedInvestigation, status_code=status.HTTP_201_CREATED)
def save_investigation(payload: SavedInvestigationCreate, user: CurrentUser = Depends(get_current_user), store: InvestigationStore = Depends(get_history_store)) -> SavedInvestigation:
    return store.create(user, payload)


@router.get("", response_model=list[SavedInvestigation])
def list_investigations(user: CurrentUser = Depends(get_current_user), store: InvestigationStore = Depends(get_history_store)) -> list[SavedInvestigation]:
    return store.list(user)


@router.get("/{investigation_id}", response_model=SavedInvestigation)
def get_investigation(investigation_id: str, user: CurrentUser = Depends(get_current_user), store: InvestigationStore = Depends(get_history_store)) -> SavedInvestigation:
    result = store.get(user, investigation_id)
    if not result:
        raise HTTPException(status_code=404, detail="Saved investigation was not found")
    return result


@router.delete("/{investigation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_investigation(investigation_id: str, user: CurrentUser = Depends(get_current_user), store: InvestigationStore = Depends(get_history_store)) -> Response:
    if not store.delete(user, investigation_id):
        raise HTTPException(status_code=404, detail="Saved investigation was not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
