"""Pytest test configuration, fixtures, socket blocking guard, and database lifecycle."""

import socket
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.base import Base
from app.db.session import get_db
from app.main import app

# PRD Section 6.3 & 10: Rate limiting disabled strictly in test suite
limiter.enabled = False

settings = get_settings()

# PRD Section 10 Rule: TEST_DATABASE_URL must end in _test; suite aborts otherwise
test_db_url = settings.TEST_DATABASE_URL
db_name = test_db_url.split("/")[-1].split("?")[0]
if not db_name.endswith("_test"):
    raise RuntimeError(
        f"CRITICAL: TEST_DATABASE_URL '{test_db_url}' is invalid. The database name must end in '_test'."
    )

test_engine = create_engine(test_db_url, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> Generator[None, None, None]:
    """Ensure rate limiter remains disabled by default during test execution."""
    limiter.enabled = False
    yield
    limiter.enabled = False


@pytest.fixture(autouse=True)
def block_external_sockets(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """PRD Section 10 Rule: Block all outbound network sockets in tests except local database, unless marked live."""
    if request.node.get_closest_marker("live"):
        return

    original_connect = socket.socket.connect

    def guarded_connect(self: socket.socket, address: Any) -> None:
        if isinstance(address, tuple):
            host = address[0]
            # Allow connections to localhost / 127.0.0.1 / ::1
            if host in ("127.0.0.1", "localhost", "::1"):
                return original_connect(self, address)
        raise RuntimeError(
            f"Outbound network socket connection to {address} is forbidden in test suite."
        )

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db() -> Generator[None, None, None]:
    """Create all tables in test database once per session using alembic upgrade head per PRD Section 10."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    alembic_ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", test_db_url.replace("%", "%%"))

    try:
        with test_engine.connect():
            pass
    except Exception as e:
        pytest.skip(f"Test database is not reachable at {test_db_url}: {e}")

    # Exercise alembic upgrade head once at start of test session
    command.upgrade(alembic_cfg, "head")
    yield
    # Clean teardown
    try:
        command.downgrade(alembic_cfg, "base")
    except Exception:
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session(setup_test_db) -> Generator[Session, None, None]:
    """Provide a transactional session with automatic rollback for state isolation."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient with overridden get_db dependency pointing to the isolated test transaction."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
