param(
    [ValidateSet("compose", "kubernetes")]
    [string]$Environment = "compose",

    [ValidateSet("local", "s3")]
    [string]$Backend = "local"
)

$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param([scriptblock]$Command, [string]$FailureMessage)
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

if ($Environment -eq "compose") {
    $profile = "backup-$Backend"
    $service = "backup-$Backend"
    Invoke-Checked {
        docker compose --profile $profile run --rm $service
    } "Compose backup failed."
    exit 0
}

$cronJob = kubectl get cronjob postgres-backup -n task-manager -o json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw "The postgres-backup CronJob is not deployed."
}
$deployedBackend = $cronJob.metadata.labels.'backup.task-manager/backend'
if ($deployedBackend -ne $Backend) {
    throw "The cluster is configured for '$deployedBackend' backups, not '$Backend'."
}

$jobName = "postgres-backup-manual-$(Get-Date -Format 'yyyyMMddHHmmss')"
Invoke-Checked {
    kubectl create job $jobName --from=cronjob/postgres-backup -n task-manager
} "Could not create the manual Kubernetes backup Job."

try {
    Invoke-Checked {
        kubectl wait --for=condition=complete "job/$jobName" -n task-manager --timeout=1800s
    } "The Kubernetes backup Job did not complete successfully."
}
finally {
    kubectl logs "job/$jobName" -n task-manager
}

Write-Host "Backup Job $jobName completed. It is retained temporarily for inspection."
