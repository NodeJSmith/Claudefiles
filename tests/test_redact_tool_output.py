"""Integration tests for redact-tool-output.py (PostToolUse: Read|Bash).

Verifies the hook end-to-end against real tool_response shapes rather than only
trusting the script's own --self-check — a hook that's wired up but never
actually fires on a real tool call is a documented real-world failure mode
(cooneycw/claude-power-pack#1206), so this exercises the same subprocess path
Claude Code uses, not just the redaction function in isolation.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
REDACT_HOOK = REPO_ROOT / "scripts" / "hooks" / "redact-tool-output.py"


def run_hook(stdin: str, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = extra_env.copy() if extra_env else {}
    import os

    full_env = os.environ.copy()
    full_env.update(env)
    return subprocess.run(
        [sys.executable, str(REDACT_HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        env=full_env,
        timeout=5,
        check=False,
    )


def _read_payload(content: str) -> str:
    return json.dumps(
        {
            "tool_name": "Read",
            "tool_input": {"file_path": "/home/user/.local/share/opencode/auth.json"},
            "tool_response": {
                "type": "text",
                "file": {"content": content, "numLines": 1, "totalLines": 1},
            },
        }
    )


def _bash_payload(stdout: str, stderr: str = "") -> str:
    return json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": {"command": "cat auth.json"},
            "tool_response": {"stdout": stdout, "stderr": stderr, "status": 0},
        }
    )


class TestSelfCheck:
    def test_self_check_passes(self):
        result = subprocess.run(
            [sys.executable, str(REDACT_HOOK), "--self-check"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0, result.stdout
        assert "0 failures" in result.stdout


class TestReadRedaction:
    def test_redacts_openai_style_token_from_file_content(self):
        stdin = _read_payload("access_token=ghp_AbCdEf0123456789ghijklmnopqrstuvwxyz")
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)
        content = out["hookSpecificOutput"]["updatedToolOutput"]["file"]["content"]
        assert "ghp_AbCdEf" not in content
        assert "[REDACTED:" in content

    def test_leaves_ordinary_file_content_untouched(self):
        clean = "def main():\n    print('hello world')\n"
        stdin = _read_payload(clean)
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)
        content = out["hookSpecificOutput"]["updatedToolOutput"]["file"]["content"]
        assert content == clean

    def test_num_lines_matches_actual_line_count(self):
        """Regression test: numLines/totalLines must equal the real physical
        line count, not count + 1."""
        stdin = _read_payload("line1\nline2\nline3\n")
        result = run_hook(stdin)
        assert result.returncode == 0
        file_resp = json.loads(result.stdout)["hookSpecificOutput"][
            "updatedToolOutput"
        ]["file"]
        assert file_resp["numLines"] == 3
        assert file_resp["totalLines"] == 3


class TestBashRedaction:
    def test_redacts_secret_from_docker_compose_config_style_stdout(self):
        stdout = (
            "services:\n  bot:\n    environment:\n      - API_TOKEN=hunter2xyz789\n"
        )
        stdin = _bash_payload(stdout)
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)
        redacted_stdout = out["hookSpecificOutput"]["updatedToolOutput"]["stdout"]
        assert "hunter2xyz789" not in redacted_stdout
        assert "[REDACTED:" in redacted_stdout

    def test_leaves_ordinary_stdout_untouched(self):
        stdout = "total 0\ndrwxr-xr-x 2 user user 4096 Jan 1 00:00 .\n"
        stdin = _bash_payload(stdout)
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["hookSpecificOutput"]["updatedToolOutput"]["stdout"] == stdout

    def test_redacts_secret_in_stderr_independently_of_stdout(self):
        """Regression test: the upstream script joined stdout+stderr into one
        string, redacted it once, and only ever wrote the result back into
        `stdout` — a secret in stderr (curl -v auth header, failed-login
        password, a CLI error echoing a token) passed through completely
        unredacted. stderr must be redacted and written back to its own field.
        """
        stdin = _bash_payload(
            stdout="ok output here",
            stderr="Authorization: Basic dXNlcjpzZWNyZXRwYXNzd29yZA==",
        )
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)["hookSpecificOutput"]["updatedToolOutput"]
        assert out["stdout"] == "ok output here"
        assert "dXNlcjpzZWNyZXRwYXNzd29yZA==" not in out["stderr"]
        assert "[REDACTED:" in out["stderr"]


class TestUnrecognizedShapeIsLeftAlone:
    def test_dict_response_without_file_or_stdout_key_passes_through_unchanged(self):
        """Regression test for the upstream bug this hook fixed: a dict-shaped
        tool_response in neither Read's nor Bash's shape must never be collapsed
        into a bare string — that would corrupt output for any tool whose schema
        this hook doesn't understand.
        """
        resp = {"filePath": "/tmp/x.py", "success": True}
        stdin = json.dumps(
            {"tool_name": "SomeOtherTool", "tool_input": {}, "tool_response": resp}
        )
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["hookSpecificOutput"]["updatedToolOutput"] == resp


class TestSkipTools:
    def test_skips_configured_tools_without_modification(self):
        stdin = json.dumps(
            {
                "tool_name": "WebFetch",
                "tool_input": {"url": "https://example.com"},
                "tool_response": "token=ghp_AbCdEf0123456789ghijklmnopqrstuvwxyz",
            }
        )
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["hookSpecificOutput"]["updatedToolOutput"] == (
            "token=ghp_AbCdEf0123456789ghijklmnopqrstuvwxyz"
        )


class TestMalformedInput:
    def test_empty_stdin_does_not_crash(self):
        result = run_hook("")
        assert result.returncode == 0
        assert result.stdout == ""

    def test_non_json_stdin_does_not_crash(self):
        result = run_hook("not json at all")
        assert result.returncode == 0
        assert result.stdout == ""
