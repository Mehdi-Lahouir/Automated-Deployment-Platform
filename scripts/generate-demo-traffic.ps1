param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [ValidateRange(1, 500)]
    [int]$Requests = 25,
    [string]$ApiKey = $env:APP_API_KEY
)

$ErrorActionPreference = "Stop"
$BaseUrl = $BaseUrl.TrimEnd("/")

for ($index = 1; $index -le $Requests; $index++) {
    $requestId = "portfolio-demo-{0:D4}" -f $index
    $headers = @{"X-Request-ID" = $requestId}
    $path = "/health/live"
    if ($ApiKey) {
        $headers["X-API-Key"] = $ApiKey
        $path = if ($index % 5 -eq 0) { "/tasks/999999" } else { "/tasks" }
    }

    try {
        $response = Invoke-WebRequest `
            -Uri "$BaseUrl$path" `
            -Headers $headers `
            -Method Get `
            -UseBasicParsing
        Write-Host "$requestId -> $($response.StatusCode)"
    }
    catch {
        $statusCode = [int]$_.Exception.Response.StatusCode
        Write-Host "$requestId -> $statusCode"
    }
}

Write-Host "Generated $Requests safe requests. Search Grafana for request ID portfolio-demo-0001."
