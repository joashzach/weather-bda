"""Integration tests for CLI seed commands: seed-sources and seed-locations."""

import argparse
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.cli import cmd_seed_locations, cmd_seed_sources
from app.db.models.data_sources import DataSource
from app.db.models.locations import Location
from tests.conftest import test_engine


@pytest.fixture(autouse=True)
def clean_seeds(setup_test_db):
    """Ensure data_sources and locations are clean before and after tests."""

    def _do_clean():
        with test_engine.begin() as conn:
            conn.execute(text("DELETE FROM weather_records"))
            conn.execute(text("DELETE FROM ingestion_runs"))
            conn.execute(text("DELETE FROM locations"))
            conn.execute(text("DELETE FROM data_sources"))

    _do_clean()
    yield
    _do_clean()


def test_seed_sources_idempotent(db_session: Session, monkeypatch):
    monkeypatch.setattr("app.cli.SessionLocal", lambda: db_session)
    args = argparse.Namespace()

    # 1. First run seeds sources
    exit_code = cmd_seed_sources(args)
    assert exit_code == 0

    sources = db_session.query(DataSource).all()
    source_names = {s.name for s in sources}
    assert "open_meteo" in source_names
    assert "citizen_reports" in source_names
    assert "rss_imd_advisories" in source_names
    assert "data_gov_in_realtime" in source_names
    assert len(sources) == 4

    open_meteo = db_session.query(DataSource).filter_by(name="open_meteo").one()
    assert open_meteo.adapter_key == "open_meteo"
    assert open_meteo.trust_level == "provider_model"
    assert "Open-Meteo.com" in open_meteo.attribution_text

    rss_imd = db_session.query(DataSource).filter_by(name="rss_imd_advisories").one()
    assert rss_imd.is_enabled is False
    assert rss_imd.adapter_key == "rss"

    dgov = db_session.query(DataSource).filter_by(name="data_gov_in_realtime").one()
    assert dgov.is_enabled is False
    assert dgov.adapter_key == "data_gov_in"

    # 2. Second run is idempotent
    exit_code2 = cmd_seed_sources(args)
    assert exit_code2 == 0
    assert db_session.query(DataSource).count() == 4


def test_seed_locations_from_default_yaml(db_session: Session, monkeypatch):
    monkeypatch.setattr("app.cli.SessionLocal", lambda: db_session)

    # Use actual config/locations.yaml
    default_yaml = Path(__file__).resolve().parent.parent.parent / "config" / "locations.yaml"
    args = argparse.Namespace(file=str(default_yaml))

    # 1. Seed locations from default YAML
    exit_code = cmd_seed_locations(args)
    assert exit_code == 0

    locations = db_session.query(Location).all()
    assert len(locations) == 5
    slugs = {loc.slug for loc in locations}
    assert slugs == {"mumbai", "delhi", "bengaluru", "chennai", "kolkata"}

    # Verify coordinates of Mumbai
    mumbai = db_session.query(Location).filter_by(slug="mumbai").one()
    assert float(mumbai.latitude) == pytest.approx(19.076, abs=1e-3)
    assert float(mumbai.longitude) == pytest.approx(72.877, abs=1e-3)
    assert mumbai.is_active is True

    # 2. Second run is idempotent
    exit_code2 = cmd_seed_locations(args)
    assert exit_code2 == 0
    assert db_session.query(Location).count() == 5


def test_seed_locations_file_not_found(db_session: Session, monkeypatch):
    monkeypatch.setattr("app.cli.SessionLocal", lambda: db_session)
    args = argparse.Namespace(file="non_existent_path.yaml")

    exit_code = cmd_seed_locations(args)
    assert exit_code == 1


def test_seed_locations_empty_and_invalid(db_session: Session, monkeypatch, tmp_path):
    monkeypatch.setattr("app.cli.SessionLocal", lambda: db_session)

    # 1. Empty YAML
    empty_file = tmp_path / "empty.yaml"
    empty_file.write_text("locations: []\n", encoding="utf-8")
    exit_code = cmd_seed_locations(argparse.Namespace(file=str(empty_file)))
    assert exit_code == 0

    # 2. Invalid YAML syntax
    invalid_file = tmp_path / "invalid.yaml"
    invalid_file.write_text("locations: [unclosed list", encoding="utf-8")
    exit_code = cmd_seed_locations(argparse.Namespace(file=str(invalid_file)))
    assert exit_code == 1
