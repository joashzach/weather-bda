"""Public news and advisory REST API endpoints conforming to PRD Section 7.2."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.schemas.common import PaginatedResponse
from app.schemas.news import NewsItemPublic
from app.services.news import NewsService

settings = get_settings()
router = APIRouter(prefix="/news", tags=["News"])


@router.get(
    "",
    response_model=PaginatedResponse[NewsItemPublic],
    summary="List news and advisory items",
    description="Returns sanitized, paginated news and meteorological advisory items from verified RSS/Atom feeds.",
)
@limiter.limit(settings.RATE_LIMIT_PUBLIC_READ)
def list_news(
    request: Request,
    source: str | None = Query(
        default=None,
        description="Filter by data source slug name (e.g., 'rss_imd_advisories')",
    ),
    from_time: datetime | None = Query(
        default=None,
        alias="from",
        description="Filter items published_at >= from (UTC ISO 8601)",
    ),
    to_time: datetime | None = Query(
        default=None,
        alias="to",
        description="Filter items published_at <= to (UTC ISO 8601)",
    ),
    category: str | None = Query(
        default=None,
        description="Filter by item category ('news', 'advisory_feed')",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Page limit (default 50, maximum 200)",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Page offset (default 0)",
    ),
    db: Session = Depends(get_db),
) -> PaginatedResponse[NewsItemPublic]:
    return NewsService.list_news(
        db=db,
        source_slug=source,
        from_time=from_time,
        to_time=to_time,
        category=category,
        limit=limit,
        offset=offset,
    )
