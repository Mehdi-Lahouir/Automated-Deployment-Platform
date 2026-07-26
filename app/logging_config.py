import json
import logging
import sys
from datetime import UTC, datetime

LOG_FIELDS = (
    "event",
    "request_id",
    "method",
    "route",
    "status",
    "duration_ms",
    "exception_type",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, str | int | float] = {
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "service": "task-api",
            "event": getattr(record, "event", "application_event"),
        }
        for field in LOG_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, separators=(",", ":"))


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("task_manager")
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logging.getLogger("uvicorn.access").disabled = True
    return logger
