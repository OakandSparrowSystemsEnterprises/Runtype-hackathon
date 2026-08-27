param(
    [int]$Width = 4,
    [string]$SnapshotId = "07fd77b8-7caf-400e-8e8e-42eb16396098",
    [string]$WslDistribution = "Ubuntu-24.04",
    [string]$TenkiCli = "/home/ankou/.local/bin/tenki",
    [string]$WorkerCommand = "python3 /home/tenki/gatekeeper-tenki/worker.py",
    [string[]]$ExistingSessionIds = @(),
    [int]$Retries = 5,
    [switch]$Sticky,
    [switch]$NoAutoDiscover
)

$ErrorActionPreference = "Stop"
if ($Width -lt 2 -or $Width -gt 16) {
    throw "Width must be between 2 and 16"
}
if ($ExistingSessionIds.Count -gt $Width) {
    throw "ExistingSessionIds cannot exceed requested Width"
}
if ($Retries -lt 1 -or $Retries -gt 8) {
    throw "Retries must be between 1 and 8"
}

function Invoke-Tenki([string[]]$Arguments) {
    $lastOutput = @()
    for ($attempt = 1; $attempt -le $Retries; $attempt++) {
        $previousPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $output = & wsl.exe -d $WslDistribution -- $TenkiCli @Arguments 2>&1
            $exitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $previousPreference
        }
        $lastOutput = @($output | ForEach-Object { "$_" })
        if ($exitCode -eq 0) {
            return $lastOutput
        }

        $joined = ($lastOutput -join "`n")
        $transient = (
            $joined -match 'write envelope: EOF' -or
            $joined -match 'unexpected EOF' -or
            $joined -match 'connection reset' -or
            $joined -match 'temporarily unavailable'
        )
        if (-not $transient -or $attempt -eq $Retries) {
            throw "Tenki command failed after $attempt attempt(s): $($Arguments -join ' ')`n$joined"
        }

        $delayMs = 500 * $attempt
        Write-Host "Tenki transport retry $attempt/$Retries after transient failure..."
        Start-Sleep -Milliseconds $delayMs
    }
    throw "Tenki command failed: $($Arguments -join ' ')`n$($lastOutput -join "`n")"
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

function Get-PropertyValue($Object, [string[]]$Names) {
    foreach ($name in $Names) {
        $property = $Object.PSObject.Properties[$name]
        if ($property -and $null -ne $property.Value -and "$($property.Value)" -ne "") {
            return $property.Value
        }
    }
    return $null
}

function Discover-TenkiSessions {
    $lines = Invoke-Tenki @("sandbox", "list", "--json")
    $raw = ($lines -join "`n").Trim()
    if (-not $raw) { return @() }
    try {
        $parsed = $raw | ConvertFrom-Json
    } catch {
        Write-Host "Tenki session auto-discovery could not parse list JSON; continuing without discovery."
        return @()
    }

    $items = @()
    if ($parsed -is [System.Array]) {
        $items = @($parsed)
    } else {
        foreach ($containerName in @("sessions", "items", "data")) {
            $candidate = $parsed.PSObject.Properties[$containerName]
            if ($candidate -and $candidate.Value) {
                $items = @($candidate.Value)
                break
            }
        }
        if ($items.Count -eq 0) { $items = @($parsed) }
    }

    $sessionMatches = New-Object System.Collections.ArrayList
    foreach ($item in $items) {
        $id = Get-PropertyValue $item @("session_id", "sessionId", "id")
        $name = Get-PropertyValue $item @("name", "session_name", "sessionName")
        $status = Get-PropertyValue $item @("status", "state")
        $nameText = if ($name) { "$name" } else { "" }
        $statusText = if ($status) { "$status".ToUpperInvariant() } else { "" }
        $active = (-not $statusText) -or $statusText -in @("RUNNING", "ACTIVE", "READY")
        if ($id -and $active -and $nameText -match '^gatekeeper-goi') {
            [void]$sessionMatches.Add([pscustomobject]@{
                id = "$id"
                name = $nameText
                status = $statusText
            })
        }
    }
    return @($sessionMatches | Sort-Object name, id)
}

