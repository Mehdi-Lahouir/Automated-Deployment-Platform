import os
from pathlib import Path

test_database = Path(__file__).resolve().parent.parent / "test_tasks.db"
os.environ["DATABASE_URL"] = f"sqlite:///{test_database.as_posix()}"
os.environ["APP_API_KEY"] = "test-api-key-with-at-least-24-characters"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(
        app,
        headers={"X-API-Key": os.environ["APP_API_KEY"]},
    ) as test_client:
        yield test_client
