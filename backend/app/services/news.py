"""News service handling business logic, validation, and serialization for news and advisory items."""

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models.news_items import NewsItem
from app.repositories.news import NewsRepository
from app.schemas.common import PaginatedResponse
from app.schemas.news import NewsItemPublic, NewsSourceSummary

ALLOWED_CATEGORIES = {"news", "advisory_feed"}


def _to_news_public(item: NewsItem) -> NewsItemPublic:
    source_summary = NewsSourceSummary(
        id=item.source.id,
        name=item.source.name,
        display_name=item.source.display_name,
        trust_level=item.source.trust_level,
    )
    is_official = item.source.trust_level == "official"

    return NewsItemPublic(
        id=item.id,
        source=source_summary,
        title=item.title,
        summary=item.summary,
        url=item.url,
        published_at=item.published_at,
        fetched_at=item.fetched_at,
        category=item.category,
        is_official=is_official,
    )


class NewsService:
    @staticmethod
    def list_news(
        db: Session,
        source_slug: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse[NewsItemPublic]:
        if category and category not in ALLOWED_CATEGORIES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_error",
                    "message": f"Invalid category '{category}'. Allowed: {sorted(ALLOWED_CATEGORIES)}",
                },
            )

        if from_time and to_time:
            if from_time >= to_time:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "validation_error",
                        "message": "'from' timestamp must be strictly earlier than 'to' timestamp",
                    },
                )
            if (to_time - from_time).total_seconds() > 366 * 86400:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "validation_error",
                        "message": "Maximum allowed time span for news list is 366 days",
                    },
                )

        repo = NewsRepository(db)
        items, total = repo.list_news(
            source_slug=source_slug,
            from_time=from_time,
            to_time=to_time,
            category=category,
            limit=limit,
            offset=offset,
        )

        mapped_items = [_to_news_public(it) for it in items]
        return PaginatedResponse(
            items=mapped_items,
            total=total,
            limit=limit,
            offset=offset,
        )
