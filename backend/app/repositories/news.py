"""News items repository handling database queries and persistence conforming to PRD Section 4.7 and Section 8.3."""

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db.models.data_sources import DataSource
from app.db.models.news_items import NewsItem


class NewsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_news(
        self,
        source_slug: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[NewsItem], int]:
        """Query news items with optional filters, joined source relationship, and published_at DESC ordering."""
        stmt = select(NewsItem).options(joinedload(NewsItem.source))
        count_stmt = select(func.count(NewsItem.id))

        if source_slug:
            stmt = stmt.join(DataSource, NewsItem.source_id == DataSource.id).where(
                DataSource.name == source_slug
            )
            count_stmt = count_stmt.join(DataSource, NewsItem.source_id == DataSource.id).where(
                DataSource.name == source_slug
            )

        if from_time:
            stmt = stmt.where(NewsItem.published_at >= from_time)
            count_stmt = count_stmt.where(NewsItem.published_at >= from_time)

        if to_time:
            stmt = stmt.where(NewsItem.published_at <= to_time)
            count_stmt = count_stmt.where(NewsItem.published_at <= to_time)

        if category:
            stmt = stmt.where(NewsItem.category == category)
            count_stmt = count_stmt.where(NewsItem.category == category)

        total = self.db.scalar(count_stmt) or 0

        stmt = (
            stmt.order_by(NewsItem.published_at.desc().nullslast(), NewsItem.id.desc())
            .limit(limit)
            .offset(offset)
        )
        items = list(self.db.scalars(stmt).all())

        return items, total

    def bulk_upsert(
        self,
        source_id: int,
        items: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Deduplicate and upsert news items based on (source_id, dedupe_key) and content_hash.

        Returns statistics: {'inserted': int, 'updated': int, 'skipped': int}.
        """
        if not items:
            return {"inserted": 0, "updated": 0, "skipped": 0}

        dedupe_keys = [item["dedupe_key"] for item in items]
        existing_stmt = select(NewsItem).where(
            NewsItem.source_id == source_id,
            NewsItem.dedupe_key.in_(dedupe_keys),
        )
        existing_items = {r.dedupe_key: r for r in self.db.scalars(existing_stmt).all()}

        inserted = 0
        updated = 0
        skipped = 0

        for item_data in items:
            key = item_data["dedupe_key"]
            if key in existing_items:
                existing = existing_items[key]
                if existing.content_hash == item_data["content_hash"]:
                    skipped += 1
                else:
                    existing.title = item_data["title"]
                    existing.summary = item_data.get("summary")
                    existing.url = item_data["url"]
                    existing.content_hash = item_data["content_hash"]
                    existing.fetched_at = item_data["fetched_at"]
                    if item_data.get("published_at") is not None:
                        existing.published_at = item_data["published_at"]
                    updated += 1
            else:
                new_item = NewsItem(
                    source_id=source_id,
                    dedupe_key=item_data["dedupe_key"],
                    title=item_data["title"],
                    summary=item_data.get("summary"),
                    url=item_data["url"],
                    published_at=item_data.get("published_at"),
                    fetched_at=item_data["fetched_at"],
                    category=item_data["category"],
                    content_hash=item_data["content_hash"],
                )
                self.db.add(new_item)
                existing_items[key] = new_item
                inserted += 1

        self.db.flush()
        return {"inserted": inserted, "updated": updated, "skipped": skipped}
