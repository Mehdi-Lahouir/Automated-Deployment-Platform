param(
    [ValidateSet("compose", "kubernetes")]
    [string]$Environment = "compose",

    [ValidateSet("trigger", "recover", "check")]
    [string]$Action = "check"
)

$ErrorActionPreference = "Stop"
$sessionId = "11111111-2222-3333-4444-555555555555"

function Invoke-Checked {
    param([scriptblock]$Command, [string]$FailureMessage)
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

if ($Action -eq "trigger") {
    if ($Environment -eq "compose") {
        Invoke-Checked { docker compose stop api } "Could not stop the Compose API."
    }
    else {
        Invoke-Checked {
            kubectl scale deployment/task-api -n task-manager --replicas=0
        } "Could not scale down the Kubernetes API."
    }
    Write-Host "API stopped. The availability alert waits two minutes, then Grafana groups for up to 10 seconds."
    exit 0
}

if ($Action -eq "recover") {
    if ($Environment -eq "compose") {
        Invoke-Checked { docker compose up -d api } "Could not restart the Compose API."
    }
    else {
        Invoke-Checked {
            kubectl scale deployment/task-api -n task-manager --replicas=2
        } "Could not scale up the Kubernetes API."
        Invoke-Checked {
            kubectl rollout status deployment/task-api -n task-manager --timeout=120s
        } "The Kubernetes API did not become ready."
    }
    Write-Host "API recovered. Grafana will send a resolved notification."
    exit 0
}

if ($Environment -eq "compose") {
    $inboxLogs = docker compose logs --no-color webhook-inbox
    if ($LASTEXITCODE -ne 0) {
        throw "Could not read webhook inbox logs."
    }
    $ui = "http://127.0.0.1:8081/s/$sessionId"
}
else {
    $inboxLogs = kubectl logs deployment/webhook-inbox -n task-manager
    if ($LASTEXITCODE -ne 0) {
        throw "Could not read Kubernetes webhook inbox logs."
    }
    $ui = "Run kubectl port-forward service/webhook-inbox 8081:8080 -n task-manager, then open http://127.0.0.1:8081/s/$sessionId"
}

if ($inboxLogs -match "$sessionId|grafana") {
    Write-Host "A Grafana webhook delivery is present in the local inbox logs."
}
else {
    Write-Host "No Grafana delivery found yet. Wait for the alert evaluation and run this check again."
}
Write-Host "Inbox: $ui"
