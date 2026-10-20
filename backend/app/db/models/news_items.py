"""News and advisory items table ingested from verified RSS/Atom feeds."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    desc,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("data_sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    source = relationship("DataSource")

    __table_args__ = (
        UniqueConstraint("source_id", "dedupe_key", name="uq_news_items_source_dedupe"),
        CheckConstraint("category IN ('news', 'advisory_feed')", name="ck_news_items_category"),
        CheckConstraint(
            "summary IS NULL OR length(summary) <= 2000", name="ck_news_items_summary_len"
        ),
        Index("ix_news_items_published", desc("published_at")),
    )
