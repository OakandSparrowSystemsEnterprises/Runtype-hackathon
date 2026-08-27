param(
    [switch]$Restart,
    [switch]$GenerateDemoKeys,
    [switch]$SkipPublicEdge,
    [switch]$RunGate0
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

function Write-State([string]$stage, [string]$status, [hashtable]$detail = @{}) {
    $body = [ordered]@{ stage = $stage; status = $status }
    foreach ($key in $detail.Keys) { $body[$key] = $detail[$key] }
    $body | ConvertTo-Json -Compress
}

function New-DemoSecret {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    return ([System.BitConverter]::ToString($bytes) -replace '-', '').ToLowerInvariant()
}

function Require-Command([string]$name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "required command not found: $name"
    }
}

function Get-Listener([int]$port) {
    Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -First 1
}

function Stop-Listener([int]$port) {
    $listener = Get-Listener $port
    if ($listener) {
        Stop-Process -Id $listener.OwningProcess -Force
        Start-Sleep -Milliseconds 250
    }
}

function Wait-JsonHealth([string]$url, [int]$seconds = 10) {
    $deadline = (Get-Date).AddSeconds($seconds)
    do {
        try {
            return Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 2
        } catch {
            Start-Sleep -Milliseconds 250
        }
    } while ((Get-Date) -lt $deadline)
    throw "health check did not become ready: $url"
}

Require-Command python

if (-not $env:GATEKEEPER_V2_SOURCE_ROOT) {
    throw "GATEKEEPER_V2_SOURCE_ROOT must point at the source-of-truth Gatekeeper-V2-NPU checkout"
}

if ($GenerateDemoKeys) {
    $agentA = New-DemoSecret
    $agentB = New-DemoSecret
    $env:GATEKEEPER_AGENT_KEYS_JSON = (@{
        "agent-a" = $agentA
        "agent-b" = $agentB
    } | ConvertTo-Json -Compress)
    $env:GATEKEEPER_AGENT_CAPABILITIES_JSON = (@{
        "agent-a" = @()
        "agent-b" = @("parent-shield.navigation")
    } | ConvertTo-Json -Compress)
    Write-State "agent_keys" "GENERATED_EPHEMERAL" @{ printed = $false }
}

if (-not $env:GATEKEEPER_AGENT_KEYS_JSON) {
    throw "GATEKEEPER_AGENT_KEYS_JSON is required. Use -GenerateDemoKeys only for an explicit ephemeral hackathon identity set."
}
if (-not $env:GATEKEEPER_AGENT_CAPABILITIES_JSON) {
    throw "GATEKEEPER_AGENT_CAPABILITIES_JSON is required"
}

try {
    $keys = $env:GATEKEEPER_AGENT_KEYS_JSON | ConvertFrom-Json
} catch {
    throw "GATEKEEPER_AGENT_KEYS_JSON must be valid JSON"
}

$agentBSecret = $keys.'agent-b'
if (-not ($agentBSecret -is [string]) -or -not $agentBSecret) {
    throw "GATEKEEPER_AGENT_KEYS_JSON must contain a non-empty agent-b key"
}

$env:DIAGNOSTIC_AGENT_ID = "agent-b"
$env:DIAGNOSTIC_AGENT_SECRET = $agentBSecret
Write-State "diagnostic_identity" "READY" @{ principal = "agent-b"; secret_printed = $false }

try {
    $v2 = Invoke-RestMethod -Uri "http://127.0.0.1:8787/health" -Method Get -TimeoutSec 3
} catch {
    throw "Gatekeeper V2 is not reachable at http://127.0.0.1:8787/health"
}
if (-not ($v2.routeMounts -contains "parent-shield")) {
    throw "Gatekeeper V2 health is reachable but parent-shield is not mounted"
}
Write-State "gatekeeper_v2" "READY" @{ parent_shield_mounted = $true; runtime_identity_proven = $false }

$ports = @(8081, 8082, 8083)
if ($Restart) {
    foreach ($port in $ports) { Stop-Listener $port }
} else {
    $occupied = @($ports | Where-Object { Get-Listener $_ })
    if ($occupied.Count -gt 0) {
        throw "hackathon service ports already occupied: $($occupied -join ','). Re-run with -Restart to replace those listeners."
    }
}

$artifact = Start-Process python -ArgumentList ".\src\artifact-boundary\server.py" -WorkingDirectory $RepoRoot -PassThru
$action = Start-Process python -ArgumentList ".\src\action-edge\server.py" -WorkingDirectory $RepoRoot -PassThru
$orchestrator = Start-Process python -ArgumentList ".\src\demo-orchestrator\server.py" -WorkingDirectory $RepoRoot -PassThru

Wait-JsonHealth "http://127.0.0.1:8081/health" | Out-Null
Wait-JsonHealth "http://127.0.0.1:8082/health" | Out-Null
Wait-JsonHealth "http://127.0.0.1:8083/health" | Out-Null
$upstream = Wait-JsonHealth "http://127.0.0.1:8082/health/upstream"
if ($upstream.reachable_from_action_edge -ne $true -or $upstream.parent_shield_mounted -ne $true) {
    throw "action edge cannot prove Gatekeeper V2 parent-shield reachability"
}
Write-State "hackathon_services" "READY" @{
    artifact_boundary_pid = $artifact.Id
    action_edge_pid = $action.Id
    orchestrator_pid = $orchestrator.Id
    action_edge_v2_latency_ms = $upstream.latency_ms
}

if (-not $SkipPublicEdge) {
    Require-Command docker
    $existingContainer = (& docker ps -a --filter "name=^/gatekeeper-public-edge$" --format "{{.ID}}" 2>$null).Trim()
    if ($existingContainer) {
        & docker rm -f gatekeeper-public-edge | Out-Null
    }
    $nginxPath = (Resolve-Path ".\nginx.conf").Path
    $containerId = (& docker run -d --rm --name gatekeeper-public-edge -p 8080:8080 --mount "type=bind,source=$nginxPath,target=/etc/nginx/conf.d/default.conf,readonly" nginx:alpine).Trim()
    if (-not $containerId) { throw "failed to start gatekeeper-public-edge nginx container" }
    Wait-JsonHealth "http://127.0.0.1:8080/health" | Out-Null
    Write-State "public_edge" "READY" @{ container = "gatekeeper-public-edge"; runtime_identity_proven = $false }
}

Write-State "DAY2_STACK" "READY" @{
    gatekeeper_authority_source = "Gatekeeper-V2-NPU"
    artifact_boundary = "http://127.0.0.1:8081"
    action_edge = "http://127.0.0.1:8082"
    orchestrator = "http://127.0.0.1:8083"
    public_edge = $(if ($SkipPublicEdge) { "SKIPPED" } else { "http://127.0.0.1:8080" })
    diagnostic_secret_printed = $false
}

if ($RunGate0) {
    Write-State "GATE0_RUN" "STARTING" @{ fresh_artifact = $true }
    & python ".\scripts\prove_gate0.py"
    if ($LASTEXITCODE -ne 0) {
        throw "Gate 0 proof failed with exit code $LASTEXITCODE"
    }
    Write-State "GATE0_RUN" "PASS" @{ core_authority_proof = $true }
}
