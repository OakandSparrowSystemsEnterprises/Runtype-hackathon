param(
    [int]$Width = 4,
    [string]$SnapshotId = "07fd77b8-7caf-400e-8e8e-42eb16396098",
    [string]$ImageRef = $env:TENKI_IMAGE_REF,
    [string]$WslDistribution = "Ubuntu-24.04",
    [string]$TenkiCli = "/home/ankou/.local/bin/tenki",
    [string]$WorkerCommand = "python3 /home/tenki/gatekeeper-tenki/worker.py",
    [string[]]$ExistingSessionIds = @(),
    [int]$Retries = 3,
    [switch]$Sticky,
    [switch]$NoAutoDiscover,
    [switch]$InsecureTls
)

$ErrorActionPreference = "Stop"
if ($Width -lt 2 -or $Width -gt 16) { throw "Width must be between 2 and 16" }
if ($ExistingSessionIds.Count -gt $Width) { throw "ExistingSessionIds cannot exceed requested Width" }

$ImageMode = -not [string]::IsNullOrWhiteSpace($ImageRef)
$SessionPrefix = $(if ($ImageMode) { "gatekeeper-goi-image-swarm" } else { "gatekeeper-goi-swarm" })

if ($InsecureTls) {
    # Opt-in escape hatch for networks that TLS-intercept *.sb.tenki.sh.
    # Evidence-plane only: claims stay non-authoritative and content-bound.
    [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
    $env:TENKI_TLS_INSECURE = "1"
    Write-Host "WARNING: TLS verification relaxed for Tenki evidence probes (surfaced in results)."
}

function Invoke-Tenki([string[]]$Arguments, [switch]$FailForward) {
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
        if ($exitCode -eq 0) { return $lastOutput }
        $joined = ($lastOutput -join "`n")
        $transient = $joined -match 'write envelope: EOF|unexpected EOF|connection reset|temporarily unavailable'
        if (-not $transient -or $attempt -eq $Retries) {
            if ($FailForward) { return @($lastOutput) }
            throw "Tenki command failed after $attempt attempt(s): $($Arguments -join ' ')`n$joined"
        }
        Start-Sleep -Milliseconds (350 * $attempt)
    }
    if ($FailForward) { return @($lastOutput) }
    throw "Tenki command failed: $($Arguments -join ' ')"
}

