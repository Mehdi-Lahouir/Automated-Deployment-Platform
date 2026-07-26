param(
    [ValidateSet("local", "s3")]
    [string]$BackupBackend = "local"
)

$ErrorActionPreference = "Stop"

$appSecretsFile = "k8s/app-secrets.env"
$monitoringSecretsFile = "k8s/monitoring-secrets.env"
$backupSecretsFile = "k8s/backup-secrets.env"

if (-not (Test-Path -LiteralPath $appSecretsFile)) {
    throw "Create $appSecretsFile from k8s/app-secrets.env.example and replace every placeholder."
}
if (-not (Test-Path -LiteralPath $monitoringSecretsFile)) {
    throw "Create $monitoringSecretsFile from k8s/monitoring-secrets.env.example and replace every placeholder."
}
if (-not (Test-Path -LiteralPath $backupSecretsFile)) {
    throw "Create $backupSecretsFile from k8s/backup-secrets.env.example and replace every placeholder."
}
if (
    (Select-String -LiteralPath $appSecretsFile -SimpleMatch "replace-with" -Quiet) -or
    (Select-String -LiteralPath $monitoringSecretsFile -SimpleMatch "replace-with" -Quiet) -or
    (Select-String -LiteralPath $backupSecretsFile -SimpleMatch "replace-with" -Quiet)
) {
    throw "Secret files still contain placeholder values. Generate strong secrets before deploying."
}

if (-not (Get-Command kind -ErrorAction SilentlyContinue)) {
    throw "kind is not installed. See https://kind.sigs.k8s.io/docs/user/quick-start/"
}

if (-not (kind get clusters | Select-String -SimpleMatch "task-manager")) {
    kind create cluster --name task-manager --config kind-config.yaml
}

docker build -t task-manager:local .
docker build -t backup-agent:local -f backup/Dockerfile .
kind load docker-image task-manager:local --name task-manager
kind load docker-image backup-agent:local --name task-manager
kubectl apply -f k8s/namespace.yaml
kubectl create secret generic app-secrets `
    --namespace task-manager `
    --from-env-file=$appSecretsFile `
    --dry-run=client `
    -o yaml | kubectl apply -f -
kubectl create secret generic monitoring-secrets `
    --namespace task-manager `
    --from-env-file=$monitoringSecretsFile `
    --dry-run=client `
    -o yaml | kubectl apply -f -
kubectl create secret generic backup-secrets `
    --namespace task-manager `
    --from-env-file=$backupSecretsFile `
    --dry-run=client `
    -o yaml | kubectl apply -f -

$kustomizePath = if ($BackupBackend -eq "s3") {
    "k8s-overlays/backup-s3"
}
else {
    "k8s"
}
kubectl apply -k $kustomizePath
kubectl rollout status deployment/postgres -n task-manager --timeout=120s
kubectl rollout status deployment/task-api -n task-manager --timeout=120s
kubectl rollout status deployment/loki -n task-manager --timeout=120s
kubectl rollout status deployment/alloy -n task-manager --timeout=120s
kubectl rollout status deployment/webhook-inbox -n task-manager --timeout=120s
if ($BackupBackend -eq "s3") {
    kubectl rollout status deployment/minio -n task-manager --timeout=120s
    kubectl wait --for=condition=complete job/minio-bucket-init -n task-manager --timeout=120s
}

Write-Host "API: run kubectl port-forward service/task-api 8000:8000 -n task-manager"
Write-Host "Grafana: run kubectl port-forward service/grafana 3000:3000 -n task-manager"
Write-Host "Alert inbox: run kubectl port-forward service/webhook-inbox 8081:8080 -n task-manager"
Write-Host "Backups: .\scripts\backup.ps1 -Environment kubernetes -Backend $BackupBackend"
