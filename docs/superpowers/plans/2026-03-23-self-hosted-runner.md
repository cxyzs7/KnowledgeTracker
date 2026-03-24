# Self-Hosted Runner on WSL2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register the user's WSL2 laptop as a GitHub Actions self-hosted runner so that daily/weekly workflows run from a residential IP, unblocking Reddit's unauthenticated JSON API.

**Architecture:** The GitHub Actions runner agent runs as a systemd service inside WSL2, keeping it alive persistently. A Windows Task Scheduler entry starts WSL on login so no terminal needs to stay open. Both workflow files get two changes: `runs-on: self-hosted` and a `rm -rf vault` prefix on the vault clone step.

**Tech Stack:** WSL2 (Ubuntu), systemd, GitHub Actions self-hosted runner binary, Windows Task Scheduler, YAML

---

## File Map

| File | Change |
|------|--------|
| `.github/workflows/daily_digest.yml` | `runs-on: self-hosted`, `rm -rf vault` before clone |
| `.github/workflows/weekly_deepdive.yml` | `runs-on: self-hosted`, `rm -rf vault` before clone |

All other changes are infrastructure on the laptop (no repo files).

---

## Task 1: Enable systemd in WSL2

**Context:** The GitHub Actions runner installs itself as a systemd service. WSL2 does not enable systemd by default — without it, `svc.sh install` will fail and the runner cannot auto-start.

**Where:** Inside your WSL2 terminal (Ubuntu or whichever distro you use).

- [ ] **Step 1: Check if systemd is already enabled**

```bash
ps --no-headers -o comm 1
```

Expected output if already enabled: `systemd`
Expected output if not enabled: `init` or `docker-init`

If it already says `systemd`, skip to Task 2.

- [ ] **Step 2: Edit `/etc/wsl.conf` to enable systemd**

```bash
sudo tee /etc/wsl.conf > /dev/null <<'EOF'
[boot]
systemd=true
EOF
```

- [ ] **Step 3: Verify the file was written correctly**

```bash
cat /etc/wsl.conf
```

Expected:
```
[boot]
systemd=true
```

- [ ] **Step 4: Shut down WSL from PowerShell (run this in Windows PowerShell, not WSL)**

```powershell
wsl --shutdown
```

- [ ] **Step 5: Reopen your WSL terminal and confirm systemd is now PID 1**

```bash
ps --no-headers -o comm 1
```

Expected: `systemd`

---

## Task 2: Install runtime dependencies in WSL

**Context:** The workflow steps run `git` and `uv` directly on the host. These must be available in the WSL environment the runner uses.

- [ ] **Step 1: Confirm git is installed**

```bash
git --version
```

Expected: `git version 2.x.x` — if missing, run `sudo apt-get install -y git`

- [ ] **Step 2: Confirm uv is installed**

```bash
uv --version
```

Expected: `uv x.x.x` — if missing, install with:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

---

## Task 3: Download and register the GitHub Actions runner

**Context:** GitHub provides a per-repo registration flow that generates a one-time token and exact download commands. The token expires after 1 hour so complete this task in one sitting.

- [ ] **Step 1: Navigate to the runner registration page**

In your browser: go to your KnowledgeTracker repo on GitHub → **Settings** → **Actions** → **Runners** → **New self-hosted runner**

Select: **Linux** / **x64**

GitHub will show a block of commands. Use those exact commands (they contain a token unique to your repo). The steps below mirror the structure — use GitHub's actual values.