function Test-DeriveEndpoint([string]$DeriveUrl) {
    $probe = @{
        artifact_ref = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        artifact_sha256 = "0000000000000000000000000000000000000000000000000000000000000000"
        requested_effect = "parent-shield.navigation"
        principal = "agent-b"
    } | ConvertTo-Json -Compress
    try {
        $response = Invoke-RestMethod -Uri $DeriveUrl -Method Post -ContentType "application/json" -Body $probe -TimeoutSec 4
        return ($response.ok -eq $true -and $response.claim.authority -eq $false)
    } catch {
        return $false
    }
}

function Get-DeriveUrl([string]$SessionId) {
    $preview = Extract-PreviewUrl (
        Invoke-Tenki @("sandbox", "expose", "--session", $SessionId, "--port", "8080")
    )
    return "$preview/derive"
}

if (-not $NoAutoDiscover -and $ExistingSessionIds.Count -lt $Width) {
    $discovered = @(Discover-TenkiSessions)
    $known = New-Object 'System.Collections.Generic.HashSet[string]'
    foreach ($id in $ExistingSessionIds) { [void]$known.Add($id) }
    foreach ($session in $discovered) {
        if ($ExistingSessionIds.Count -ge $Width) { break }
        if ($known.Add($session.id)) {
            Write-Host "Auto-discovered active Tenki worker: $($session.name) [$($session.id)]"
            $ExistingSessionIds += $session.id
        }
    }
    Write-Host "Tenki auto-discovery adopted $($ExistingSessionIds.Count) active worker(s)."
}

$workers = @()
for ($index = 0; $index -lt $Width; $index++) {
    $adopted = $index -lt $ExistingSessionIds.Count
    if ($adopted) {
        $sessionId = $ExistingSessionIds[$index]
        Write-Host "Adopting existing Tenki replica $index/$($Width - 1): $sessionId"
    } else {
        $name = "gatekeeper-goi-swarm-$('{0:d2}' -f $index)"
        Write-Host "Launching Tenki replica $index/$($Width - 1)..."
        $createArgs = @(
            "sandbox", "create",
            "--snapshot", $SnapshotId,
            "--name", $name,
            "--metadata", "oasse_role=goi-replica",
            "--metadata", "oasse_replica=$index"
        )
        if ($Sticky) { $createArgs += "--sticky" }
        $sessionId = Extract-SessionId (Invoke-Tenki $createArgs)
    }

    $deriveUrl = Get-DeriveUrl $sessionId
    $workerReady = Test-DeriveEndpoint $deriveUrl

    if (-not $workerReady) {
        Write-Host "Replica $index is not serving /derive yet; starting worker..."
        $shell = "nohup $WorkerCommand >/home/tenki/gatekeeper-tenki/worker-$index.log 2>&1 </dev/null &"
        try {
            Invoke-Tenki @("sandbox", "exec", "--session", $sessionId, "-c", $shell) | Out-Null
        } catch {
            Write-Host "Tenki exec failed for replica $index; re-probing exposed worker before giving up."
        }
        Start-Sleep -Seconds 1
        $workerReady = Test-DeriveEndpoint $deriveUrl
    }

    if (-not $workerReady) {
        throw "Tenki replica $index [$sessionId] exists but /derive is not reachable after restore/start attempts"
    }

    Write-Host "Tenki replica $index LIVE: $sessionId"
    $workers += [ordered]@{
        replica_index = $index
        session_id = $sessionId
        adopted_existing = $adopted
        derive_url = $deriveUrl
        snapshot_id = $SnapshotId
        authority = $false
        live = $true
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
    adopted_existing = $ExistingSessionIds.Count
    created_new = $Width - $ExistingSessionIds.Count
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
