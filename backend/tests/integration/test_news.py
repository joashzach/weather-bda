"""Integration tests for News and Advisory RSS/Atom ingestion and REST API endpoints."""

import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.data_sources import DataSource
from app.db.models.news_items import NewsItem
from app.ingestion.adapters.base import AdapterResult
from app.ingestion.normalizers import NormalizedNewsItem
from app.ingestion.pipeline import IngestionPipeline
from app.repositories.news import NewsRepository
from app.repositories.sources import DataSourceRepository

SAMPLE_FEED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>IMD Cyclone Warning Bulletin</title>
    <link>https://mausam.imd.gov.in/</link>
    <item>
      <title>Cyclone Alert 1</title>
      <link>https://mausam.imd.gov.in/cyclone/01.html</link>
      <description>Heavy sea conditions expected.</description>
      <guid>cyclone-01</guid>
      <pubDate>Tue, 20 Oct 2026 08:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Cyclone Alert 2</title>
      <link>https://mausam.imd.gov.in/cyclone/02.html</link>
      <description>Gale wind warning.</description>
      <guid>cyclone-02</guid>
      <pubDate>Tue, 20 Oct 2026 09:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def _setup_news_sources(db: Session) -> dict[str, DataSource]:
    source_repo = DataSourceRepository(db)

    # 1. Official IMD advisories source
    imd = source_repo.get_by_name("rss_imd_test")
    if not imd:
        imd = DataSource(
            name="rss_imd_test",
            display_name="IMD Alerts",
            source_type="rss",
            adapter_key="rss",
            trust_level="official",
            is_enabled=True,
            interval_seconds=3600,
            attribution_text="India Meteorological Department",
            config={"feed_url": "https://mausam.imd.gov.in/feed.xml", "category": "advisory_feed"},
        )
        db.add(imd)

    # 2. News media source
    news_media = source_repo.get_by_name("rss_media_test")
    if not news_media:
        news_media = DataSource(
            name="rss_media_test",
            display_name="Weather Daily News",
            source_type="rss",
            adapter_key="rss",
            trust_level="news",
            is_enabled=True,
            interval_seconds=3600,
            attribution_text="Weather Daily News",
            config={"feed_url": "https://example.com/rss.xml", "category": "news"},
        )
        db.add(news_media)

    db.commit()
    db.refresh(imd)
    db.refresh(news_media)
    return {"imd": imd, "media": news_media}


def test_news_repository_deduplication(db_session: Session):
    sources = _setup_news_sources(db_session)
    source = sources["imd"]
    repo = NewsRepository(db_session)

    now = datetime.now(UTC)
    h1 = hashlib.sha256(b"title1summary1url1").hexdigest()
    h2 = hashlib.sha256(b"title2summary2url2").hexdigest()

    items = [
        {
            "dedupe_key": "k1" + "0" * 62,
            "title": "Title 1",
            "summary": "Summary 1",
            "url": "https://example.com/1",
            "published_at": now - timedelta(hours=2),
            "fetched_at": now,
            "category": "advisory_feed",
            "content_hash": h1,
        },
        {
            "dedupe_key": "k2" + "0" * 62,
            "title": "Title 2",
            "summary": "Summary 2",
            "url": "https://example.com/2",
            "published_at": now - timedelta(hours=1),
            "fetched_at": now,
            "category": "advisory_feed",
            "content_hash": h2,
        },
    ]

    # 1. First run: both inserted
    res1 = repo.bulk_upsert(source.id, items)
    db_session.commit()
    assert res1["inserted"] == 2
    assert res1["updated"] == 0
    assert res1["skipped"] == 0

    # 2. Second run with identical content: both skipped
    res2 = repo.bulk_upsert(source.id, items)
    db_session.commit()
    assert res2["inserted"] == 0
    assert res2["updated"] == 0
    assert res2["skipped"] == 2

    # 3. Third run: item 1 modified, item 2 unchanged
    h1_mod = hashlib.sha256(b"title1_modifiedsummary1url1").hexdigest()
    items_mod = [
        {
            "dedupe_key": "k1" + "0" * 62,
            "title": "Title 1 Modified",
            "summary": "Summary 1",
            "url": "https://example.com/1",
            "published_at": now - timedelta(hours=2),
            "fetched_at": now,
            "category": "advisory_feed",
            "content_hash": h1_mod,
        },
        items[1],
    ]
    res3 = repo.bulk_upsert(source.id, items_mod)
    db_session.commit()
    assert res3["inserted"] == 0
    assert res3["updated"] == 1
    assert res3["skipped"] == 1


