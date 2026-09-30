<#
Astra (gpt-6-astra) reviews Radar candidates in GitHub Actions with a ChatGPT
login stored in the CODEX_AUTH_JSON secret. See docs/ASTRA-LOGIN.md.

  -Seed ci       Sign in once for Actions and upload that login as the secret.
  -Seed reserve  Sign in once for the spare login this PC keeps for repairs.
  -Repair        (scheduled) Keep the spare fresh; if Actions reports the login
                 broken, hand the spare to Actions and re-run the workflow.

Each seed is a separate ChatGPT sign-in, so its refresh token is independent of
your everyday Codex login and of the other copy. Nothing here prints tokens.
#>
param(
    [ValidateSet('ci', 'reserve')][string]$Seed,
    [switch]$Repair,
    [string]$Repo = 'harshad22491/AI-Product-Radar'
)
$ErrorActionPreference = 'Stop'
# Windows PowerShell pipes ASCII to native programs by default.
$OutputEncoding = New-Object System.Text.UTF8Encoding $false
$stateDir = Join-Path $env:LOCALAPPDATA 'AI-Radar'
$reserveHome = Join-Path $env:USERPROFILE '.codex-radar-reserve'
$logFile = Join-Path $stateDir 'astra-login.log'
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

function Write-Log([string]$message) {
    $line = (Get-Date -Format 's') + ' ' + $message
    Add-Content -LiteralPath $logFile -Value $line -Encoding utf8
    Write-Output $line
}

function Show-Notice([string]$message) {
    Write-Log $message
    try {
        Add-Type -AssemblyName System.Windows.Forms
        $icon = New-Object System.Windows.Forms.NotifyIcon
        $icon.Icon = [System.Drawing.SystemIcons]::Information
        $icon.Visible = $true
        $icon.ShowBalloonTip(20000, 'AI Product Radar - Astra login', $message, 'Info')
        Start-Sleep -Seconds 20
        $icon.Dispose()
    } catch { }
}

function Invoke-Codex([string]$codexHome, [string[]]$arguments, [string]$stdin = '') {
    $previous = $env:CODEX_HOME
    $env:CODEX_HOME = $codexHome
    try {
        if ($stdin) { $stdin | & codex @arguments 2>&1 | Out-Null } else { & codex @arguments | Out-Host }
        return $LASTEXITCODE
    } finally { $env:CODEX_HOME = $previous }
}

function Set-CiSecret([string]$authFile) {
    Get-Content -LiteralPath $authFile -Raw | & gh secret set CODEX_AUTH_JSON --repo $Repo | Out-Null
    if ($LASTEXITCODE) { throw 'gh secret set failed' }
}

if ($Seed) {
    if ($Seed -eq 'ci') {
        # A throwaway home: once uploaded, Actions owns this login's refresh chain.
        $target = Join-Path $env:TEMP ('codex-radar-ci-' + [guid]::NewGuid().ToString('N'))
    } else {
        $target = $reserveHome
    }
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    Write-Output "Sign in to ChatGPT in the browser window that opens (login for: $Seed)."
    if ((Invoke-Codex $target @('login'))) { throw 'codex login failed' }
    $auth = Join-Path $target 'auth.json'
    if (!(Test-Path -LiteralPath $auth)) { throw 'codex login did not create auth.json' }
    if ($Seed -eq 'ci') {
        Set-CiSecret $auth
        Remove-Item -LiteralPath $target -Recurse -Force
        & gh variable set ASTRA_AUTH_STATUS --repo $Repo --body seeded | Out-Null
        Write-Log 'Seeded Actions login (CODEX_AUTH_JSON) and removed the local copy.'
    } else {
        Set-Content -LiteralPath (Join-Path $stateDir 'reserve-warmed') -Value (Get-Date -Format 's')
        Write-Log 'Seeded spare login in ~/.codex-radar-reserve.'
    }
    exit 0
}

if (!$Repair) { throw 'Pass -Seed ci, -Seed reserve or -Repair.' }

$reserveAuth = Join-Path $reserveHome 'auth.json'
$warmedFile = Join-Path $stateDir 'reserve-warmed'

# 1. Keep the spare alive: a tiny daily call lets Codex refresh it before it goes stale.
if (Test-Path -LiteralPath $reserveAuth) {
    $last = if (Test-Path $warmedFile) { [datetime](Get-Content $warmedFile -Raw).Trim() } else { [datetime]::MinValue }
    if ((Get-Date) - $last -gt (New-TimeSpan -Hours 20)) {
        $scratch = Join-Path $env:TEMP 'codex-radar-warm'
        New-Item -ItemType Directory -Force -Path $scratch | Out-Null
        $code = Invoke-Codex $reserveHome @('exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check',
            '--disable', 'shell_tool', '-s', 'read-only', '-C', $scratch, '-') 'Reply with OK.'
        if ($code) {
            Show-Notice ('The spare Astra login stopped working. Run: ' + $PSCommandPath + ' -Seed reserve')
        } else {
            Set-Content -LiteralPath $warmedFile -Value (Get-Date -Format 's')
            Write-Log 'Spare login refreshed.'
        }
    }
}

# 2. Repair: Actions sets ASTRA_AUTH_STATUS=broken when OpenAI rejects its login.
$status = (& gh variable get ASTRA_AUTH_STATUS --repo $Repo 2>$null)
if ($LASTEXITCODE) { Write-Log 'Could not read ASTRA_AUTH_STATUS (offline or gh signed out).'; exit 0 }
$status = "$status".Trim()
if ($status -ne 'broken') { exit 0 }

if (!(Test-Path -LiteralPath $reserveAuth)) {
    Show-Notice ('Astra login in GitHub Actions is broken and no spare is ready. Run: ' + $PSCommandPath + ' -Seed ci')
    exit 0
}
Set-CiSecret $reserveAuth
# The spare now belongs to Actions; keeping a copy here would fork its refresh chain.
Remove-Item -LiteralPath $reserveAuth -Force
Remove-Item -LiteralPath $warmedFile -Force -ErrorAction SilentlyContinue
& gh variable set ASTRA_AUTH_STATUS --repo $Repo --body repaired | Out-Null
& gh workflow run daily.yml --repo $Repo | Out-Null
Show-Notice ('Repaired the Astra login in GitHub Actions and re-ran today''s Radar. Make a new spare when convenient: ' + $PSCommandPath + ' -Seed reserve')
