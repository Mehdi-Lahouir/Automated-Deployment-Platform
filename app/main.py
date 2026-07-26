import hmac
import os
import re
import time
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, Security, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.logging_config import configure_logging
from app.models import Task
from app.schemas import TaskCreate, TaskResponse, TaskUpdate

DbSession = Annotated[Session, Depends(get_db)]
STATIC_DIR = Path(__file__).resolve().parent / "static"
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
RATE_WINDOW_SECONDS = 60
request_history: dict[str, deque[float]] = defaultdict(deque)
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
logger = configure_logging()

REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "path"],
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    api_key = os.getenv("APP_API_KEY", "")
    if len(api_key) < 24:
        raise RuntimeError("APP_API_KEY must be set to a secret value of at least 24 characters")
    Base.metadata.create_all(bind=engine)
    logger.info("Application started", extra={"event": "application_started"})
    yield
    logger.info("Application stopped", extra={"event": "application_stopped"})


app = FastAPI(
    title="Task Manager API",
    version=os.getenv("APP_VERSION", "dev"),
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def normalized_route(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", "unmatched")


@app.middleware("http")
async def record_metrics(request: Request, call_next):
    started = time.perf_counter()
    supplied_request_id = request.headers.get("X-Request-ID", "")
    request_id = (
        supplied_request_id
        if REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
        else uuid.uuid4().hex
    )
    request.state.request_id = request_id
    response = None
    request_failed = False

    if request.url.path.startswith("/tasks"):
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        history = request_history[client]
        while history and history[0] <= now - RATE_WINDOW_SECONDS:
            history.popleft()
        if len(history) >= RATE_LIMIT:
            response = Response(
                content='{"detail":"rate limit exceeded"}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
                headers={"Retry-After": str(RATE_WINDOW_SECONDS)},
            )
        else:
            history.append(now)

    try:
        if response is None:
            response = await call_next(request)
    except Exception as exc:
        path = normalized_route(request)
        duration = time.perf_counter() - started
        request_failed = True
        REQUESTS.labels(request.method, path, 500).inc()
        LATENCY.labels(request.method, path).observe(duration)
        logger.error(
            "Request failed",
            extra={
                "event": "request_failed",
                "request_id": request_id,
                "method": request.method,
                "route": path,
                "status": 500,
                "duration_ms": round(duration * 1000, 3),
                "exception_type": type(exc).__name__,
            },
        )
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "internal server error"},
        )

    path = normalized_route(request)
    duration = time.perf_counter() - started
    if not request_failed:
        REQUESTS.labels(request.method, path, response.status_code).inc()
        LATENCY.labels(request.method, path).observe(duration)
        logger.info(
            "Request completed",
            extra={
                "event": "request_completed",
                "request_id": request_id,
                "method": request.method,
                "route": path,
                "status": response.status_code,
                "duration_ms": round(duration * 1000, 3),
            },
        )

    response.headers["X-Request-ID"] = request_id
    if request.url.path == "/docs":
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' https://cdn.jsdelivr.net; "
            "style-src-attr 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; base-uri 'self'; "
            "frame-ancestors 'none'; form-action 'self'"
        )
    else:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; "
            "form-action 'self'"
        )
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def require_api_key(provided_key: Annotated[str | None, Security(API_KEY_HEADER)]) -> None:
    expected_key = os.environ["APP_API_KEY"]
    if provided_key is None or not hmac.compare_digest(provided_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing API key",
        )


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/metrics-view", include_in_schema=False)
def metrics_dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "metrics.html")


@app.get("/docs", include_in_schema=False)
def api_documentation() -> FileResponse:
    return FileResponse(STATIC_DIR / "docs.html")


@app.get("/api/info", tags=["system"], dependencies=[Security(require_api_key)])
def api_info() -> dict[str, str]:
    return {"service": "task-manager", "status": "running"}


@app.get("/health/live", tags=["system"])
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready", tags=["system"])
def readiness(db: DbSession) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_api_key)],
)
def create_task(payload: TaskCreate, db: DbSession) -> Task:
    task = Task(title=payload.title)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@app.get(
    "/tasks",
    response_model=list[TaskResponse],
    dependencies=[Security(require_api_key)],
)
def list_tasks(
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Task]:
    query = select(Task).order_by(Task.id).offset(offset).limit(limit)
    return list(db.scalars(query).all())


@app.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    dependencies=[Security(require_api_key)],
)
def get_task(task_id: int, db: DbSession) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@app.patch(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    dependencies=[Security(require_api_key)],
)
def update_task(task_id: int, payload: TaskUpdate, db: DbSession) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@app.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Security(require_api_key)],
)
def delete_task(task_id: int, db: DbSession) -> Response:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    db.delete(task)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
