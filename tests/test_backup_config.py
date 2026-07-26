from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_yaml_documents(relative_path: str):
    path = PROJECT_ROOT / relative_path
    return [document for document in yaml.safe_load_all(path.read_text()) if document]


def test_compose_defines_local_and_s3_backup_profiles():
    compose = load_yaml_documents("compose.yaml")[0]
    services = compose["services"]

    assert services["backup-local-init"]["cap_add"] == ["CHOWN", "FOWNER"]
    assert services["backup-local"]["profiles"] == ["backup-local"]
    assert (
        services["backup-local"]["depends_on"]["backup-local-init"]["condition"]
        == "service_completed_successfully"
    )
    assert services["restore-local"]["environment"]["MODE"] == "restore"
    assert services["backup-s3"]["profiles"] == ["backup-s3"]
    assert services["backup-s3"]["environment"]["RESTIC_REPOSITORY"].startswith("s3:")
    assert services["minio"]["ports"] == [
        "127.0.0.1:9000:9000",
        "127.0.0.1:9001:9001",
    ]


def test_backup_retention_and_restore_safety_are_configured():
    backup_script = (PROJECT_ROOT / "backup/run-backup.sh").read_text()
    restore_script = (PROJECT_ROOT / "backup/run-restore.sh").read_text()
    entrypoint = (PROJECT_ROOT / "backup/entrypoint.sh").read_text()

    assert "--keep-daily=7" in backup_script
    assert "--keep-weekly=4" in backup_script
    assert "--keep-monthly=3" in backup_script
    assert "restic check --read-data" in backup_script
    assert "require_variable AWS_ACCESS_KEY_ID" in entrypoint
    assert "require_variable AWS_SECRET_ACCESS_KEY" in entrypoint
    assert "backup_started" in backup_script
    assert "backup_completed" in backup_script
    assert "backup_failed" in backup_script
    assert "restore_started" in restore_script
    assert "restore_verified" in restore_script
    assert "restore_failed" in restore_script
    assert "ALLOW_PRODUCTION_RESTORE:-false" in restore_script
    assert "tasks_restore_test" in restore_script


def test_kubernetes_has_scheduled_and_suspended_backup_jobs():
    documents = load_yaml_documents("k8s/backup.yaml")
    cron_jobs = {
        document["metadata"]["name"]: document
        for document in documents
        if document["kind"] == "CronJob"
    }

    backup = cron_jobs["postgres-backup"]
    restore = cron_jobs["postgres-restore-verification"]
    assert backup["spec"]["schedule"] == "0 2 * * *"
    assert backup["spec"]["concurrencyPolicy"] == "Forbid"
    assert restore["spec"]["suspend"] is True
    assert restore["spec"]["jobTemplate"]["spec"]["backoffLimit"] == 0


def test_s3_overlay_uses_minio_and_encrypted_restic_repository():
    patch_documents = load_yaml_documents("k8s-overlays/backup-s3/backup-s3-patch.yaml")
    repositories = []
    for document in patch_documents:
        environment = document["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0][
            "env"
        ]
        repositories.extend(
            variable["value"] for variable in environment if variable["name"] == "RESTIC_REPOSITORY"
        )

    assert repositories == [
        "s3:http://minio:9000/task-manager-backups",
        "s3:http://minio:9000/task-manager-backups",
    ]
