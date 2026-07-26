$ErrorActionPreference = "Stop"

if (-not (Get-Command kind -ErrorAction SilentlyContinue)) {
    throw "kind is not installed. See https://kind.sigs.k8s.io/docs/user/quick-start/"
}

if (-not (kind get clusters | Select-String -SimpleMatch "task-manager")) {
    kind create cluster --name task-manager --config kind-config.yaml
}

docker build -t task-manager:local .
kind load docker-image task-manager:local --name task-manager
kubectl apply -k k8s
kubectl rollout status deployment/postgres -n task-manager --timeout=120s
kubectl rollout status deployment/task-api -n task-manager --timeout=120s

Write-Host "API: run kubectl port-forward service/task-api 8000:8000 -n task-manager"
Write-Host "Grafana: run kubectl port-forward service/grafana 3000:3000 -n task-manager"

