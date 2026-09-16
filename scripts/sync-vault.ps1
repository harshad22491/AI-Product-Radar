# Runs radar.sync with provided exchange and vault paths.
param(
    [Parameter(Mandatory = $true)][string]$ExchangePath,
    [Parameter(Mandatory = $true)][string]$VaultPath
)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

Push-Location -LiteralPath $repoRoot
try {
    python -m radar.sync --exchange $ExchangePath --vault $VaultPath
    $radarExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $radarExitCode
