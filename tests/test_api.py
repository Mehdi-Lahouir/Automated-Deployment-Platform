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


def test_root_and_metrics(client):
    assert client.get("/").json()["service"] == "task-manager"
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "http_requests_total" in metrics.text
