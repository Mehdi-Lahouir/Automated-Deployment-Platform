import json
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_loki_retention_and_alloy_collectors_are_configured():
    loki = yaml.safe_load((PROJECT_ROOT / "k8s/observability/loki.yml").read_text())
    compose_alloy = (PROJECT_ROOT / "monitoring/alloy/compose.alloy").read_text()
    kubernetes_alloy = (PROJECT_ROOT / "k8s/alloy-config.alloy").read_text()

    assert loki["limits_config"]["retention_period"] == "168h"
    assert "loki.source.docker" in compose_alloy
    assert "docker-socket-proxy:2375" in compose_alloy
    assert "loki.source.kubernetes" in kubernetes_alloy
    assert 'names = ["task-manager"]' in kubernetes_alloy


def test_grafana_has_loki_dashboard_and_six_alerts():
    datasource_path = (
        PROJECT_ROOT / "k8s/observability/grafana/provisioning/datasources/datasources.yml"
    )
    rules_path = PROJECT_ROOT / "k8s/observability/grafana/provisioning/alerting/rules.yml"
    dashboard_path = PROJECT_ROOT / "k8s/observability/grafana/dashboards/operations-logs.json"

    datasources = yaml.safe_load(datasource_path.read_text())
    rules = yaml.safe_load(rules_path.read_text())
    dashboard = json.loads(dashboard_path.read_text())

    assert any(source["uid"] == "loki" for source in datasources["datasources"])
    assert len(rules["groups"][0]["rules"]) == 6
    assert {rule["uid"] for rule in rules["groups"][0]["rules"]} == {
        "task-api-unavailable",
        "task-api-high-error-rate",
        "task-api-high-latency",
        "task-api-rate-limit-spike",
        "task-backup-failed",
        "task-backup-missing",
    }
    assert dashboard["uid"] == "task-manager-logs"


def test_compose_socket_proxy_is_read_only_and_inbox_is_loopback_only():
    compose = yaml.safe_load((PROJECT_ROOT / "compose.yaml").read_text())
    services = compose["services"]

    proxy = services["docker-socket-proxy"]
    assert proxy["environment"]["POST"] == "0"
    assert proxy["environment"]["CONTAINERS"] == "1"
    assert proxy["networks"] == ["logging-control"]
    assert services["webhook-inbox"]["ports"] == ["127.0.0.1:8081:8080"]


def test_kubernetes_alloy_uses_namespace_scoped_rbac_without_host_mounts():
    documents = list(yaml.safe_load_all((PROJECT_ROOT / "k8s/logging.yaml").read_text()))
    role = next(document for document in documents if document["kind"] == "Role")
    alloy = next(
        document
        for document in documents
        if document["kind"] == "Deployment" and document["metadata"]["name"] == "alloy"
    )

    assert role["metadata"]["namespace"] == "task-manager"
    assert {resource for rule in role["rules"] for resource in rule["resources"]} == {
        "pods",
        "pods/log",
    }
    volumes = alloy["spec"]["template"]["spec"]["volumes"]
    assert all("hostPath" not in volume for volume in volumes)
