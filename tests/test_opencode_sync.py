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

Also covers PR #506 review fixes: `resolve()` routes an opus-tier dispatch
to `worker-opus` (or a `SPECIALIST_AGENTS` entry's own `<name>-opus` variant)
regardless of the original `agent_type`; `generate_specialist_opus_variants()`
generates those variants with the specialist's prompt preserved and safely
scoped orphan cleanup (`GENERATED_FILE_MARKER`-gated); `build_agent_config()`
only pins config.json entries for variants actually generated; and
`SPECIALIST_AGENTS` is cross-checked against `agent-routing.md`'s table.
"""

import json
import re
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


def test_uninstall_previous_home_override_targets_scratch_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_script()
    uninstall = module["uninstall_previous"]
    subprocess_module = module["subprocess"]
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return _fake_completed_process()

    monkeypatch.setattr(subprocess_module, "run", fake_run)
    scratch_home = tmp_path / "scratch-home"

    uninstall(home_override=scratch_home)

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[3:5] == ["uninstall", "claudefiles"]
    assert args[args.index("--cwd") + 1] == str(scratch_home)
    assert kwargs["env"]["HOME"] == str(scratch_home)


def test_generate_skill_commands_writes_only_selected_available_skills(
    tmp_path: Path,
) -> None:
    module = _load_script()
    generate = module["generate_skill_commands"]

    config_dir = tmp_path / "opencode"
    for name, opencode_command in (("mine-review", True), ("mine-debug", False)):
        skill_dir = config_dir / "skills" / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\nopencode-command: "
            f"{'true' if opencode_command else 'false'}\n---\n"
        )

    generated = generate(config_dir, dry_run=False)

    assert generated == ["mine-review"]
    wrapper = (config_dir / "commands" / "mine-review.md").read_text()
    assert "Load the `mine-review` skill using the native skill tool" in wrapper
    assert "$ARGUMENTS" in wrapper
    assert ".claude/skills" not in wrapper
    assert not (config_dir / "commands" / "mine-debug.md").exists()


def test_generate_skill_commands_prunes_owned_wrappers_but_preserves_commands(
    tmp_path: Path,
) -> None:
    module = _load_script()
    generate = module["generate_skill_commands"]

    config_dir = tmp_path / "opencode"
    commands_dir = config_dir / "commands"
    commands_dir.mkdir(parents=True)
    legacy_marker = module["LEGACY_SKILL_COMMAND_MARKER"]
    (commands_dir / "mine-debug.md").write_text(f"{legacy_marker}\nold wrapper\n")
    standalone = commands_dir / "mine-issues.md"
    standalone.write_text("---\ndescription: Deep-dive issues\n---\nactual workflow\n")

    generate(config_dir, dry_run=False)

    assert not (commands_dir / "mine-debug.md").exists()
    assert standalone.exists()
    assert "actual workflow" in standalone.read_text()


def test_generate_skill_commands_does_not_overwrite_non_generated_collision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_script()
    generate = module["generate_skill_commands"]

    config_dir = tmp_path / "opencode"
    skill_dir = config_dir / "skills" / "mine-review"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: mine-review\nopencode-command: true\n---\n"
    )
    commands_dir = config_dir / "commands"
    commands_dir.mkdir()
    command = commands_dir / "mine-review.md"
    command.write_text("hand-written command\n")

    generated = generate(config_dir, dry_run=False)

    assert generated == []
    assert command.read_text() == "hand-written command\n"
    assert "not overwriting non-generated command" in capsys.readouterr().err


def test_generate_skill_commands_skips_duplicate_frontmatter(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_script()
    generate = module["generate_skill_commands"]
    skill_dir = tmp_path / "opencode" / "skills" / "mine-review"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: mine-review\nopencode-command: true\nopencode-command: false\n---\n"
    )

    assert generate(tmp_path / "opencode", dry_run=False) == []
    assert "skipping invalid opencode-command frontmatter" in capsys.readouterr().err


def test_resolve_general_purpose_opus_routes_to_worker_opus() -> None:
    module = _load_script()
    resolve = module["resolve"]

    assert resolve("general-purpose", "opus") == ("worker-opus", None)


def test_resolve_specialist_opus_routes_to_own_variant_not_generic_worker() -> None:
    """An escalated retry ("Try again with stronger model") keeps the same
    executor `subagent_type` the original dispatch selected -- which may be
    a SPECIALIST_AGENTS entry (e.g. engineering-backend-developer), not
    general-purpose. Routing it to the generic worker-opus would reach Sol
    but silently drop the specialist's own prompt (FastAPI/Pydantic
    conventions, etc.) -- it must route to its own `<name>-opus` variant
    instead, which generate_specialist_opus_variants() generates with that
    prompt preserved.
    """
    module = _load_script()
    resolve = module["resolve"]

    assert resolve("engineering-backend-developer", "opus") == (
        "engineering-backend-developer-opus",
        None,
    )


def test_resolve_builtin_opus_routes_to_worker_opus_not_builtin_map() -> None:
    module = _load_script()
    resolve = module["resolve"]

    assert resolve("Explore", "opus") == ("worker-opus", None)


def test_specialist_agents_matches_agent_routing_table() -> None:
    """SPECIALIST_AGENTS (bin/opencode-sync) must list exactly the named
    executor agent types skills/mine-orchestrate/agent-routing.md's routing
    table can select, minus general-purpose (which routes through TIER_MAP,
    not SPECIALIST_AGENTS). agent-routing.md's own SYNC CHECKLIST documents
    updating SPECIALIST_AGENTS as a manual step when adding a specialist --
    this test is the runtime check backing that instruction, so a specialist
    added to one list and not the other fails here instead of silently
    falling back to the generic worker-opus on an escalated retry.
    """
    module = _load_script()
    specialist_agents = set(module["SPECIALIST_AGENTS"])

    routing_table = (
        REPO_ROOT / "skills" / "mine-orchestrate" / "agent-routing.md"
    ).read_text()
    row_re = re.compile(r"^\|.*\|\s*`([a-z][a-z0-9_-]*)`(?:, `model: \w+`)?\s*\|\s*$")
    routed_types = {
        match.group(1)
        for match in (row_re.match(line) for line in routing_table.splitlines())
        if match is not None
    }
    routed_types.discard("general-purpose")

    assert routed_types == specialist_agents


def test_build_agent_config_only_includes_actually_generated_variants() -> None:
    """build_agent_config() must take the actually-generated variant list, not
    re-derive it from SPECIALIST_AGENTS -- a specialist source file can be
    legitimately missing at sync time (generate_specialist_opus_variants()
    warns and skips it), and pinning a config.json entry for a name with no
    corresponding `<name>-opus.md` on disk would be a dead reference.
    """
    module = _load_script()
    build_agent_config = module["build_agent_config"]

    config = build_agent_config(["engineering-backend-developer-opus"])

    assert config["engineering-backend-developer-opus"] == {
        "model": "openai/gpt-5.6-sol",
        "effort": "high",
    }
    assert "engineering-frontend-developer-opus" not in config


def test_generate_specialist_opus_variants_copies_prompt_with_swapped_frontmatter(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_script()
    generate = module["generate_specialist_opus_variants"]
    specialist_agents = module["SPECIALIST_AGENTS"]
    generated_file_marker = module["GENERATED_FILE_MARKER"]
    name = specialist_agents[0]

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / f"{name}.md").write_text(
        f"---\nname: {name}\nmodel: openai/gpt-5.6-terra\neffort: medium\n"
        "description: A specialist.\n---\n\n# Specialist body\n\nDo the thing.\n"
    )

    generated = generate(agents_dir, dry_run=False)

    assert generated == [f"{name}-opus"]
    variant = (agents_dir / f"{name}-opus.md").read_text()
    assert f"name: {name}-opus" in variant
    assert "model: openai/gpt-5.6-sol" in variant
    assert "effort: medium" in variant
    assert "description: A specialist." in variant
    assert generated_file_marker in variant
    assert "# Specialist body" in variant
    assert "Do the thing." in variant

    warnings = capsys.readouterr().err
    for missing in specialist_agents[1:]:
        assert missing in warnings


def test_generate_specialist_opus_variants_removes_own_orphan_but_not_foreign_file(
    tmp_path: Path,
) -> None:
    """Orphan cleanup must only remove `*-opus.md` files this function itself
    wrote (marked with GENERATED_FILE_MARKER) -- `*-opus.md` is a generic
    suffix a user could plausibly reuse for their own hand-authored OpenCode
    subagent, unlike `worker-*.md` (a prefix namespace this repo exclusively
    owns). Pattern-matching the name alone, with no ownership check, would
    silently delete a file this function never wrote.
    """
    module = _load_script()
    generate = module["generate_specialist_opus_variants"]
    generated_file_marker = module["GENERATED_FILE_MARKER"]

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "worker-opus.md").write_text("---\nname: worker-opus\n---\n")
    (agents_dir / "foreign-hand-authored-opus.md").write_text(
        "---\nname: foreign-hand-authored-opus\n---\nA user's own subagent.\n"
    )
    (agents_dir / "renamed-specialist-opus.md").write_text(
        f"---\nname: renamed-specialist-opus\n---\n{generated_file_marker}\n"
    )

    generate(agents_dir, dry_run=False)

    assert (agents_dir / "worker-opus.md").exists()
    assert (agents_dir / "foreign-hand-authored-opus.md").exists()
    assert not (agents_dir / "renamed-specialist-opus.md").exists()


def test_rewrite_general_purpose_opus_dispatch_routes_to_worker_opus() -> None:
    """The opus TIER_MAP entry's `worker: None` used to make resolve() return
    bare `None` for this pairing, leaving `general-purpose` + `model: opus`
    dispatches (e.g. mine-orchestrate's "Try again with stronger model" retry)
    unrewritten -- so on synced OpenCode installs the retry silently stayed on
    the sonnet-equivalent worker instead of reaching Sol. worker-opus closes
    that gap.
    """
    module = _load_script()

    rewritten = module["rewrite_dispatches_prose"](
        "Launch subagent_type: general-purpose, model: opus for the retry.\n"
    )

    assert rewritten == "Launch subagent_type: worker-opus for the retry.\n"


def test_rewrite_model_less_builtin_subagent_type() -> None:
    module = _load_script()

    rewritten = module["rewrite_dispatches_prose"](
        "Launch subagent_type: Explore to inspect the code.\n"
    )

    assert rewritten == "Launch subagent_type: explore to inspect the code.\n"

    rewritten = module["rewrite_dispatches_prose"](
        "Launch subagent_type: Bash to inspect project history.\n"
    )

    assert rewritten == (
        "Launch subagent_type: worker-lightweight to inspect project history.\n"
    )
