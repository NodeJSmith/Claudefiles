# Sudo Operations

Claude Code cannot run `sudo` locally: there is no TTY for the password prompt, so a local `sudo` cannot authenticate. Don't rely on cached credentials, and don't expect a hook or wrapper to handle the prompt.

## Local sudo

Don't run a local `sudo` in a Bash call and hope cached credentials exist. Pick one:

- **A command or two:** tell the user the exact command and ask them to run it in their own terminal (in the Claude Code CLI, typing `! sudo <cmd>` runs it and lands the output in the conversation). Wait for the result before continuing.
- **Anything longer, phased, or needing a reviewable artifact:** generate a script (see below) and tell the user the exact run command.

Other escalation mechanisms (`pkexec`, `su -c`) have the same no-TTY problem; use the same two options.

## Remote sudo works normally

`ssh host 'sudo ...'` runs `sudo` on the remote host, which has its own sudoers policy and needs no local credentials. Run it directly, no special prefix or workaround. If the remote host does require a password, the command fails with a prompt error; treat that as a remote configuration issue and report it.

## Script Generation

Write the script via `get-tmp-filename`, tell the user the exact run command, and read the log afterward.

Key rules for generated scripts:
- `set -euo pipefail` and `trap` for the log path on exit
- `install -m 600 /dev/null "$LOG_FILE"` — restrictive permissions before writing
- Use `"$@"` for command execution, never `eval`
- `tee -a` so output appears on terminal and in log simultaneously
- Default-N confirms (`[y/N]`) between destructive phases

## Gate Irreversible Operations

For any irreversible or high-risk command — `rm -rf`, `chmod -R 777`, `curl | bash`, sudoers modification — use `AskUserQuestion` before running or handing it to the user, whether directly or via a generated script.

## Do NOT

- Pipe passwords into sudo (`echo pass | sudo`)
- Use `eval` in generated scripts — pass commands as arguments (`"$@"`)
- Assume a command succeeded without checking its output or log