- [ ] **Step 2: Create a directory for the runner and download it (use GitHub's commands)**

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner
# GitHub will show the exact curl command with the current runner version, e.g.:
# curl -o actions-runner-linux-x64-2.x.x.tar.gz -L https://github.com/actions/runner/releases/download/v2.x.x/actions-runner-linux-x64-2.x.x.tar.gz
# tar xzf ./actions-runner-linux-x64-2.x.x.tar.gz
```

- [ ] **Step 3: Configure the runner (use GitHub's command)**

```bash
# GitHub will show the exact ./config.sh command with your repo URL and token, e.g.:
# ./config.sh --url https://github.com/YOUR_USERNAME/KnowledgeTracker --token YOUR_TOKEN
```

When prompted:
- Runner group: press Enter (default)
- Runner name: press Enter (defaults to hostname) or enter something memorable like `wsl-laptop`
- Additional labels: press Enter (none needed)
- Work folder: press Enter (default `_work`)

- [ ] **Step 4: Confirm the runner registered successfully**

The config step should end with:
```
√ Runner successfully added
√ Runner connection is good
```

Go to GitHub → Settings → Actions → Runners — your runner should appear with status **Idle**.

---

## Task 4: Install the runner as a systemd service

**Context:** Running `./run.sh` manually works but stops when the terminal closes. Installing as a systemd service makes it start automatically when WSL boots and restart after crashes.

- [ ] **Step 1: Install the service (must be in the runner directory)**

```bash
cd ~/actions-runner
sudo ./svc.sh install
```

Expected output ends with: `Service actions.runner.<repo>.<runner-name> installed` (where `<runner-name>` is whatever name you chose in Task 3, Step 3)

- [ ] **Step 2: Start the service**

```bash
sudo ./svc.sh start
```

- [ ] **Step 3: Verify the service is running**

```bash
sudo ./svc.sh status
```

Expected: `Active: active (running)`

- [ ] **Step 4: Verify the runner shows as Idle on GitHub**

GitHub → Settings → Actions → Runners — status should be **Idle** (not Offline).

---

## Task 5: Set up Windows Task Scheduler to auto-start WSL on login

**Context:** With systemd enabled, the runner service starts automatically when WSL boots. But WSL itself only starts when something launches it. Without a Task Scheduler entry, you'd need to open a terminal manually after every Windows login.

**Where:** Windows PowerShell (run as Administrator).

- [ ] **Step 1: Open PowerShell as Administrator**

Search "PowerShell" in Start menu → right-click → "Run as administrator"

- [ ] **Step 2: Create the scheduled task**

If your default WSL distro is not the one where the runner is installed, replace `"wsl.exe"` with `"wsl.exe" -ArgumentList "-d","Ubuntu"` (substituting your distro name from `wsl --list`).

```powershell
$action = New-ScheduledTaskAction -Execute "wsl.exe"
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0
Register-ScheduledTask -TaskName "Start WSL Runner" -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest
```

`-ExecutionTimeLimit 0` means the task never times out. `-RunLevel Highest` ensures it has sufficient privileges.

- [ ] **Step 3: Verify the task was created**

```powershell
Get-ScheduledTask -TaskName "Start WSL Runner"
```

Expected: task listed with `State: Ready`

- [ ] **Step 4: Configure Windows power settings (do this once)**

Control Panel → Power Options → set plan to **High Performance** or **Balanced**, then **Change plan settings** → set "Put the computer to sleep" to **Never**. If using a laptop, also set the lid-close action to **Do nothing** (under "Choose what closing the lid does").

- [ ] **Step 5: Test it — restart Windows and confirm the runner comes back online**

After reboot, wait ~30 seconds, then check GitHub → Settings → Actions → Runners. The runner should show **Idle** without you opening a terminal.

---

## Task 6: Update the workflow files

**Context:** Two YAML changes per file: `runs-on` and the vault clone step.

- [ ] **Step 1: Update `daily_digest.yml`**

In `.github/workflows/daily_digest.yml`, change line 10:
```yaml
# before
    runs-on: ubuntu-latest

# after
    runs-on: self-hosted
```

And update the "Checkout Obsidian vault" step (lines 16–18):
```yaml
      - name: Checkout Obsidian vault
        run: |
          rm -rf vault
          git clone https://x-access-token:${{ secrets.VAULT_TOKEN }}@github.com/${{ secrets.VAULT_REPO }} vault
          echo "VAULT_PATH=$(pwd)/vault" >> $GITHUB_ENV
```

- [ ] **Step 2: Update `weekly_deepdive.yml`** — same two changes

In `.github/workflows/weekly_deepdive.yml`, change line 10:
```yaml
    runs-on: self-hosted
```

And the "Checkout Obsidian vault" step (lines 16–18):
```yaml
      - name: Checkout Obsidian vault
        run: |
          rm -rf vault
          git clone https://x-access-token:${{ secrets.VAULT_TOKEN }}@github.com/${{ secrets.VAULT_REPO }} vault
          echo "VAULT_PATH=$(pwd)/vault" >> $GITHUB_ENV
```

- [ ] **Step 3: Commit and push**

```bash
git add .github/workflows/daily_digest.yml .github/workflows/weekly_deepdive.yml
git commit -m "feat: switch to self-hosted runner for residential IP"
git push origin main
```

---

## Task 7: Verify end-to-end with a manual trigger

**Context:** Trigger the daily digest workflow manually to confirm the runner picks it up and the pipeline completes successfully, including Reddit results.

- [ ] **Step 1: Trigger the workflow manually**

GitHub → Actions → "Daily Digest" → **Run workflow** → Run workflow

- [ ] **Step 2: Watch the run**

Click into the run. Confirm:
- The job is picked up by your self-hosted runner (shown in the job header, not `ubuntu-latest`)
- All steps pass

- [ ] **Step 3: Check the vault for Reddit articles**

In your vault (or the GitHub vault repo), open today's digest. Confirm it contains articles sourced from Reddit (`source: reddit` in frontmatter, or Reddit URLs in the article list).

- [ ] **Step 4: Confirm the runner workspace contains the vault (expected)**

In WSL:
```bash
ls ~/actions-runner/_work/KnowledgeTracker/KnowledgeTracker/vault/
```

You should see your vault files. This directory is intentional — it persists between runs. Do not sync or share it externally as it contains the `VAULT_TOKEN` in `vault/.git/config`.
