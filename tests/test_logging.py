import json
import logging
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from app.logging_config import JsonFormatter
from app.main import app


def test_json_formatter_emits_only_allowed_fields():
    record = logging.LogRecord(
        name="task_manager",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="secret task title",
        args=(),
        exc_info=None,
    )
    record.event = "request_completed"
    record.request_id = "demo-request"
    record.method = "POST"
    record.route = "/tasks"
    record.status = 201
    record.duration_ms = 12.5
    record.api_key = "must-not-appear"
    record.request_body = '{"title":"must-not-appear"}'

    payload = JsonFormatter().format(record)
    parsed = json.loads(payload)

    assert parsed["event"] == "request_completed"
    assert parsed["request_id"] == "demo-request"
    assert parsed["route"] == "/tasks"
    assert "secret task title" not in payload
    assert "must-not-appear" not in payload
    assert "api_key" not in parsed
    assert "request_body" not in parsed


def test_request_id_is_returned_and_logged(client):
    with patch("app.main.logger.info") as log:
        response = client.get("/health/live", headers={"X-Request-ID": "portfolio-demo"})

    assert response.headers["X-Request-ID"] == "portfolio-demo"
    request_event = next(
        call for call in log.call_args_list if call.kwargs["extra"]["event"] == "request_completed"
    )
    assert request_event.kwargs["extra"]["request_id"] == "portfolio-demo"
    assert request_event.kwargs["extra"]["route"] == "/health/live"


def test_invalid_request_id_is_replaced(client):
    unsafe_id = "invalid value\r\nX-Leak: secret"
    with patch("app.main.logger.info") as log:
        response = client.get("/health/live", headers={"X-Request-ID": unsafe_id})

    generated_id = response.headers["X-Request-ID"]
    assert generated_id != unsafe_id
    assert len(generated_id) == 32
    request_event = next(
        call for call in log.call_args_list if call.kwargs["extra"]["event"] == "request_completed"
    )
    assert request_event.kwargs["extra"]["request_id"] == generated_id


def test_request_log_does_not_include_sensitive_request_data(client):
    secret_title = "confidential customer task"
    with patch("app.main.logger.info") as log:
        response = client.post(
            "/tasks?debug=private-query",
            json={"title": secret_title},
            headers={"X-API-Key": "test-api-key-with-at-least-24-characters"},
        )

    assert response.status_code == 201
    logged = repr(log.call_args_list)
    assert secret_title not in logged
    assert "private-query" not in logged
    assert "test-api-key" not in logged


def test_unmatched_path_is_not_written_to_logs(client):
    sensitive_path = "/not-found/private-customer-name"
    with patch("app.main.logger.info") as log:
        response = client.get(sensitive_path)

    assert response.status_code == 404
    request_event = next(
        call for call in log.call_args_list if call.kwargs["extra"]["event"] == "request_completed"
    )
    assert request_event.kwargs["extra"]["route"] == "unmatched"
    assert sensitive_path not in repr(log.call_args_list)


def test_concurrent_requests_receive_unique_correlation_ids(client):
    with ThreadPoolExecutor(max_workers=8) as executor:
        responses = list(executor.map(lambda _: client.get("/health/live"), range(20)))

    request_ids = [response.headers["X-Request-ID"] for response in responses]
    assert all(response.status_code == 200 for response in responses)
    assert len(set(request_ids)) == len(request_ids)


def test_unexpected_error_is_sanitized_and_correlated(client):
    def fail_for_test():
        raise RuntimeError("database-password-must-not-appear")

    app.add_api_route("/__test_failure", fail_for_test, include_in_schema=False)
    added_route = app.routes[-1]
    try:
        with patch("app.main.logger.error") as log:
            response = client.get(
                "/__test_failure",
                headers={"X-Request-ID": "failure-demo"},
            )
    finally:
        app.routes.remove(added_route)

    assert response.status_code == 500
    assert response.json() == {"detail": "internal server error"}
    assert response.headers["X-Request-ID"] == "failure-demo"
    assert log.call_args.kwargs["extra"]["event"] == "request_failed"
    assert log.call_args.kwargs["extra"]["exception_type"] == "RuntimeError"
    assert "database-password" not in repr(log.call_args_list)
