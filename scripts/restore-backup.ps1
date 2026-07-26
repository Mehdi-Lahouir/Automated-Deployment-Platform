param(
    [ValidateSet("compose", "kubernetes")]
    [string]$Environment = "compose",

    [ValidateSet("local", "s3")]
    [string]$Backend = "local",

    [string]$Snapshot = "latest",

    [string]$TargetDatabase = "tasks_restore_test",

    [switch]$ReplaceActiveDatabase
)

$ErrorActionPreference = "Stop"
$activeDatabase = "tasks"

if ($TargetDatabase -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
    throw "TargetDatabase may contain only letters, numbers, and underscores."
}

if ($ReplaceActiveDatabase) {
    $TargetDatabase = $activeDatabase
    $confirmation = Read-Host "Type RESTORE $activeDatabase to replace the active database"
    if ($confirmation -cne "RESTORE $activeDatabase") {
        throw "Active database restore cancelled."
    }
}
elseif ($TargetDatabase -eq $activeDatabase) {
    throw "Use -ReplaceActiveDatabase to restore over the active database."
}

function Invoke-Checked {
    param([scriptblock]$Command, [string]$FailureMessage)
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

if ($Environment -eq "compose") {
    $profile = "backup-$Backend"
    $service = "restore-$Backend"
    $previousSnapshot = $env:SNAPSHOT_ID
    $previousTarget = $env:RESTORE_TARGET_DB
    $previousAllow = $env:ALLOW_PRODUCTION_RESTORE
    $apiStopped = $false

    try {
        $env:SNAPSHOT_ID = $Snapshot
        $env:RESTORE_TARGET_DB = $TargetDatabase
        $env:ALLOW_PRODUCTION_RESTORE = $ReplaceActiveDatabase.ToString().ToLowerInvariant()

        if ($ReplaceActiveDatabase) {
            Invoke-Checked { docker compose stop api } "Could not stop the API before restore."
            $apiStopped = $true
        }

        Invoke-Checked {
            docker compose --profile $profile run --rm $service
        } "Compose restore verification failed."
    }
    finally {
        $env:SNAPSHOT_ID = $previousSnapshot
        $env:RESTORE_TARGET_DB = $previousTarget
        $env:ALLOW_PRODUCTION_RESTORE = $previousAllow
        if ($apiStopped) {
            docker compose up -d api
        }
    }
    exit 0
}

$cronJob = kubectl get cronjob postgres-restore-verification -n task-manager -o json |
    ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw "The postgres-restore-verification CronJob template is not deployed."
}
$deployedBackend = $cronJob.metadata.labels.'backup.task-manager/backend'
if ($deployedBackend -ne $Backend) {
    throw "The cluster is configured for '$deployedBackend' backups, not '$Backend'."
}

$jobName = "postgres-restore-$(Get-Date -Format 'yyyyMMddHHmmss')"
$job = kubectl create job $jobName `
    --from=cronjob/postgres-restore-verification `
    -n task-manager `
    --dry-run=client `
    -o json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw "Could not generate the Kubernetes restore Job."
}

$containerEnvironment = $job.spec.template.spec.containers[0].env
($containerEnvironment | Where-Object name -eq "SNAPSHOT_ID").value = $Snapshot
($containerEnvironment | Where-Object name -eq "RESTORE_TARGET_DB").value = $TargetDatabase
($containerEnvironment | Where-Object name -eq "ALLOW_PRODUCTION_RESTORE").value =
    $ReplaceActiveDatabase.ToString().ToLowerInvariant()

$replicas = 0
$apiStopped = $false
try {
    if ($ReplaceActiveDatabase) {
        $replicas = [int](kubectl get deployment task-api -n task-manager -o jsonpath='{.spec.replicas}')
        Invoke-Checked {
            kubectl scale deployment/task-api -n task-manager --replicas=0
        } "Could not stop the Kubernetes API deployment."
        $apiStopped = $true
    }

    $job | ConvertTo-Json -Depth 100 -Compress | kubectl apply -f -
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create the Kubernetes restore Job."
    }

    Invoke-Checked {
        kubectl wait --for=condition=complete "job/$jobName" -n task-manager --timeout=1800s
    } "The Kubernetes restore Job did not complete successfully."
}
finally {
    kubectl logs "job/$jobName" -n task-manager
    if ($apiStopped) {
        kubectl scale deployment/task-api -n task-manager --replicas=$replicas
        kubectl rollout status deployment/task-api -n task-manager --timeout=120s
    }
}

Write-Host "Restore Job $jobName completed and verified database $TargetDatabase."
