"""Weather records table storing high-volume observations and forecasts with content-hash deduplication."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    desc,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WeatherRecord(Base):
    __tablename__ = "weather_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("data_sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    record_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    measurement_basis: Mapped[str] = mapped_column(String(30), nullable=False)
    valid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)

    # Core measurements (null means not provided, never zero)
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    apparent_temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    relative_humidity_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    precipitation_mm: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    rain_mm: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    precipitation_probability_pct: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    wind_speed_kmh: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    wind_gust_kmh: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    wind_direction_deg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingestion_run_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("ingestion_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    location = relationship("Location")
    source = relationship("DataSource")

    __table_args__ = (
        UniqueConstraint(
            "location_id",
            "source_id",
            "record_kind",
            "valid_at",
            name="uq_weather_records_dedupe",
        ),
        CheckConstraint(
            "record_kind IN ('observation', 'forecast')",
            name="ck_weather_records_record_kind",
        ),
        CheckConstraint(
            "measurement_basis IN ('station', 'model_analysis', 'model_forecast', 'unknown')",
            name="ck_weather_records_measurement_basis",
        ),
        CheckConstraint(
            "(record_kind = 'forecast' AND issued_at IS NOT NULL) OR (record_kind = 'observation' AND issued_at IS NULL)",
            name="ck_weather_records_forecast_issued_at",
        ),
        CheckConstraint(
            "temperature_c IS NULL OR (temperature_c >= -90.00 AND temperature_c <= 60.00)",
            name="ck_weather_records_temperature_c",
        ),
        CheckConstraint(
            "relative_humidity_pct IS NULL OR (relative_humidity_pct >= 0.00 AND relative_humidity_pct <= 100.00)",
            name="ck_weather_records_humidity_pct",
        ),
        CheckConstraint(
            "precipitation_mm IS NULL OR (precipitation_mm >= 0.00 AND precipitation_mm <= 1000.00)",
            name="ck_weather_records_precip_mm",
        ),
        CheckConstraint(
            "rain_mm IS NULL OR (rain_mm >= 0.00 AND rain_mm <= 1000.00)",
            name="ck_weather_records_rain_mm",
        ),
        CheckConstraint(
            "precipitation_probability_pct IS NULL OR (precipitation_probability_pct >= 0 AND precipitation_probability_pct <= 100)",
            name="ck_weather_records_precip_prob",
        ),
        CheckConstraint(
            "wind_speed_kmh IS NULL OR (wind_speed_kmh >= 0.00 AND wind_speed_kmh <= 500.00)",
            name="ck_weather_records_wind_speed",
        ),
        CheckConstraint(
            "wind_gust_kmh IS NULL OR (wind_gust_kmh >= 0.00 AND wind_gust_kmh <= 500.00)",
            name="ck_weather_records_wind_gust",
        ),
        CheckConstraint(
            "wind_direction_deg IS NULL OR (wind_direction_deg >= 0.00 AND wind_direction_deg <= 360.00)",
            name="ck_weather_records_wind_direction",
        ),
        Index(
            "ix_weather_records_location_kind_valid", "location_id", "record_kind", desc("valid_at")
        ),
        Index("ix_weather_records_source_valid", "source_id", desc("valid_at")),
    )
