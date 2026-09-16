param(
    [string]$ExchangePath = 'G:\My Drive\AI Product Radar',
    [string]$VaultPath = 'D:\Paper Recommender\AI Product Radar Vault'
)
$radarMutex = New-Object System.Threading.Mutex($false, 'Local\AIProductRadarVaultSync')
if (!$radarMutex.WaitOne(0)) { $radarMutex.Dispose(); exit 0 }
try {
    while ($true) {
        if ((Test-Path -LiteralPath $ExchangePath) -and (Test-Path -LiteralPath $VaultPath)) {
            try {
                Push-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
                try { python -m radar.sync --exchange $ExchangePath --vault $VaultPath }
                finally { Pop-Location }
            } catch {
                # Keep the user's notes intact and retry when Drive is available.
            }
        }
        Start-Sleep -Seconds 900
    }
} finally { $radarMutex.ReleaseMutex(); $radarMutex.Dispose() }
