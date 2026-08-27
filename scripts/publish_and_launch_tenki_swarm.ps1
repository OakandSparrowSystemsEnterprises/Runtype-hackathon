param(
    [int]$Width = 2,
    [string]$TemplateId = "01a04108-b541-7a1d-ba3d-e22c1479bca3",
    [string]$WorkspaceName = $env:TENKI_WORKSPACE_NAME,
    [string]$ArtifactName = "gatekeeper-goi-worker-v2",
    [string]$ImageTag = "latest",
    [string]$WslDistribution = "Ubuntu-24.04",
    [string]$TenkiCli = "/home/ankou/.local/bin/tenki",
    [switch]$Republish
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

if ($Width -lt 2 -or $Width -gt 16) {
    throw "Width must be between 2 and 16"
}

function Invoke-Tenki([string[]]$Arguments) {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & wsl.exe -d $WslDistribution -- $TenkiCli @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($exitCode -ne 0) {
        throw "Tenki command failed: $($Arguments -join ' ')`n$($output -join "`n")"
    }
    return @($output | ForEach-Object { "$_" })
}

function Test-TenkiImage([string]$ImageRef) {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $null = & wsl.exe -d $WslDistribution -- $TenkiCli sandbox registry resolve $ImageRef --json 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    return ($exitCode -eq 0)
}

function Resolve-WorkspaceName {
    if (-not [string]::IsNullOrWhiteSpace($WorkspaceName)) {
        return $WorkspaceName.Trim()
    }

    $python = @'
from tenki import Client
client = Client()
identity = client.who_am_i()
for workspace in identity.workspaces:
    if getattr(workspace, "name", None):
        print(workspace.name)
        break
'@

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & wsl.exe -d $WslDistribution -- python3 -c $python 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }

    if ($exitCode -ne 0) {
        throw "Could not resolve the Tenki workspace name through WhoAmI. Set TENKI_WORKSPACE_NAME or pass -WorkspaceName. Python SDK output:`n$($output -join "`n")"
    }

    $resolved = @($output | ForEach-Object { ("$_").Trim() } | Where-Object { $_ }) | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($resolved)) {
        throw "Tenki WhoAmI returned no workspace name. Set TENKI_WORKSPACE_NAME or pass -WorkspaceName."
    }
    return $resolved
}

$resolvedWorkspace = Resolve-WorkspaceName
$ImageRef = "$resolvedWorkspace/$ArtifactName`:$ImageTag"

if ($Republish -or -not (Test-TenkiImage $ImageRef)) {
    Write-Host "Publishing Tenki template $TemplateId as $ImageRef..."
    Invoke-Tenki @(
        "sandbox", "registry", "publish",
        "--image", $ImageRef,
        "--from-template", $TemplateId,
        "--visibility", "private"
    ) | Out-Null
} else {
    Write-Host "Using existing Tenki registry image: $ImageRef"
}

$env:TENKI_IMAGE_REF = $ImageRef
$env:TENKI_WORKSPACE_NAME = $resolvedWorkspace
$env:TENKI_SWARM_WIDTH = [string]$Width

Write-Host "Launching $Width fresh sticky Tenki workers from published image $ImageRef..."
& (Join-Path $PSScriptRoot "launch_tenki_swarm.ps1") `
    -Width $Width `
    -ImageRef $ImageRef `
    -Sticky `
    -NoAutoDiscover `
    -WslDistribution $WslDistribution `
    -TenkiCli $TenkiCli
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
