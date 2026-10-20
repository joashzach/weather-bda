"""Unit tests for RSS/Atom syndication adapter conforming to PRD Section 8.3."""

from unittest.mock import MagicMock

import httpx

from app.core.config import Settings
from app.db.models.data_sources import DataSource
from app.ingestion.adapters.rss_atom import RssAtomAdapter

SAMPLE_VALID_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>IMD National Weather Bulletin</title>
    <link>https://mausam.imd.gov.in/</link>
    <description>Daily meteorological bulletin and alerts</description>
    <item>
      <title>Heavy &lt;b&gt;Rainfall&lt;/b&gt; Alert for &lt;script&gt;alert(1)&lt;/script&gt;Coastal Areas</title>
      <link>https://mausam.imd.gov.in/bulletins/2026-10-20.pdf</link>
      <description>&lt;p&gt;Widespread rainfall expected &lt;a href="http://spam.link"&gt;over coastal districts&lt;/a&gt;.&lt;/p&gt;</description>
      <guid isPermaLink="false">imd-bulletin-20261020-001</guid>
      <pubDate>Tue, 20 Oct 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Dense Fog Warning</title>
      <link>ftp://invalid-scheme.internal/file.txt</link>
      <description>Low visibility expected.</description>
      <guid isPermaLink="false">imd-bulletin-20261020-002</guid>
    </item>
    <item>
      <title>Second Advisory Without Published Date</title>
      <link>https://mausam.imd.gov.in/bulletins/advisory-2.html</link>
      <description>Scattered thunderstorms.</description>
      <guid isPermaLink="false">imd-bulletin-20261020-003</guid>
    </item>
  </channel>
</rss>
"""

SAMPLE_MALFORMED_XML = """<?xml version="1.0"?>
<corrupted><unclosed_tag>This is not a valid feed
"""


def test_rss_is_configured():
    adapter = RssAtomAdapter()
    settings = Settings()

    # 1. Missing feed_url
    s1 = DataSource(name="rss1", config={})
    assert adapter.is_configured(s1, settings) is False

    # 2. Invalid category
    s2 = DataSource(
        name="rss2", config={"feed_url": "https://example.com/rss", "category": "invalid_cat"}
    )
    assert adapter.is_configured(s2, settings) is False

    # 3. Valid configuration
    s3 = DataSource(
        name="rss3", config={"feed_url": "https://example.com/rss", "category": "advisory_feed"}
    )
    assert adapter.is_configured(s3, settings) is True


def test_rss_parsing_and_sanitization():
    adapter = RssAtomAdapter()
    settings = Settings()
    source = DataSource(
        id=10,
        name="rss_imd",
        config={"feed_url": "https://mausam.imd.gov.in/feed.xml", "category": "advisory_feed"},
    )

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.content = SAMPLE_VALID_RSS.encode("utf-8")
    mock_resp.raise_for_status = MagicMock()
    mock_client.get.return_value = mock_resp

    res = adapter.run(source, targets=[], http_client=mock_client, settings=settings)

    assert res.failed_count == 0
    # Entry 2 has ftp:// URL which must be skipped; entries 1 and 3 are valid
    assert len(res.news_records) == 2

    item1 = res.news_records[0]
    # Check HTML tags stripped and whitespace collapsed
    assert "<b>" not in item1.title
    assert "<script>" not in item1.title
    assert item1.title == "Heavy Rainfall Alert for Coastal Areas"
    assert "<p>" not in item1.summary
    assert "<a>" not in item1.summary
    assert item1.summary == "Widespread rainfall expected over coastal districts."
    assert item1.url == "https://mausam.imd.gov.in/bulletins/2026-10-20.pdf"
    assert item1.published_at is not None
    assert item1.published_at.year == 2026
    assert item1.published_at.month == 10
    assert item1.published_at.day == 20
    assert item1.category == "advisory_feed"
    assert len(item1.dedupe_key) == 64
    assert len(item1.content_hash) == 64

    # Entry 3 has no published_parsed: published_at must be None (never replaced with fetch time!)
    item3 = res.news_records[1]
    assert item3.published_at is None
    assert item3.title == "Second Advisory Without Published Date"


def test_rss_malformed_feed_returns_failed_status():
    adapter = RssAtomAdapter()
    settings = Settings()
    source = DataSource(
        id=10,
        name="rss_imd",
        config={"feed_url": "https://mausam.imd.gov.in/broken.xml", "category": "news"},
    )

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.content = SAMPLE_MALFORMED_XML.encode("utf-8")
    mock_resp.raise_for_status = MagicMock()
    mock_client.get.return_value = mock_resp

    res = adapter.run(source, targets=[], http_client=mock_client, settings=settings)
    assert res.failed_count == 1
    assert len(res.errors) == 1
    assert res.errors[0].error_code == "feed_malformed"


def test_rss_network_error_handled_gracefully():
    adapter = RssAtomAdapter()
    settings = Settings()
    source = DataSource(
        id=10,
        name="rss_imd",
        config={"feed_url": "https://mausam.imd.gov.in/offline.xml", "category": "news"},
    )

    mock_client = MagicMock()
    mock_client.get.side_effect = httpx.ConnectTimeout("Connection timed out")

    res = adapter.run(source, targets=[], http_client=mock_client, settings=settings)
    assert res.failed_count == 1
    assert len(res.errors) == 1
    assert res.errors[0].error_code == "http_fetch_error"
