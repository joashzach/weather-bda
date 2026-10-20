"""Location API routes conforming to PRD Section 7.2."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.locations import LocationListResponse
from app.services.locations import LocationService

router = APIRouter(prefix="/locations", tags=["Locations"])


@router.get(
    "",
    response_model=LocationListResponse,
    summary="List active weather collection locations",
    description="Returns all configured active locations for data collection and analytics.",
)
def list_locations(db: Session = Depends(get_db)) -> LocationListResponse:
    return LocationService.list_active_locations(db)
