param(
    [string]$ExchangePath = 'G:\My Drive\AI Product Radar',
    [string]$VaultPath = 'D:\Paper Recommender\AI Product Radar Vault'
)
$ErrorActionPreference = 'Stop'
$radarRoot = Split-Path -Parent $PSScriptRoot
$radarPython = (Get-Command python -ErrorAction Stop).Source
$radarScript = Join-Path $PSScriptRoot 'sync-vault.ps1'
if (!(Test-Path -LiteralPath $ExchangePath -PathType Container)) { throw 'Drive exchange is not available.' }
if (!(Test-Path -LiteralPath $VaultPath -PathType Container)) { throw 'Initialize the vault first.' }
$radarArguments = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $radarScript + '" -ExchangePath "' + $ExchangePath + '" -VaultPath "' + $VaultPath + '"'
$radarAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $radarArguments -WorkingDirectory $radarRoot
$radarTriggers = @(
    (New-ScheduledTaskTrigger -AtLogOn),
    (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 15))
)
$radarSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$radarPrincipal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'AI Product Radar - Obsidian Sync' -Action $radarAction -Trigger $radarTriggers -Settings $radarSettings -Principal $radarPrincipal -Description 'Sync the separate Radar vault with private Google Drive when this PC is online. Does not run cloud research or send email.' -Force | Select-Object TaskName,State
