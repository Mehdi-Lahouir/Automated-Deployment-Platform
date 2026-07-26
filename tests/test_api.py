from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoints(client):
    assert client.get("/health/live").json() == {"status": "alive"}
    assert client.get("/health/ready").json() == {"status": "ready"}


def test_task_lifecycle(client):
    created = client.post("/tasks", json={"title": "Learn Docker"})
    assert created.status_code == 201
    task_id = created.json()["id"]

    listed = client.get("/tasks")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = client.get(f"/tasks/{task_id}")
    assert fetched.json()["title"] == "Learn Docker"

    updated = client.patch(
        f"/tasks/{task_id}",
        json={"title": "Learn Kubernetes", "completed": True},
    )
    assert updated.status_code == 200
    assert updated.json()["completed"] is True

    deleted = client.delete(f"/tasks/{task_id}")
    assert deleted.status_code == 204
    assert client.get(f"/tasks/{task_id}").status_code == 404


def test_validation_and_missing_tasks(client):
    assert client.post("/tasks", json={"title": ""}).status_code == 422
    assert client.get("/tasks/999").status_code == 404
    assert client.patch("/tasks/999", json={"completed": True}).status_code == 404
    assert client.delete("/tasks/999").status_code == 404
    assert client.get("/tasks", params={"limit": 101}).status_code == 422


def test_dashboard_info_and_metrics(client):
    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert dashboard.headers["content-type"].startswith("text/html")
    assert "TaskFlow" in dashboard.text
    assert "/static/app.js" in dashboard.text

    assert client.get("/api/info").json() == {
        "service": "task-manager",
        "status": "running",
    }

    stylesheet = client.get("/static/styles.css")
    assert stylesheet.status_code == 200
    assert stylesheet.headers["content-type"].startswith("text/css")

    metrics_dashboard = client.get("/metrics-view")
    assert metrics_dashboard.status_code == 200
    assert "System <span>pulse.</span>" in metrics_dashboard.text
    assert "/static/metrics.js" in metrics_dashboard.text

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "http_requests_total" in metrics.text


def test_protected_routes_reject_missing_api_key():
    with TestClient(app) as unauthenticated:
        assert unauthenticated.get("/tasks").status_code == 401
        assert unauthenticated.post("/tasks", json={"title": "Blocked"}).status_code == 401
        assert unauthenticated.get("/api/info").status_code == 401


def test_security_headers(client):
    response = client.get("/")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["referrer-policy"] == "no-referrer"

    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "/static/docs.js" in docs.text
    assert "<script>" not in docs.text
    assert "https://cdn.jsdelivr.net" in docs.headers["content-security-policy"]
    assert "script-src 'self' https://cdn.jsdelivr.net;" in docs.headers["content-security-policy"]
