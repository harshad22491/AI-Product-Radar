# Astra reviewer login

Opus 5.5 (`claude-opus-5-5`) researches both editions. Astra (`gpt-6-astra`, via
the Codex CLI) independently reviews each candidate. Astra signs in with a
ChatGPT login stored in the `CODEX_AUTH_JSON` Actions secret, not an API key.

OpenAI's guidance for this pattern is at
https://learn.chatgpt.com/docs/auth/ci-cd-auth. It warns against using it in
public repositories; this repository is public by the owner's choice. Secrets
are not exposed to fork pull requests and this workflow runs only on schedule
or manual dispatch. The runner never prints the login, removes it after each
run, and gives the reviewer no shell tool.

## Why it needs care

Codex refreshes the login about every eight days and each refresh invalidates
the previous refresh token. So:

- The workflow writes the refreshed `auth.json` back to the secret after every
  run (`RADAR_GH_TOKEN` must be able to set repository secrets and variables).
- Runs are serialized by the `daily-radar` concurrency group.
- Each copy of the login must be a separate ChatGPT sign-in. Never copy
  `~/.codex/auth.json` from your everyday Codex; the two would invalidate each
  other.

## Automatic repair

When OpenAI rejects the login, the runner stops before spending more research
and the workflow sets the repository variable `ASTRA_AUTH_STATUS=broken`.

`scripts/astra-login.ps1 -Repair`, run hourly on the owner's PC, keeps a spare
sign-in fresh in `~/.codex-radar-reserve` with one tiny call a day. When it sees
`broken`, it uploads the spare as the new secret, deletes the local copy, sets
the status to `repaired`, re-runs the workflow and shows a notification. Then
create a new spare (one browser sign-in) when convenient.

## Setup

```powershell
scripts\astra-login.ps1 -Seed ci        # browser sign-in; uploads CODEX_AUTH_JSON
scripts\astra-login.ps1 -Seed reserve   # second browser sign-in; kept on this PC
```

Register the hourly repair as a Windows scheduled task (owner's decision; it
is not installed automatically):

```powershell
$script = "$env:LOCALAPPDATA\AI-Radar\astra-login.ps1"
New-Item -ItemType Directory -Force (Split-Path $script) | Out-Null
Copy-Item scripts\astra-login.ps1 $script -Force
$action = New-ScheduledTaskAction -Execute powershell.exe -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`" -Repair"
$triggers = @((New-ScheduledTaskTrigger -AtLogOn), (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Hours 1)))
Register-ScheduledTask -TaskName 'AI Radar - Astra Login Repair' -Action $action -Trigger $triggers -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -MultipleInstances IgnoreNew)
```

The repair only works while the PC is on. Without a spare it notifies instead;
run `-Seed ci` to fix the secret by hand.
