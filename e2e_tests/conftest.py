import os
import socket
import threading
import time
from collections.abc import Generator

import httpx
import pytest
import uvicorn
from alembic import command
from alembic.config import Config

API_KEY = "e2e-api-key-with-at-least-24-characters"


def _available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def app_url(tmp_path_factory: pytest.TempPathFactory) -> Generator[str, None, None]:
    database = tmp_path_factory.mktemp("taskflow-e2e") / "tasks.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
    os.environ["APP_API_KEY"] = API_KEY
    os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"

    command.upgrade(Config("alembic.ini"), "head")

    from app.main import app

    port = _available_port()
    url = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{url}/health/ready", timeout=0.5).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.1)
    else:
        server.should_exit = True
        thread.join(timeout=5)
        pytest.fail("TaskFlow did not become ready for the browser test")

    yield url

    server.should_exit = True
    thread.join(timeout=5)
