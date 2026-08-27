param(
    [int]$Width = 4,
    [string]$SnapshotId = "07fd77b8-7caf-400e-8e8e-42eb16396098",
    [string]$WslDistribution = "Ubuntu-24.04",
    [string]$TenkiCli = "/home/ankou/.local/bin/tenki",
    [string]$WorkerCommand = "python3 /home/tenki/gatekeeper-tenki/worker.py",
    [switch]$Sticky
)

$ErrorActionPreference = "Stop"
if ($Width -lt 2 -or $Width -gt 16) {
    throw "Width must be between 2 and 16"
}

function Invoke-Tenki([string[]]$Arguments) {
    $output = & wsl.exe -d $WslDistribution -- $TenkiCli @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Tenki command failed: $($Arguments -join ' ')`n$($output -join "`n")"
    }
    return @($output)
}

function Extract-SessionId([string[]]$Lines) {
    $joined = ($Lines -join "`n")
    $match = [regex]::Match($joined, '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
    if (-not $match.Success) {
        throw "Could not parse Tenki session id from create output"
    }
    return $match.Value
}

function Extract-PreviewUrl([string[]]$Lines) {
    $joined = ($Lines -join "`n")
    $match = [regex]::Match($joined, 'https://[^\s"''<>]+')
    if (-not $match.Success) {
        throw "Could not parse Tenki preview URL from expose output"
    }
    return $match.Value.TrimEnd('/')
}

$workers = @()
for ($index = 0; $index -lt $Width; $index++) {
    $name = "gatekeeper-goi-swarm-$('{0:d2}' -f $index)"
    $createArgs = @(
        "sandbox", "create",
        "--snapshot", $SnapshotId,
        "--name", $name,
        "--metadata", "oasse_role=goi-replica",
        "--metadata", "oasse_replica=$index"
    )
    if ($Sticky) {
        $createArgs += "--sticky"
    }

    Write-Host "Launching Tenki replica $index/$($Width - 1)..."
    $sessionId = Extract-SessionId (Invoke-Tenki $createArgs)

    $shell = "nohup $WorkerCommand >/home/tenki/gatekeeper-tenki/worker-$index.log 2>&1 </dev/null &"
    Invoke-Tenki @("sandbox", "exec", "--session", $sessionId, "-c", $shell) | Out-Null
    Start-Sleep -Milliseconds 500

    $preview = Extract-PreviewUrl (
        Invoke-Tenki @("sandbox", "expose", "--session", $sessionId, "--port", "8080")
    )
    $deriveUrl = "$preview/derive"

    $workers += [ordered]@{
        replica_index = $index
        session_id = $sessionId
        preview_url = $preview
        derive_url = $deriveUrl
        snapshot_id = $SnapshotId
        authority = $false
    }
}

$env:TENKI_DERIVE_URLS = (($workers | ForEach-Object { $_.derive_url }) -join ',')
$env:TENKI_DERIVE_URL = $workers[0].derive_url
$env:TENKI_SWARM_WIDTH = [string]$Width

$result = [ordered]@{
    status = "READY_FOR_LIVE_PROOF"
    platform = "Tenki"
    snapshot_id = $SnapshotId
    replica_width = $Width
    authority = $false
    sessions = $workers
    env = [ordered]@{
        TENKI_SWARM_WIDTH = $env:TENKI_SWARM_WIDTH
        TENKI_DERIVE_URLS_configured = $true
        TENKI_DERIVE_URL_compatibility_pointer = $true
    }
}
$result | ConvertTo-Json -Depth 6

Write-Host "Tenki swarm environment is configured in this PowerShell session."
Write-Host "Next: .\scripts\start_day2.ps1 -Restart -GenerateDemoKeys -RunSteward"
