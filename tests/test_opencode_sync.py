"""Tests for bin/opencode-sync.

Covers three PR #503 review fixes:
- `_strip_jsonc_comments()` now strips `/* */` block comments (not just `//`
  line comments), so `check_collisions()` no longer silently skips the FR#13
  shadowing warning when opencode.jsonc has a block comment.
- `stage_config()` creates `rules/common/` before writing the compat rule,
  instead of raising FileNotFoundError when the source tree lacks it.
- `run_opkg()` accepts an optional `home_override` that redirects the opkg
  install to a scratch HOME (via `--cwd` + the `HOME` env var) instead of
  the real one, and always installs for real (never appends `--dry-run`) in
  that mode -- this is what lets `--dry-run` preview the staged content
  instead of scanning stale output from the last real sync.
"""

import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "bin" / "opencode-sync"


def _load_script() -> dict:
    return runpy.run_path(str(SCRIPT))


def test_strip_jsonc_comments_removes_block_comment() -> None:
    module = _load_script()
    strip = module["_strip_jsonc_comments"]

    text = '{\n  /* a block comment */\n  "agent": {}\n}\n'
    stripped = strip(text)

    assert "/*" not in stripped
    assert "*/" not in stripped
    assert json.loads(stripped) == {"agent": {}}


def test_strip_jsonc_comments_block_comment_with_string_lookalikes_not_corrupted() -> (
    None
):
    """A block comment's own contents (quotes, `//`) must not leak into the
    parser's string/comment tracking -- and a genuine JSON string containing
    `//` right after the comment must survive untouched.
    """
    module = _load_script()
    strip = module["_strip_jsonc_comments"]

    text = (
        "{\n"
        '  /* see https://example.com and "quoted text" // not a real comment */\n'
        '  "$schema": "https://opencode.ai/config.json",\n'
        '  "agent": {"foo": "bar"}\n'
        "}\n"
    )
    stripped = strip(text)

    data = json.loads(stripped)
    assert data["$schema"] == "https://opencode.ai/config.json"
    assert data["agent"] == {"foo": "bar"}


def test_strip_jsonc_comments_preserves_slash_star_inside_real_string() -> None:
    """A `/*`/`*/` sequence inside an actual JSON string value (not a
    comment) must not be treated as a block-comment delimiter.
    """
    module = _load_script()
    strip = module["_strip_jsonc_comments"]

    text = '{"note": "use /* not a comment */ here"}'
    stripped = strip(text)

    assert json.loads(stripped) == {"note": "use /* not a comment */ here"}


def test_check_collisions_warns_when_jsonc_has_block_comment(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Before the fix, a block comment made json.loads() raise inside
    check_collisions(), which silently returned in non-verbose mode -- so a
    real `agent` key collision went unwarned. After the fix the file parses
    and the FR#13 warning fires.
    """
    module = _load_script()
    check_collisions = module["check_collisions"]

    config_dir = tmp_path / "opencode-config"
    config_dir.mkdir()
    (config_dir / "opencode.jsonc").write_text(
        "{\n"
        "  /* stale pin from the July 30 quick-fix, never cleaned up */\n"
        '  "agent": {\n'
        '    "some-agent": "opencode/some-model"\n'
        "  }\n"
        "}\n"
    )

    check_collisions(config_dir, {"some-agent"}, verbose=False)

    captured = capsys.readouterr()
    assert "some-agent" in captured.err
    assert "WARNING" in captured.err


def test_check_collisions_no_warning_without_collision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_script()
    check_collisions = module["check_collisions"]

    config_dir = tmp_path / "opencode-config"
    config_dir.mkdir()
    (config_dir / "opencode.jsonc").write_text(
        '{\n  /* nothing shadowed here */\n  "agent": {}\n}\n'
    )

    check_collisions(config_dir, {"unrelated-agent"}, verbose=False)

    captured = capsys.readouterr()
    assert captured.err == ""


def test_stage_config_creates_missing_rules_common_dir(tmp_path: Path) -> None:
    """Before the fix, a source tree with no rules/common/ made
    compat_path.write_text() raise FileNotFoundError. After the fix,
    stage_config() creates the directory first.
    """
    module = _load_script()
    stage_config = module["stage_config"]

    claudefiles = tmp_path / "claudefiles"
    claudefiles.mkdir()
    (claudefiles / "README.md").write_text("placeholder\n")
    # Deliberately no "rules" directory at all.

    tmpdir = tmp_path / "staging"
    tmpdir.mkdir()

    staged = stage_config(claudefiles, tmpdir)

    compat_path = staged / "rules" / "common" / "opencode-compat.md"
    assert compat_path.is_file()
    assert "OpenCode Compatibility" in compat_path.read_text()


def _fake_completed_process(stdout: str = "ok\n") -> SimpleNamespace:
    return SimpleNamespace(returncode=0, stdout=stdout, stderr="")


def test_run_opkg_home_override_redirects_cwd_and_env_and_omits_dry_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With `home_override` set, the install must target the scratch home
    (via both `--cwd` and the `HOME` env var passed to subprocess.run) and
    must never pass `--dry-run` -- the scratch dir is disposable, so the
    install always runs for real regardless of the `dry_run` argument. This
    is the mechanism the dry-run preview relies on to see accurate staged
    content instead of scanning the last real sync's stale output.
    """
    module = _load_script()
    run_opkg = module["run_opkg"]
    subprocess_module = module["subprocess"]

    scratch_home = tmp_path / "scratch-home"
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return _fake_completed_process()

    monkeypatch.setattr(subprocess_module, "run", fake_run)

    # dry_run=True is passed deliberately -- home_override must still
    # suppress --dry-run, proving the two controls are independent.
    run_opkg(
        tmp_path / "staged",
        dry_run=True,
        verbose=False,
        home_override=scratch_home,
    )

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert "--dry-run" not in args
    cwd_index = args.index("--cwd")
    assert args[cwd_index + 1] == str(scratch_home)
    assert kwargs["env"]["HOME"] == str(scratch_home)


def test_run_opkg_without_home_override_matches_prior_behavior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression guard: with `home_override` omitted (the default), the
    call must be identical to before the fix -- `--cwd` is the real home,
    no `env=` override is applied (subprocess inherits the ambient
    environment), and `--dry-run` is appended solely based on `dry_run`.
    """
    module = _load_script()
    run_opkg = module["run_opkg"]
    subprocess_module = module["subprocess"]
    real_home = module["Path"].home()

    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return _fake_completed_process()

    monkeypatch.setattr(subprocess_module, "run", fake_run)

    run_opkg(tmp_path / "staged", dry_run=True, verbose=False)
    run_opkg(tmp_path / "staged", dry_run=False, verbose=False)

    assert len(calls) == 2

    dry_run_args, dry_run_kwargs = calls[0]
    assert "--dry-run" in dry_run_args
    cwd_index = dry_run_args.index("--cwd")
    assert dry_run_args[cwd_index + 1] == str(real_home)
    assert dry_run_kwargs["env"] is None

    real_run_args, real_run_kwargs = calls[1]
    assert "--dry-run" not in real_run_args
    cwd_index = real_run_args.index("--cwd")
    assert real_run_args[cwd_index + 1] == str(real_home)
    assert real_run_kwargs["env"] is None