function Extract-SessionId([string[]]$Lines) {
    $match = [regex]::Match(($Lines -join "`n"), '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
    if (-not $match.Success) { throw "Could not parse Tenki session id from create output" }
    return $match.Value
}

function Extract-PreviewUrl([string[]]$Lines) {
    $match = [regex]::Match(($Lines -join "`n"), 'https://[^\s"''<>]+')
    if (-not $match.Success) { return $null }
    return $match.Value.TrimEnd('/')
}

function Get-PropertyValue($Object, [string[]]$Names) {
    foreach ($name in $Names) {
        $property = $Object.PSObject.Properties[$name]
        if ($property -and $null -ne $property.Value -and "$($property.Value)" -ne "") { return $property.Value }
    }
    return $null
}

function Discover-TenkiSessions {
    $raw = ((Invoke-Tenki @("sandbox", "list", "--json")) -join "`n").Trim()
    if (-not $raw) { return @() }
    try { $parsed = $raw | ConvertFrom-Json } catch { return @() }
    $items = @()
    if ($parsed -is [System.Array]) { $items = @($parsed) }
    else {
        foreach ($containerName in @("sessions", "items", "data")) {
            $candidate = $parsed.PSObject.Properties[$containerName]
            if ($candidate -and $candidate.Value) { $items = @($candidate.Value); break }
        }
        if ($items.Count -eq 0) { $items = @($parsed) }
    }
    $found = New-Object System.Collections.ArrayList
    foreach ($item in $items) {
        $id = Get-PropertyValue $item @("session_id", "sessionId", "id")
        $name = Get-PropertyValue $item @("name", "session_name", "sessionName")
        $status = Get-PropertyValue $item @("status", "state")
        $nameText = if ($name) { "$name" } else { "" }
        $statusText = if ($status) { "$status".ToUpperInvariant() } else { "" }
        $active = (-not $statusText) -or $statusText -in @("RUNNING", "ACTIVE", "READY")
        if ($id -and $active -and $nameText -match "^$([regex]::Escape($SessionPrefix))") {
            [void]$found.Add([pscustomobject]@{ id = "$id"; name = $nameText })
        }
    }
    return @($found | Sort-Object name, id)
}

function Test-DeriveEndpoint([string]$DeriveUrl) {
    if (-not $DeriveUrl) { return $false }
    $probe = @{
        artifact_ref = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        artifact_sha256 = "0000000000000000000000000000000000000000000000000000000000000000"
        requested_effect = "parent-shield.navigation"
        principal = "agent-b"
    } | ConvertTo-Json -Compress
    try {
        $response = Invoke-RestMethod -Uri $DeriveUrl -Method Post -ContentType "application/json" -Body $probe -TimeoutSec 3
        return ($response.ok -eq $true -and $response.claim.authority -eq $false)
    } catch { return $false }
}

if (-not $NoAutoDiscover -and $ExistingSessionIds.Count -lt $Width) {
    $known = New-Object 'System.Collections.Generic.HashSet[string]'
    foreach ($id in $ExistingSessionIds) { [void]$known.Add($id) }
    foreach ($session in @(Discover-TenkiSessions)) {
        if ($ExistingSessionIds.Count -ge $Width) { break }
        if ($known.Add($session.id)) {
            Write-Host "Auto-discovered Tenki worker: $($session.name) [$($session.id)]"
            $ExistingSessionIds += $session.id
        }
    }
}

$sessionPool = New-Object System.Collections.ArrayList
for ($index = 0; $index -lt $Width; $index++) {
    if ($index -lt $ExistingSessionIds.Count) {
        [void]$sessionPool.Add([pscustomobject]@{ index = $index; session_id = $ExistingSessionIds[$index]; adopted = $true })
        continue
    }
    $name = "$SessionPrefix-$('{0:d2}' -f $index)"
    Write-Host "Creating Tenki replica $index/$($Width - 1) from $(if ($ImageMode) { 'published image' } else { 'snapshot' })..."
    if ($ImageMode) {
        $args = @("sandbox", "create", "--image", $ImageRef, "--name", $name, "--metadata", "oasse_role=goi-replica", "--metadata", "oasse_replica=$index")
    } else {
        $args = @("sandbox", "create", "--snapshot", $SnapshotId, "--name", $name, "--metadata", "oasse_role=goi-replica", "--metadata", "oasse_replica=$index")
    }
    if ($Sticky) { $args += "--sticky" }
    $sessionId = Extract-SessionId (Invoke-Tenki $args)
    [void]$sessionPool.Add([pscustomobject]@{ index = $index; session_id = $sessionId; adopted = $false })
}
Write-Host "Tenki session pool ready: $($sessionPool.Count)/$Width sessions."

$workers = New-Object System.Collections.ArrayList
foreach ($session in $sessionPool) {
    $index = [int]$session.index
    $sessionId = "$($session.session_id)"
    Write-Host "Preparing Tenki replica $index/$($Width - 1): $sessionId"

    $preview = Extract-PreviewUrl (Invoke-Tenki @("sandbox", "expose", "--session", $sessionId, "--port", "8080") -FailForward)
    $deriveUrl = if ($preview) { "$preview/derive" } else { $null }

    if ($ImageMode) {
        $live = $false
        for ($probeAttempt = 1; $probeAttempt -le 8; $probeAttempt++) {
            if (Test-DeriveEndpoint $deriveUrl) { $live = $true; break }
            Start-Sleep -Milliseconds 750
        }
        $startAttempted = $false
    } else {
        $live = Test-DeriveEndpoint $deriveUrl
        $startAttempted = $false
        if (-not $live) {
            $startAttempted = $true
            $shell = "nohup $WorkerCommand >/home/tenki/gatekeeper-tenki/worker-$index.log 2>&1 </dev/null &"
            Invoke-Tenki @("sandbox", "exec", "--session", $sessionId, "-c", $shell) -FailForward | Out-Null
            Start-Sleep -Milliseconds 600
            $live = Test-DeriveEndpoint $deriveUrl
        }
    }

    [void]$workers.Add([ordered]@{
        replica_index = $index
        session_id = $sessionId
        adopted_existing = [bool]$session.adopted
        derive_url = $deriveUrl
        source = $(if ($ImageMode) { "published_template_image" } else { "snapshot" })
        image_ref = $(if ($ImageMode) { $ImageRef } else { $null })
        snapshot_id = $(if ($ImageMode) { $null } else { $SnapshotId })
        authority = $false
        live = [bool]$live
        start_attempted = $startAttempted
    })
    Write-Host "Replica $index status: $(if ($live) { 'LIVE' } else { 'PENDING' })"
}

$liveWorkers = @($workers | Where-Object { $_.live -eq $true -and $_.derive_url })
$env:TENKI_SWARM_WIDTH = [string]$Width
if ($ImageMode) { $env:TENKI_IMAGE_REF = $ImageRef }
if ($liveWorkers.Count -gt 0) {
    $env:TENKI_DERIVE_URLS = (($liveWorkers | ForEach-Object { $_.derive_url }) -join ',')
    $env:TENKI_DERIVE_URL = $liveWorkers[0].derive_url
} else {
    Remove-Item Env:TENKI_DERIVE_URLS -ErrorAction SilentlyContinue
    Remove-Item Env:TENKI_DERIVE_URL -ErrorAction SilentlyContinue
}

$result = [ordered]@{
    status = $(if ($liveWorkers.Count -eq $Width) { "READY_FOR_LIVE_PROOF" } else { "PARTIAL" })
    platform = "Tenki"
    launch_mode = $(if ($ImageMode) { "published_template_image" } else { "snapshot" })
    image_ref = $(if ($ImageMode) { $ImageRef } else { $null })
    snapshot_id = $(if ($ImageMode) { $null } else { $SnapshotId })
    replica_width = $Width
    session_pool = $sessionPool.Count
    live_replicas = $liveWorkers.Count
    authority = $false
    tls_verification_relaxed = [bool]$InsecureTls
    sessions = $workers
    env = [ordered]@{
        TENKI_SWARM_WIDTH = $env:TENKI_SWARM_WIDTH
        TENKI_DERIVE_URLS_configured = ($liveWorkers.Count -gt 0)
    }
}
$result | ConvertTo-Json -Depth 6

Write-Host "Tenki pool complete: $($liveWorkers.Count)/$Width live replicas."
if ($liveWorkers.Count -gt 0) { Write-Host "Live endpoints exported in this PowerShell session." }
