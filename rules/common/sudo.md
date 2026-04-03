# Sudo Operations

Claude Code cannot run `sudo` directly — no TTY for the password prompt. A PreToolUse hook (`sudo-poll.sh`) handles this automatically for most cases.

## How It Works

1. You run a command with `sudo` (e.g., `sudo apt install ripgrep`)
2. The hook detects `sudo`, checks for cached credentials
3. If not cached, it prints "run `sudo -v` in another pane" and polls for 30s
4. User authenticates in another terminal → hook detects cached creds → command runs

**Prerequisite**: The user's sudoers must have `timestamp_type=global` to share credential cache across TTYs. Without this, `sudo -v` in another pane won't help.

## If the Hook Times Out

If the hook denies after 30s despite the user running `sudo -v`, the most likely cause is that `timestamp_type=global` is not configured. Diagnose and guide the user:

1. **Check**: `sudo grep -r timestamp_type /etc/sudoers /etc/sudoers.d/ 2>/dev/null` — if no output, the setting is missing
2. **Explain**: By default, sudo caches credentials per-TTY. Claude runs in a different TTY than the user's terminal, so `sudo -v` in another pane doesn't help unless the cache is global.
3. **Guide the user** to add the setting:
   ```
   sudo env EDITOR=/usr/bin/vim visudo
   ```
   Then add: `Defaults timestamp_type=global`
4. **After the change**: The user runs `sudo -v` in any terminal, then retries the failed command.

If the user can't or won't modify sudoers (shared machines, policy restrictions), fall back to script generation (see below).

## Just Use Sudo Normally

With the hook active, write `sudo` commands directly in Bash tool calls — no special handling needed. The hook manages the authentication flow transparently.

```bash
sudo apt install -y ripgrep
sudo systemctl restart nginx
sudo chown jessica:jessica /etc/myapp/config.toml
```

This also applies to other privilege escalation mechanisms that prompt for passwords (`pkexec`, `su -c`), though the hook only detects the `sudo` keyword.

## Fallback: Script Generation

For complex multi-step operations (5+ sudo commands, phased execution, or when you need a reviewable artifact), generate a script instead. This is the exception, not the default.

Write the script via `get-tmp-filename`, tell the user the exact run command, and read the log afterward.

Key rules for generated scripts:
- `set -euo pipefail` and `trap` for the log path on exit
- `install -m 600 /dev/null "$LOG_FILE"` — restrictive permissions before writing
- Use `"$@"` for command execution, never `eval`
- `tee -a` so output appears on terminal and in log simultaneously
- Default-N confirms (`[y/N]`) between destructive phases

## Gate Irreversible Operations

For any irreversible or high-risk command — `rm -rf`, `chmod -R 777`, `curl | bash`, sudoers modification — use `AskUserQuestion` before running, whether via the hook or a generated script.

## Do NOT

- Pipe passwords into sudo (`echo pass | sudo`)
- Use `eval` in generated scripts — pass commands as arguments (`"$@"`)
- Assume a command succeeded without checking — if the hook denied after timeout, read the denial reason