def test_rss_pipeline_execution_and_news_persistence():
    from tests.conftest import TestingSessionLocal

    with TestingSessionLocal() as db:
        sources = _setup_news_sources(db)
        source_id = sources["imd"].id

    now = datetime.now(UTC)
    mock_items = [
        NormalizedNewsItem(
            source_id=source_id,
            dedupe_key="mock_k1_" + "0" * 56,
            title="Severe Cyclone Warning",
            summary="Expected landfall tomorrow evening",
            url="https://mausam.imd.gov.in/bulletin-01.html",
            published_at=now,
            fetched_at=now,
            category="advisory_feed",
            content_hash=hashlib.sha256(b"cyclone-warning").hexdigest(),
        )
    ]
    mock_adapter_result = AdapterResult(
        records=[],
        news_records=mock_items,
        errors=[],
        fetched_count=1,
        failed_count=0,
    )

    with patch(
        "app.ingestion.adapters.rss_atom.RssAtomAdapter.run", return_value=mock_adapter_result
    ):
        pipeline = IngestionPipeline(session_factory=TestingSessionLocal)
        run = pipeline.execute_run(source_id=source_id)

        assert run.status == "succeeded"
        assert run.records_fetched == 1
        assert run.inserted == 1

    # Verify persisted row in news_items
    with TestingSessionLocal() as db:
        persisted = db.query(NewsItem).filter(NewsItem.dedupe_key == "mock_k1_" + "0" * 56).first()
        assert persisted is not None
        assert persisted.title == "Severe Cyclone Warning"
        assert persisted.category == "advisory_feed"
        # Cleanup
        db.delete(persisted)
        db.commit()


def test_get_news_api_endpoints_and_filters(client: TestClient, db_session: Session):
    sources = _setup_news_sources(db_session)
    imd = sources["imd"]
    media = sources["media"]

    now = datetime.now(UTC)
    t1 = now - timedelta(hours=5)
    t2 = now - timedelta(hours=2)

    # Clean existing test items
    db_session.query(NewsItem).delete()

    n1 = NewsItem(
        source_id=imd.id,
        dedupe_key="imd_01_" + "0" * 57,
        title="Official IMD Flood Warning",
        summary="Water levels crossing danger mark in Yamuna river",
        url="https://mausam.imd.gov.in/warning-1.html",
        published_at=t1,
        fetched_at=t1,
        category="advisory_feed",
        content_hash=hashlib.sha256(b"h1").hexdigest(),
    )
    n2 = NewsItem(
        source_id=media.id,
        dedupe_key="med_02_" + "0" * 57,
        title="Monsoon Arrives Early Across Northern States",
        summary="Farmers welcome early showers across the agricultural belt",
        url="https://example.com/monsoon.html",
        published_at=t2,
        fetched_at=t2,
        category="news",
        content_hash=hashlib.sha256(b"h2").hexdigest(),
    )
    db_session.add_all([n1, n2])
    db_session.commit()

    # 1. Unfiltered list: returns both items ordered published_at DESC
    r_all = client.get("/api/v1/news")
    assert r_all.status_code == 200
    data_all = r_all.json()
    assert data_all["total"] == 2
    items = data_all["items"]
    # Newest published first (n2 at -2h before n1 at -5h)
    assert items[0]["title"] == "Monsoon Arrives Early Across Northern States"
    assert items[0]["is_official"] is False  # Derived from 'news' trust level
    assert items[1]["title"] == "Official IMD Flood Warning"
    assert items[1]["is_official"] is True  # Derived from 'official' trust level

    # 2. Filter by source slug
    r_source = client.get(f"/api/v1/news?source={imd.name}")
    assert r_source.status_code == 200
    assert r_source.json()["total"] == 1
    assert r_source.json()["items"][0]["source"]["name"] == imd.name

    # 3. Filter by category
    r_cat = client.get("/api/v1/news?category=advisory_feed")
    assert r_cat.status_code == 200
    assert r_cat.json()["total"] == 1
    assert r_cat.json()["items"][0]["category"] == "advisory_feed"

    # 4. Filter by date window
    from_iso = (now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r_date = client.get(f"/api/v1/news?from={from_iso}")
    assert r_date.status_code == 200
    assert r_date.json()["total"] == 1
    assert r_date.json()["items"][0]["title"] == "Monsoon Arrives Early Across Northern States"

    # 5. Validation error: invalid category
    r_invalid_cat = client.get("/api/v1/news?category=gossip")
    assert r_invalid_cat.status_code == 422
    assert "invalid category" in r_invalid_cat.text.lower()

    # 6. Validation error: from >= to
    r_invalid_range = client.get(
        f"/api/v1/news?from={now.isoformat()}&to={(now - timedelta(days=1)).isoformat()}"
    )
    assert r_invalid_range.status_code == 422

    # 7. Validation error: span > 366 days
    old_time = (now - timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ")
    now_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    r_oversize_span = client.get(f"/api/v1/news?from={old_time}&to={now_time}")
    assert r_oversize_span.status_code == 422
    assert "366 days" in r_oversize_span.text
