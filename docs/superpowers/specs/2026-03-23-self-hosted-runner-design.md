# Self-Hosted GitHub Actions Runner on WSL2 Laptop

**Date:** 2026-03-23
**Status:** Approved

## Problem

Reddit blocks unauthenticated `.json` API requests from GitHub Actions IP ranges (AWS us-east-1 and similar). The `reddit.py` source returns `[]` silently on every run. Reddit no longer grants new OAuth app access to regular users, so authenticated API access is not an option.

## Solution

Register the user's Windows laptop (running WSL2) as a GitHub Actions self-hosted runner. The laptop has a residential IP that Reddit does not block. Jobs that previously ran on `ubuntu-latest` (GitHub-hosted) run instead on the laptop. All other pipeline infrastructure — GitHub secrets, cron scheduling, vault git push — remains unchanged.

## Architecture

### Components

**GitHub Actions runner agent**
A binary provided by GitHub. Download and install via the repo's Settings > Actions > Runners > "New self-hosted runner" UI — GitHub generates per-OS download and `./config.sh` commands with a pre-filled registration token. The registration token is single-use and expires after one hour; it is only needed at initial setup. After `./config.sh` completes, the runner stores durable credentials in `.credentials` files and never needs the token again. Communicates outbound over HTTPS — no inbound ports required.

**Systemd service (WSL2)**
The runner ships with `svc.sh`, which installs it as a systemd unit (`sudo ./svc.sh install && sudo ./svc.sh start`). The service auto-starts on WSL boot and restarts on crashes. Requires systemd to be enabled in WSL2 first.

**WSL2 systemd enablement**
Add to `/etc/wsl.conf` inside WSL:
```ini
[boot]
systemd=true
```
Restart WSL with `wsl --shutdown` from PowerShell, then reopen. This is a one-time setup.

**WSL auto-start on Windows login**
With systemd enabled, the runner service starts automatically when the WSL instance starts. To start WSL on Windows login without requiring a terminal, create a Windows Task Scheduler task:
- Trigger: At log on (for your user)
- Action: Start a program → `wsl.exe` with no arguments (or `wsl.exe -d Ubuntu` if the distro name is not the default)
- Settings: uncheck "Stop the task if it runs longer than"

This can be created via Task Scheduler GUI (`taskschd.msc`) or PowerShell:
```powershell
$action = New-ScheduledTaskAction -Execute "wsl.exe"
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "Start WSL" -Action $action -Trigger $trigger -RunLevel Highest
```

**Workflow change**
Both `.github/workflows/daily_digest.yml` and `.github/workflows/weekly_deepdive.yml` require two changes:

1. Change the runner:
```yaml
# before
runs-on: ubuntu-latest

# after
runs-on: self-hosted
```

2. Add `rm -rf vault` before the vault clone step. On GitHub-hosted runners the workspace is fresh on every job. On a self-hosted runner the workspace directory persists between runs, so the `git clone ... vault` step would fail with "destination path 'vault' already exists" on every run after the first. (The `actions/checkout@v4` step for the KnowledgeTracker repo itself does not need this — that action handles workspace cleanup internally.)
```yaml
- name: Checkout Obsidian vault
  run: |
    rm -rf vault
    git clone https://x-access-token:${{ secrets.VAULT_TOKEN }}@github.com/${{ secrets.VAULT_REPO }} vault
    echo "VAULT_PATH=$(pwd)/vault" >> $GITHUB_ENV
```

### Runtime dependencies on the laptop (WSL)

- `git` — for vault checkout and push steps
- `uv` — for dependency installation and running the pipeline
- `python3` — installed by uv as needed

These are standard dev tools, likely already present.

## What does not change

- All GitHub Actions secrets (`ANTHROPIC_API_KEY`, `VAULT_TOKEN`, `VAULT_REPO`, `TAVILY_API_KEY`, `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD`) — still stored and injected by GitHub
- Cron schedules (`0 7 * * *` daily, `0 8 * * 1` weekly) — still defined in workflow files
- Vault run and git push steps — unchanged (vault clone step requires a `rm -rf vault` prefix; see Workflow change section)
- `GITHUB_ACTIONS=true` environment variable — still set automatically by the runner, so `git_sync` inside `run.py` is still skipped correctly; vault push still happens via the inline `git push` step in the workflow
- `setup-uv` caching — on a self-hosted runner the cache is stored on the local filesystem rather than GitHub's cache service; this works correctly but the first run will be slower while the cache is populated

## Operational constraint

The laptop must be on and the WSL instance running at the cron times (07:00 UTC daily, 08:00 UTC Monday). If the runner is offline when a job is scheduled, GitHub queues the job and runs it when the runner reconnects — potentially hours later, producing a stale digest. Queued jobs are cancelled after 35 days if no runner picks them up. The laptop should be configured to never sleep (power plan: never sleep, lid close action: do nothing if running on AC).

## Networking

WSL2 uses Windows NAT for outbound traffic. Reddit (and all other HTTP calls) see the Windows machine's residential ISP IP. This IP is not in Reddit's datacenter blocklist.

## Security

Self-hosted runners on public repos carry a risk of malicious PRs triggering jobs on the host machine. This repo is private, so that risk does not apply.

The vault is cloned into the runner's work directory on each run. After the run, `vault/.git/config` contains the `VAULT_TOKEN` in the remote URL in plaintext. This is the same behaviour as on GitHub-hosted runners (the directory is ephemeral there; on the laptop it persists between runs). The runner work directory should be treated as sensitive and not shared or synced externally.

## Out of scope

- Migrating to a VPS (can be done later by re-registering the runner on a Hetzner/Vultr instance with no other changes)
- Changing cron schedules (separate concern)
- Authenticating to Reddit via OAuth (not currently possible for new apps)
