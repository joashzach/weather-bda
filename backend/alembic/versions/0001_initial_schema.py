"""Initial schema with all 9 core tables, constraints, partial indexes, and append-only triggers.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-19 14:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('admin', 'reviewer')", name="ck_users_role"),
    )
    op.create_index("uq_users_lower_email", "users", [sa.text("lower(email)")], unique=True)

    # 2. locations
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("slug", sa.String(length=50), nullable=False, unique=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=8, scale=5), nullable=False),
        sa.Column("longitude", sa.Numeric(precision=8, scale=5), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "latitude >= -90.00000 AND latitude <= 90.00000", name="ck_locations_latitude"
        ),
        sa.CheckConstraint(
            "longitude >= -180.00000 AND longitude <= 180.00000", name="ck_locations_longitude"
        ),
    )

    # 3. data_sources
    op.create_table(
        "data_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("adapter_key", sa.String(length=50), nullable=False),
        sa.Column("trust_level", sa.String(length=30), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("interval_seconds", sa.Integer(), nullable=False, server_default=sa.text("3600")),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("attribution_text", sa.Text(), nullable=False),
        sa.Column("license_url", sa.String(length=2048), nullable=True),
        sa.Column("homepage_url", sa.String(length=2048), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_type IN ('weather_api', 'rss', 'open_dataset', 'citizen')",
            name="ck_data_sources_source_type",
        ),
        sa.CheckConstraint(
            "trust_level IN ('official', 'provider_model', 'news', 'citizen')",
            name="ck_data_sources_trust_level",
        ),
        sa.CheckConstraint("interval_seconds >= 300", name="ck_data_sources_interval_seconds"),
    )

    # 4. ingestion_runs
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("data_sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column(
            "triggered_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column(
            "queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_fetched", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("inserted", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_summary", sa.String(length=1000), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("trigger IN ('scheduled', 'manual')", name="ck_ingestion_runs_trigger"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'partial', 'failed', 'abandoned')",
            name="ck_ingestion_runs_status",
        ),
        sa.CheckConstraint("records_fetched >= 0", name="ck_ingestion_runs_records_fetched"),
        sa.CheckConstraint("inserted >= 0", name="ck_ingestion_runs_inserted"),
        sa.CheckConstraint("updated >= 0", name="ck_ingestion_runs_updated"),
        sa.CheckConstraint("skipped >= 0", name="ck_ingestion_runs_skipped"),
        sa.CheckConstraint("failed >= 0", name="ck_ingestion_runs_failed"),
    )
    # Partial unique index for concurrent overlap prevention
    op.create_index(
        "uq_ingestion_runs_source_active",
        "ingestion_runs",
        ["source_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )

    # 5. weather_records
    op.create_table(
        "weather_records",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "location_id",
            sa.Integer(),
            sa.ForeignKey("locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("data_sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("record_kind", sa.String(length=20), nullable=False),
        sa.Column("measurement_basis", sa.String(length=30), nullable=False),
        sa.Column("valid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resolution_seconds", sa.Integer(), nullable=False, server_default=sa.text("3600")
        ),
        sa.Column("temperature_c", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("apparent_temperature_c", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("relative_humidity_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("precipitation_mm", sa.Numeric(precision=7, scale=2), nullable=True),
        sa.Column("rain_mm", sa.Numeric(precision=7, scale=2), nullable=True),
        sa.Column("precipitation_probability_pct", sa.SmallInteger(), nullable=True),
        sa.Column("wind_speed_kmh", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("wind_gust_kmh", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("wind_direction_deg", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "ingestion_run_id",
            sa.BigInteger(),
            sa.ForeignKey("ingestion_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "location_id", "source_id", "record_kind", "valid_at", name="uq_weather_records_dedupe"
        ),
        sa.CheckConstraint(
            "record_kind IN ('observation', 'forecast')", name="ck_weather_records_record_kind"
        ),
        sa.CheckConstraint(
            "measurement_basis IN ('station', 'model_analysis', 'model_forecast', 'unknown')",
            name="ck_weather_records_measurement_basis",
        ),
        sa.CheckConstraint(
            "(record_kind = 'forecast' AND issued_at IS NOT NULL) OR (record_kind = 'observation' AND issued_at IS NULL)",
            name="ck_weather_records_forecast_issued_at",
        ),
        sa.CheckConstraint(
            "temperature_c IS NULL OR (temperature_c >= -90.00 AND temperature_c <= 60.00)",
            name="ck_weather_records_temperature_c",
        ),
        sa.CheckConstraint(
            "relative_humidity_pct IS NULL OR (relative_humidity_pct >= 0.00 AND relative_humidity_pct <= 100.00)",
            name="ck_weather_records_humidity_pct",
        ),
        sa.CheckConstraint(
            "precipitation_mm IS NULL OR (precipitation_mm >= 0.00 AND precipitation_mm <= 1000.00)",
            name="ck_weather_records_precip_mm",
        ),
        sa.CheckConstraint(
            "rain_mm IS NULL OR (rain_mm >= 0.00 AND rain_mm <= 1000.00)",
            name="ck_weather_records_rain_mm",
        ),
        sa.CheckConstraint(
            "precipitation_probability_pct IS NULL OR (precipitation_probability_pct >= 0 AND precipitation_probability_pct <= 100)",
            name="ck_weather_records_precip_prob",
        ),
        sa.CheckConstraint(
            "wind_speed_kmh IS NULL OR (wind_speed_kmh >= 0.00 AND wind_speed_kmh <= 500.00)",
            name="ck_weather_records_wind_speed",
        ),
        sa.CheckConstraint(
            "wind_gust_kmh IS NULL OR (wind_gust_kmh >= 0.00 AND wind_gust_kmh <= 500.00)",
            name="ck_weather_records_wind_gust",
        ),
        sa.CheckConstraint(
            "wind_direction_deg IS NULL OR (wind_direction_deg >= 0.00 AND wind_direction_deg <= 360.00)",
            name="ck_weather_records_wind_direction",
        ),
    )
    op.create_index(
        "ix_weather_records_location_kind_valid",
        "weather_records",
        ["location_id", "record_kind", sa.text("valid_at DESC")],
    )
    op.create_index(
        "ix_weather_records_source_valid",
        "weather_records",
        ["source_id", sa.text("valid_at DESC")],
    )

    # 6. citizen_reports
    op.create_table(
        "citizen_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location_name", sa.String(length=200), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=8, scale=5), nullable=False),
        sa.Column("longitude", sa.Numeric(precision=8, scale=5), nullable=False),
        sa.Column(
            "location_id",
            sa.Integer(),
            sa.ForeignKey("locations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("contact_email", sa.String(length=254), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("tracking_token_hash", sa.String(length=64), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('heavy_rain', 'flood', 'heatwave', 'cold_wave', 'storm', 'cyclone', 'drought', 'landslide', 'lightning', 'hail', 'fog', 'other')",
            name="ck_citizen_reports_event_type",
        ),
        sa.CheckConstraint(
            "severity IS NULL OR severity IN ('low', 'moderate', 'high', 'extreme')",
            name="ck_citizen_reports_severity",
        ),
        sa.CheckConstraint(
            "length(description) >= 10 AND length(description) <= 2000",
            name="ck_citizen_reports_description_len",
        ),
        sa.CheckConstraint(
            "latitude >= -90.00000 AND latitude <= 90.00000", name="ck_citizen_reports_latitude"
        ),
        sa.CheckConstraint(
            "longitude >= -180.00000 AND longitude <= 180.00000",
            name="ck_citizen_reports_longitude",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'verified', 'rejected')", name="ck_citizen_reports_status"
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND reviewed_at IS NULL) OR (status != 'pending' AND reviewed_at IS NOT NULL)",
            name="ck_citizen_reports_reviewed_at",
        ),
    )
    op.create_index(
        "ix_citizen_reports_status_submitted", "citizen_reports", ["status", "submitted_at"]
    )
    op.create_index(
        "ix_citizen_reports_event_type_status", "citizen_reports", ["event_type", "status"]
    )
    op.create_index(
        "ix_citizen_reports_location_status_event_time",
        "citizen_reports",
        ["location_id", "status", sa.text("event_time DESC")],
    )
    op.create_index(
        "ix_citizen_reports_event_time", "citizen_reports", [sa.text("event_time DESC")]
    )

    # 7. report_reviews
    op.create_table(
        "report_reviews",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("citizen_reports.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "reviewer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(length=20), nullable=False),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("private_notes", sa.Text(), nullable=True),
        sa.Column("reason_code", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "private_notes IS NULL OR length(private_notes) <= 2000",
            name="ck_report_reviews_private_notes_len",
        ),
    )
    op.create_index(
        "ix_report_reviews_report_created", "report_reviews", ["report_id", "created_at"]
    )

    # 8. news_items
    op.create_table(
        "news_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("data_sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("source_id", "dedupe_key", name="uq_news_items_source_dedupe"),
        sa.CheckConstraint("category IN ('news', 'advisory_feed')", name="ck_news_items_category"),
        sa.CheckConstraint(
            "summary IS NULL OR length(summary) <= 2000", name="ck_news_items_summary_len"
        ),
    )
    op.create_index("ix_news_items_published", "news_items", [sa.text("published_at DESC")])

    # 9. audit_events
    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # 10. Append-only immutability triggers for report_reviews and audit_events
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_modification_report_reviews()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Table report_reviews is append-only. UPDATE, DELETE, and TRUNCATE are prohibited.';
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_report_reviews_no_modify
        BEFORE UPDATE OR DELETE ON report_reviews
        FOR EACH STATEMENT EXECUTE FUNCTION prevent_modification_report_reviews();

        CREATE TRIGGER trg_report_reviews_no_truncate
        BEFORE TRUNCATE ON report_reviews
        FOR EACH STATEMENT EXECUTE FUNCTION prevent_modification_report_reviews();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_modification_audit_events()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Table audit_events is append-only. UPDATE, DELETE, and TRUNCATE are prohibited.';
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_audit_events_no_modify
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH STATEMENT EXECUTE FUNCTION prevent_modification_audit_events();

        CREATE TRIGGER trg_audit_events_no_truncate
        BEFORE TRUNCATE ON audit_events
        FOR EACH STATEMENT EXECUTE FUNCTION prevent_modification_audit_events();
        """
    )


def downgrade() -> None:
    # Drop triggers and functions
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_no_truncate ON audit_events;")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_no_modify ON audit_events;")
    op.execute("DROP FUNCTION IF EXISTS prevent_modification_audit_events();")

    op.execute("DROP TRIGGER IF EXISTS trg_report_reviews_no_truncate ON report_reviews;")
    op.execute("DROP TRIGGER IF EXISTS trg_report_reviews_no_modify ON report_reviews;")
    op.execute("DROP FUNCTION IF EXISTS prevent_modification_report_reviews();")

    # Drop tables in reverse order of foreign key dependencies
    op.drop_table("audit_events")
    op.drop_table("news_items")
    op.drop_table("report_reviews")
    op.drop_table("citizen_reports")
    op.drop_table("weather_records")
    op.drop_table("ingestion_runs")
    op.drop_table("data_sources")
    op.drop_table("locations")
    op.drop_table("users")
