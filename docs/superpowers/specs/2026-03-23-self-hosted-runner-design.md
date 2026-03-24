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
A binary provided by GitHub (~100 MB). Configured once with a registration token from the repo settings. Communicates outbound over HTTPS — no inbound ports required. Registered under the repo (not org-level).

**Systemd service (WSL2)**
The runner ships with `svc.sh`, which installs it as a systemd unit. The service auto-starts on WSL boot and restarts on crashes. Requires systemd to be enabled in WSL2.

**WSL2 systemd enablement**
Add to `/etc/wsl.conf` inside WSL:
```ini
[boot]
systemd=true
```
Restart WSL with `wsl --shutdown` from PowerShell, then reopen. This is a one-time setup.

**Windows Task Scheduler entry**
A startup task that runs `wsl.exe` on Windows login, ensuring the WSL instance (and therefore the runner systemd service) is active without requiring a terminal to be open.

**Workflow change**
Both `.github/workflows/daily_digest.yml` and `.github/workflows/weekly_deepdive.yml` change one line:
```yaml
# before
runs-on: ubuntu-latest

# after
runs-on: self-hosted
```

### Runtime dependencies on the laptop (WSL)

- `git` — for vault checkout and push steps
- `uv` — for dependency installation and running the pipeline
- `python3` — installed by uv as needed

These are standard dev tools, likely already present.

## What does not change

- All GitHub Actions secrets (`ANTHROPIC_API_KEY`, `VAULT_TOKEN`, `VAULT_REPO`, `TAVILY_API_KEY`, `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD`) — still stored and injected by GitHub
- Cron schedules (`0 7 * * *` daily, `0 8 * * 1` weekly) — still defined in workflow files
- Vault clone, run, and git push steps — unchanged
- `GITHUB_ACTIONS=true` environment variable — still set automatically by the runner, so `git_sync` inside `run.py` is still skipped correctly

## Networking

WSL2 uses Windows NAT for outbound traffic. Reddit (and all other HTTP calls) see the Windows machine's residential ISP IP. This IP is not in Reddit's datacenter blocklist.

## Security

Self-hosted runners on public repos carry a risk of malicious PRs triggering jobs on the host machine. This repo is private, so that risk does not apply.

## Out of scope

- Migrating to a VPS (can be done later by re-registering the runner on a Hetzner/Vultr instance with no other changes)
- Changing cron schedules (separate concern)
- Authenticating to Reddit via OAuth (not currently possible for new apps)
