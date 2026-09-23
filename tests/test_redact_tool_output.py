"""Integration tests for redact-tool-output.py (PostToolUse and
PostToolUseFailure: Read|Bash).

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


def _read_payload(
    content: str, num_lines: int | None = None, total_lines: int | None = None
) -> str:
    line_count = len(content.splitlines())
    return json.dumps(
        {
            "tool_name": "Read",
            "tool_input": {"file_path": "/home/user/.local/share/opencode/auth.json"},
            "tool_response": {
                "type": "text",
                "file": {
                    "content": content,
                    "numLines": num_lines if num_lines is not None else line_count,
                    "totalLines": total_lines
                    if total_lines is not None
                    else line_count,
                },
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

    def test_partial_read_preserves_original_total_lines(self):
        """Regression test: for an offset/limit Read, totalLines describes the
        whole source file and must not be overwritten with the returned
        chunk's line count — doing so falsely reports EOF and can stop the
        model from requesting the rest of the file."""
        stdin = _read_payload("line20\nline21\nline22\n", num_lines=3, total_lines=1000)
        result = run_hook(stdin)
        assert result.returncode == 0
        file_resp = json.loads(result.stdout)["hookSpecificOutput"][
            "updatedToolOutput"
        ]["file"]
        assert file_resp["numLines"] == 3
        assert file_resp["totalLines"] == 1000


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

    def test_conn_str_scan_stays_fast_on_long_scheme_free_text(self):
        """Regression test: _CONN_STR's scheme-prefix quantifier was
        unbounded, so a long run of scheme-charset text with no "://"
        anywhere (a minified file, a base64 blob) made the regex do O(n^2)
        backtracking — 50k chars took >5s, exceeding the hook's own 5000ms
        timeout in settings.json and causing the whole redaction pass (not
        just this one rule) to fail open on unrelated real secrets in the
        same output."""
        stdin = _bash_payload("a" * 50_000)
        result = run_hook(stdin)
        assert result.returncode == 0


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


class TestPrefixBoundaryAnchoring:
    """Regression tests: short vendor prefixes ("key-"/Mailgun, "re_"/Resend,
    "SK"/Twilio) are common substrings of ordinary identifiers, not just
    secret prefixes."""

    def test_redacts_real_mailgun_key(self):
        # No leading "KEY=" assignment on purpose: that shape is caught by
        # env_secret earlier in rule order, which would mask whether
        # mailgun_key itself actually fires — see the _MUST_CUT fixture note.
        stdin = _bash_payload(
            "rotating the mailgun key-3ax6xnjp29jd6fds4gc373sgvjxteol now"
        )
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)["hookSpecificOutput"]["updatedToolOutput"]
        assert "3ax6xnjp29jd6fds4gc373sgvjxteol" not in out["stdout"]
        assert "[REDACTED:mailgun_key]" in out["stdout"]

    def test_redacts_real_resend_key(self):
        # Same reasoning as the Mailgun case above: no "KEY=" assignment shape.
        stdin = _bash_payload(
            "rotating the resend re_123456789012345678901234567890 now"
        )
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)["hookSpecificOutput"]["updatedToolOutput"]
        assert "123456789012345678901234567890" not in out["stdout"]
        assert "[REDACTED:resend_key]" in out["stdout"]

    def test_leaves_monkey_patching_identifier_untouched(self):
        stdout = "monkey-patching-library is imported here\n"
        stdin = _bash_payload(stdout)
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)["hookSpecificOutput"]["updatedToolOutput"]
        assert out["stdout"] == stdout

    def test_leaves_future_annotations_identifier_untouched(self):
        stdout = "future_annotations_enabled = True\n"
        stdin = _bash_payload(stdout)
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)["hookSpecificOutput"]["updatedToolOutput"]
        assert out["stdout"] == stdout

    def test_leaves_non_mailgun_shaped_key_dash_token_untouched(self):
        stdout = "bumped key-rotation-v2 in the changelog\n"
        stdin = _bash_payload(stdout)
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)["hookSpecificOutput"]["updatedToolOutput"]
        assert out["stdout"] == stdout

    def test_redacts_bare_twilio_key(self):
        # Built via concatenation, not a literal — GitHub push protection
        # flags a bare "SK" + 32 hex chars string as a real Twilio key.
        fake_key = "SK" + "1234567890abcdef" * 2
        stdin = _bash_payload(f"{fake_key} printed to stdout")
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)["hookSpecificOutput"]["updatedToolOutput"]
        assert fake_key[2:] not in out["stdout"]
        assert "[REDACTED:twilio_key]" in out["stdout"]

    def test_leaves_ordinary_words_containing_sk_untouched(self):
        stdout = "TASK: review the DESK lamp before we MASK the wall\n"
        stdin = _bash_payload(stdout)
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)["hookSpecificOutput"]["updatedToolOutput"]
        assert out["stdout"] == stdout


class TestVendorPrefixCoverage:
    """Regression tests: these vendor formats were already known to
    scripts/hooks/secrets-check.sh but simply missing from _PREFIX, so a
    bare, unlabeled token of these shapes reached the model unredacted."""

    def test_redacts_bare_github_server_token(self):
        stdin = _bash_payload("ghs_AbCdEf0123456789ghijklmnopqrstuvwxyz printed")
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)["hookSpecificOutput"]["updatedToolOutput"]
        assert "AbCdEf0123456789ghijklmnopqrstuvwxyz" not in out["stdout"]
        assert "[REDACTED:" in out["stdout"]

    def test_redacts_bare_slack_refresh_token(self):
        stdin = _bash_payload(
            "xoxe-1-1234567890-1234567890123-abcdefghijklmnopqrstuvwxyz0123456789AB"
        )
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)["hookSpecificOutput"]["updatedToolOutput"]
        assert "abcdefghijklmnopqrstuvwxyz0123456789AB" not in out["stdout"]
        assert "[REDACTED:" in out["stdout"]


class TestQuotedAssignmentKeys:
    """Regression test: JSON/TOML's quoted keys ("access_token": "...") sit
    between the keyword and the separator, which previously blocked the
    assignment rule entirely — exactly the auth.json shape motivating this
    hook."""

    def test_redacts_quoted_json_access_token(self):
        stdin = _bash_payload(
            '{"access_token": "ya29.a0AfH6SMBnrandomlongvalue1234567890"}'
        )
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)["hookSpecificOutput"]["updatedToolOutput"]
        assert "ya29.a0AfH6SMBnrandomlongvalue1234567890" not in out["stdout"]
        assert "[REDACTED:assignment]" in out["stdout"]

    def test_redacts_quoted_json_password(self):
        stdin = _bash_payload('{"password": "correct-horse-battery-1234"}')
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)["hookSpecificOutput"]["updatedToolOutput"]
        assert "correct-horse-battery-1234" not in out["stdout"]
        assert "[REDACTED:assignment]" in out["stdout"]

    def test_redacts_quoted_json_credentials(self):
        stdin = _bash_payload('{"credentials": "AbCdEf0123456789ghijklmn"}')
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)["hookSpecificOutput"]["updatedToolOutput"]
        assert "AbCdEf0123456789ghijklmn" not in out["stdout"]
        assert "[REDACTED:secret_word]" in out["stdout"]

    def test_leaves_quoted_placeholder_value_untouched(self):
        stdout = "config = {'key': 'value', 'token': 'placeholder'}\n"
        stdin = _bash_payload(stdout)
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)["hookSpecificOutput"]["updatedToolOutput"]
        assert out["stdout"] == stdout


class TestPostToolUseFailure:
    """Regression test: redaction must apply to failed Bash calls too — a
    `curl -v`, a failed login, or a CLI error can echo a credential in the
    failure message just as easily as in a success stdout/stderr.

    PostToolUseFailure carries no `tool_response` — the failure detail is a
    top-level `error` string instead (confirmed against this repo's own
    fixture in tests/test_hooks.py's test_captures_failed_command, and the
    Claude Code hooks reference). An earlier version of this test invented a
    success-shaped `tool_response` for a failure event, which passed without
    ever exercising the real payload shape."""

    def test_redacts_secret_from_failed_bash_call_and_echoes_event_name(self):
        stdin = json.dumps(
            {
                "hook_event_name": "PostToolUseFailure",
                "tool_name": "Bash",
                "tool_input": {"command": "curl -v https://example.com"},
                "error": (
                    "curl: (6) Could not resolve host, Authorization: Bearer "
                    "ghp_AbCdEf0123456789ghijklmnopqrstuvwxyz"
                ),
            }
        )
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUseFailure"
        updated = out["hookSpecificOutput"]["updatedToolOutput"]
        assert "ghp_AbCdEf" not in updated
        assert "[REDACTED:" in updated

    def test_leaves_ordinary_failure_message_untouched(self):
        stdin = json.dumps(
            {
                "hook_event_name": "PostToolUseFailure",
                "tool_name": "Bash",
                "tool_input": {"command": "bad-command"},
                "error": "command not found: bad-command",
            }
        )
        result = run_hook(stdin)
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["hookSpecificOutput"]["updatedToolOutput"] == (
            "command not found: bad-command"
        )


class TestMalformedConfig:
    """Regression test: a broken redact.toml must fall back to defaults, not
    crash the hook and silently expose secrets."""

    def test_rule_as_table_instead_of_array_falls_back_without_crashing(self, tmp_path):
        config_path = tmp_path / "redact.toml"
        config_path.write_text('[rule]\nname = "custom"\npattern = "x"\n')
        stdin = _bash_payload("token=ghp_AbCdEf0123456789ghijklmnopqrstuvwxyz")
        result = run_hook(stdin, extra_env={"REDACT_CONFIG": str(config_path)})
        assert result.returncode == 0
        out = json.loads(result.stdout)["hookSpecificOutput"]["updatedToolOutput"]
        assert "ghp_AbCdEf" not in out["stdout"]
        assert "[REDACTED:" in out["stdout"]

    def test_scalar_enable_falls_back_without_crashing(self, tmp_path):
        config_path = tmp_path / "redact.toml"
        config_path.write_text('enable = "entropy"\n')
        stdin = _bash_payload("token=ghp_AbCdEf0123456789ghijklmnopqrstuvwxyz")
        result = run_hook(stdin, extra_env={"REDACT_CONFIG": str(config_path)})
        assert result.returncode == 0
        out = json.loads(result.stdout)["hookSpecificOutput"]["updatedToolOutput"]
        assert "ghp_AbCdEf" not in out["stdout"]
        assert "[REDACTED:" in out["stdout"]
