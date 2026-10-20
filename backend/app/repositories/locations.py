"""Location repository handling persistence and querying of geographic locations."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models.locations import Location


class LocationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, location_id: int) -> Location | None:
        return self.db.execute(
            select(Location).where(Location.id == location_id)
        ).scalar_one_or_none()

    def get_by_slug(self, slug: str) -> Location | None:
        return self.db.execute(
            select(Location).where(Location.slug == slug.strip().lower())
        ).scalar_one_or_none()

    def list_active(self) -> Sequence[Location]:
        stmt = (
            select(Location)
            .where(Location.is_active.is_(True))
            .order_by(Location.name.asc(), Location.id.asc())
        )
        return self.db.execute(stmt).scalars().all()

    def list_all(self) -> Sequence[Location]:
        stmt = select(Location).order_by(Location.name.asc(), Location.id.asc())
        return self.db.execute(stmt).scalars().all()

    def upsert(
        self,
        slug: str,
        name: str,
        region: str | None,
        country_code: str,
        latitude: float,
        longitude: float,
        is_active: bool = True,
    ) -> Location:
        """Idempotent upsert by slug using PostgreSQL ON CONFLICT."""
        normalized_slug = slug.strip().lower()
        stmt = (
            insert(Location)
            .values(
                slug=normalized_slug,
                name=name.strip(),
                region=region.strip() if region else None,
                country_code=country_code.strip().upper(),
                latitude=latitude,
                longitude=longitude,
                is_active=is_active,
            )
            .on_conflict_do_update(
                index_elements=[Location.slug],
                set_={
                    "name": name.strip(),
                    "region": region.strip() if region else None,
                    "country_code": country_code.strip().upper(),
                    "latitude": latitude,
                    "longitude": longitude,
                    "is_active": is_active,
                },
            )
            .returning(Location)
        )
        location = self.db.execute(stmt).scalar_one()
        return location
