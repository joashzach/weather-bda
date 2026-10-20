"""RSS and Atom syndication feed ingestion adapter conforming to PRD Section 8.3."""

import hashlib
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import feedparser
import nh3

from app.core.config import Settings
from app.core.http_client import SafeHttpClient
from app.core.logging import get_logger
from app.db.models.data_sources import DataSource
from app.ingestion.adapters.base import AdapterResult, BaseAdapter, TargetError
from app.ingestion.normalizers import NormalizedNewsItem

logger = get_logger("app.ingestion.adapters.rss_atom")

MAX_FEED_ENTRIES = 200
ALLOWED_NEWS_CATEGORIES = {"news", "advisory_feed"}


class RssAtomAdapter(BaseAdapter):
    key = "rss"

    def is_configured(self, source: DataSource, settings: Settings) -> bool:
        """Check that the data source has a non-empty feed_url and a valid category."""
        cfg = source.config or {}
        feed_url = cfg.get("feed_url")
        category = cfg.get("category", "news")

        if not feed_url or not isinstance(feed_url, str) or not feed_url.strip():
            return False

        return category in ALLOWED_NEWS_CATEGORIES

    def run(
        self,
        source: DataSource,
        targets: list[Any],
        http_client: SafeHttpClient,
        settings: Settings,
    ) -> AdapterResult:
        """Fetch feed bytes through guarded HTTP client, parse with feedparser, sanitize, and normalize."""
        cfg = source.config or {}
        feed_url = cfg.get("feed_url", "").strip()
        category = cfg.get("category", "news")

        if not feed_url:
            return AdapterResult(
                errors=[
                    TargetError(
                        target_key=source.name,
                        error_code="missing_feed_url",
                        message="DataSource config does not contain a valid feed_url",
                    )
                ],
                failed_count=1,
            )

        # 1. Fetch raw bytes safely via SafeHttpClient (enforces SSRF protection & response size limits)
        try:
            response = http_client.get(feed_url)
            response.raise_for_status()
            content_bytes = response.content
        except Exception as exc:
            logger.error("rss_fetch_failed", feed_url=feed_url, error=str(exc))
            return AdapterResult(
                errors=[
                    TargetError(
                        target_key=feed_url,
                        error_code="http_fetch_error",
                        message=f"Failed to fetch feed: {exc}"[:1000],
                    )
                ],
                failed_count=1,
            )

        # 2. Parse in-memory bytes using feedparser (NEVER pass URL directly to feedparser)
        feed = feedparser.parse(content_bytes)

        # 3. Handle malformed feeds
        errors: list[TargetError] = []
        if feed.bozo and not feed.entries:
            bozo_exc = str(getattr(feed, "bozo_exception", "Malformed feed structure"))
            logger.error("rss_malformed_feed", feed_url=feed_url, error=bozo_exc)
            return AdapterResult(
                errors=[
                    TargetError(
                        target_key=feed_url,
                        error_code="feed_malformed",
                        message=f"Malformed feed with no entries: {bozo_exc}"[:1000],
                    )
                ],
                failed_count=1,
            )

        # Non-fatal warnings (bozo with entries)
        if feed.bozo and feed.entries:
            bozo_exc = str(getattr(feed, "bozo_exception", "XML warning"))
            errors.append(
                TargetError(
                    target_key=feed_url,
                    error_code="feed_parse_warning",
                    message=f"Feed parsed with warning: {bozo_exc}"[:1000],
                )
            )

        # 4. Normalize up to MAX_FEED_ENTRIES entries
        now = datetime.now(UTC)
        raw_entries = feed.entries[:MAX_FEED_ENTRIES]
        news_items: list[NormalizedNewsItem] = []

        for entry in raw_entries:
            # Title: sanitize with nh3 (strip all HTML tags), collapse whitespace, truncate to 500
            raw_title = entry.get("title", "")
            cleaned_title = " ".join(nh3.clean(raw_title, tags=set()).split())
            if not cleaned_title:
                continue
            title = cleaned_title[:500]

            # Summary: sanitize with nh3, collapse whitespace, truncate to 2000
            raw_summary = entry.get("summary") or entry.get("description") or ""
            cleaned_summary = " ".join(nh3.clean(raw_summary, tags=set()).split())
            summary = cleaned_summary[:2000] if cleaned_summary else None

            # URL: accept only http / https schemes up to 2048 chars
            raw_url = (entry.get("link") or "").strip()
            parsed_url = urlparse(raw_url)
            if parsed_url.scheme.lower() not in ("http", "https") or len(raw_url) > 2048:
                continue
            url = raw_url

            # Published at: from published_parsed or updated_parsed converted to UTC, else NULL
            pub_struct = entry.get("published_parsed") or entry.get("updated_parsed")
            published_at = None
            if pub_struct:
                try:
                    published_at = datetime(*pub_struct[:6], tzinfo=UTC)
                except (ValueError, TypeError):
                    published_at = None

            # Dedupe key: sha256 of GUID / link / (title + published)
            guid = entry.get("id") or entry.get("guid") or url
            if not guid:
                guid = f"{title}{published_at.isoformat() if published_at else ''}"
            dedupe_key = hashlib.sha256(guid.encode("utf-8")).hexdigest()

            # Content hash: sha256 of title + summary + url
            content_str = f"{title}{summary or ''}{url}"
            content_hash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()

            news_items.append(
                NormalizedNewsItem(
                    source_id=source.id,
                    dedupe_key=dedupe_key,
                    title=title,
                    summary=summary,
                    url=url,
                    published_at=published_at,
                    fetched_at=now,
                    category=category,
                    content_hash=content_hash,
                )
            )

        return AdapterResult(
            records=[],
            news_records=news_items,
            errors=errors,
            fetched_count=len(news_items),
            failed_count=0,
        )
