"""Location service managing business logic and mapping to response schemas."""

from sqlalchemy.orm import Session

from app.repositories.locations import LocationRepository
from app.schemas.locations import LocationListResponse, LocationPublic


class LocationService:
    @staticmethod
    def list_active_locations(db: Session) -> LocationListResponse:
        repo = LocationRepository(db)
        locations = repo.list_active()
        items = [
            LocationPublic(
                id=loc.id,
                slug=loc.slug,
                name=loc.name,
                region=loc.region,
                country_code=loc.country_code,
                latitude=float(loc.latitude),
                longitude=float(loc.longitude),
            )
            for loc in locations
        ]
        return LocationListResponse(items=items)
