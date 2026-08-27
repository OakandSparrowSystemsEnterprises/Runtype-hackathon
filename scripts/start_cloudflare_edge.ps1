param(
    [int]$LocalPort = 8080,
    [string]$CloudflaredPath = "",
    [int]$TimeoutSeconds = 45
)

# Puts a real Cloudflare-operated edge (quick tunnel, *.trycloudflare.com) in
# front of the local nginx public edge. Honest boundary: this is Cloudflare's
# free quick-tunnel tier - a genuine Cloudflare service in the request path,
# reported as mode=quick-tunnel, not represented as a named production tunnel.

$ErrorActionPreference = "Stop"

function Emit([hashtable]$Payload) {
    ($Payload | ConvertTo-Json -Compress)
}

if ([string]::IsNullOrWhiteSpace($CloudflaredPath)) {
    $command = Get-Command "cloudflared" -ErrorAction SilentlyContinue
    if ($command) { $CloudflaredPath = $command.Source }
}

if ([string]::IsNullOrWhiteSpace($CloudflaredPath) -or -not (Test-Path $CloudflaredPath)) {
    Emit @{ stage = "cloudflare_edge"; status = "FAIL"; reason = "cloudflared not found on PATH"; install = "winget install --id Cloudflare.cloudflared" }
    exit 1
}

$logPath = Join-Path $env:TEMP ("cloudflared-edge-" + [guid]::NewGuid().ToString("n") + ".log")
$arguments = "tunnel --url http://127.0.0.1:$LocalPort --no-autoupdate"

$process = Start-Process -FilePath $CloudflaredPath -ArgumentList $arguments `
    -RedirectStandardError $logPath -RedirectStandardOutput ($logPath + ".out") `
    -PassThru -WindowStyle Hidden

Emit @{ stage = "cloudflare_edge"; status = "STARTING"; local_port = $LocalPort; pid = $process.Id; log = $logPath }

$publicUrl = $null
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 800
    if ($process.HasExited) { break }
    foreach ($file in @($logPath, ($logPath + ".out"))) {
        if (Test-Path $file) {
            $match = [regex]::Match((Get-Content $file -Raw), "https://[a-z0-9-]+\.trycloudflare\.com")
            if ($match.Success) { $publicUrl = $match.Value; break }
        }
    }
    if ($publicUrl) { break }
}

if (-not $publicUrl) {
    $detail = ""
    if (Test-Path $logPath) { $detail = ((Get-Content $logPath -Tail 5) -join " | ") }
    Emit @{ stage = "cloudflare_edge"; status = "FAIL"; reason = "no trycloudflare URL within $TimeoutSeconds s"; process_exited = $process.HasExited; log_tail = $detail }
    exit 1
}

$env:CLOUDFLARE_PUBLIC_EDGE = $publicUrl

# Prove Cloudflare is actually in the path: the response must carry a cf-ray id.
$cfRay = $null
$healthStatus = $null
try {
    $response = Invoke-WebRequest -Uri ($publicUrl + "/") -UseBasicParsing -TimeoutSec 20
    $healthStatus = [int]$response.StatusCode
    $cfRay = $response.Headers["cf-ray"]
} catch {
    $healthStatus = -1
}

$inPath = -not [string]::IsNullOrWhiteSpace($cfRay)
$status = "READY"
if (-not $inPath) { $status = "PARTIAL" }

Emit @{
    stage = "CLOUDFLARE_EDGE"
    status = $status
    mode = "quick-tunnel"
    public_url = $publicUrl
    arena = ($publicUrl + "/")
    upstream = "http://127.0.0.1:$LocalPort"
    edge_probe_status = $healthStatus
    cf_ray = $cfRay
    cloudflare_in_path = $inPath
    pid = $process.Id
    stop_hint = "Stop-Process -Id $($process.Id)"
}

if ($inPath) {
    Write-Host "Cloudflare edge live: $publicUrl (cf-ray $cfRay). Open the Arena through this URL so the CLOUDFLARE EDGE chip flips from runtime evidence."
} else {
    Write-Host "Tunnel URL allocated but the probe saw no cf-ray header yet; retry the probe or open $publicUrl in a browser."
}
