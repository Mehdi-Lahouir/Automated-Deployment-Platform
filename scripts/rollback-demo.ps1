$ErrorActionPreference = "Stop"

kubectl set image deployment/task-api api=task-manager:broken -n task-manager
kubectl rollout status deployment/task-api -n task-manager --timeout=30s
if ($LASTEXITCODE -ne 0) {
    Write-Host "The broken release failed as expected. Rolling back..."
    kubectl rollout undo deployment/task-api -n task-manager
    kubectl rollout status deployment/task-api -n task-manager --timeout=120s
}

