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


def _write_specialist_source(agents_dir: Path, name: str) -> None:
    """Write a minimal specialist agent file used as generate_specialist_
    opus_variants()'s input fixture across multiple tests -- kept in one
    place so a fourth caller doesn't need its own copy of the frontmatter.

    Carries `variant:`, not Claude's `effort:`: process_agent_frontmatter()
    runs first in the real pipeline and has already rewritten that key by the
    time generate_specialist_opus_variants() reads the file.
    """
    (agents_dir / f"{name}.md").write_text(
        f"---\nname: {name}\nmodel: openai/gpt-5.6-terra\nvariant: medium\n"
        "description: A specialist.\n---\n\n# Specialist body\n\nDo the thing.\n"
    )


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
        "model": module["TIER_MAP"]["opus"]["model"],
        "variant": module["TIER_MAP"]["opus"]["variant"],
    }
    assert "engineering-frontend-developer-opus" not in config


def test_generate_config_points_instructions_at_synced_rules(tmp_path: Path) -> None:
    """Rules that opkg puts on disk are inert unless `instructions` names them.

    OpenCode's only other global instruction source is the first existing of
    `[<config>/AGENTS.md, ~/.claude/CLAUDE.md]`; nothing globs `<config>/rules/`.
    """
    module = _load_script()

    content = module["generate_config"](
        tmp_path, dry_run=False, specialist_opus_variants=[]
    )
    config = json.loads(content)

    assert config["instructions"] == [str(tmp_path / "rules/common/*.md")]


def test_build_instructions_never_uses_recursive_glob() -> None:
    """For an absolute pattern OpenCode globs `basename` inside `dirname` and
    does not recurse, so a `**` entry matches nothing -- silently, which is
    indistinguishable from having no rules at all.
    """
    module = _load_script()

    for entry in module["build_instructions"](Path("/tmp/oc")):
        assert "**" not in entry, f"{entry} will silently match nothing"
        assert entry.endswith("*.md")


def test_check_instruction_globs_flags_uncovered_rules_directory(
    tmp_path: Path,
) -> None:
    """A new rules subdirectory that INSTRUCTION_DIRS doesn't cover must fail
    the lint rather than shipping rules nothing ever loads.
    """
    module = _load_script()
    covered = tmp_path / "rules" / "common"
    covered.mkdir(parents=True)
    (covered / "a.md").write_text("# covered\n")
    uncovered = tmp_path / "rules" / "personal"
    uncovered.mkdir()
    (uncovered / "b.md").write_text("# uncovered\n")

    errors = module["check_instruction_globs"](tmp_path)

    assert len(errors) == 1
    assert "rules/personal" in errors[0]
    assert "INSTRUCTION_DIRS" in errors[0]


def test_check_instruction_globs_clean_when_every_rules_dir_covered(
    tmp_path: Path,
) -> None:
    module = _load_script()
    covered = tmp_path / "rules" / "common"
    covered.mkdir(parents=True)
    (covered / "a.md").write_text("# covered\n")

    assert module["check_instruction_globs"](tmp_path) == []


def test_check_instruction_globs_ignores_directory_with_no_rules(
    tmp_path: Path,
) -> None:
    """An empty or purely structural directory has nothing to load, so
    flagging it would fail syncs over a non-problem.
    """
    module = _load_script()
    (tmp_path / "rules" / "common").mkdir(parents=True)
    (tmp_path / "rules" / "scratch").mkdir()

    assert module["check_instruction_globs"](tmp_path) == []


def _write_rule(path: Path, tool_line: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = f"---\n{tool_line}\n---\n" if tool_line else ""
    path.write_text(f"{frontmatter}# {path.stem}\n")


def test_stage_config_drops_only_excluded_rules(tmp_path: Path) -> None:
    """Include is the default: OPENCODE_COMPAT_RULE translates Claude-only
    references, so only rules that are actively wrong for OpenCode are
    withheld. Deriving this from `tool:` frontmatter instead excluded seven
    rules OpenCode wants -- that marker answers "does this go to Antigravity?"
    """
    module = _load_script()

    claudefiles = tmp_path / "claudefiles"
    rules = claudefiles / "rules" / "common"
    # Marked harness-only for Antigravity's benefit, but wanted by OpenCode.
    _write_rule(rules / "git-workflow.md", "tool: claude  # harness-only: agents")
    _write_rule(rules / "capabilities-core.md", "tool: claude  # harness-only: skills")
    _write_rule(rules / "performance.md", "tool: claude  # harness-only: registry")
    _write_rule(rules / "sudo.md", "tool: claude  # harness-only: hook")
    _write_rule(rules / "tmux.md", "tool: claude  # harness-only: helper")

    tmpdir = tmp_path / "staging"
    tmpdir.mkdir()
    staged = module["stage_config"](claudefiles, tmpdir)

    staged_rules = staged / "rules" / "common"
    assert (staged_rules / "git-workflow.md").is_file()
    assert (staged_rules / "capabilities-core.md").is_file()
    for excluded in ("performance.md", "sudo.md", "tmux.md"):
        assert not (staged_rules / excluded).exists()
    # The compat rule is written after exclusion and must survive it.
    assert (staged_rules / "opencode-compat.md").is_file()


def test_opencode_marked_rule_is_never_excluded(tmp_path: Path) -> None:
    """A rule explicitly marked `tool: opencode` -- as the generated compat
    rule is -- must sync. The frontmatter-derived filter dropped exactly this.
    """
    module = _load_script()

    claudefiles = tmp_path / "claudefiles"
    _write_rule(claudefiles / "rules" / "common" / "compat-ish.md", "tool: opencode")

    tmpdir = tmp_path / "staging"
    tmpdir.mkdir()
    staged = module["stage_config"](claudefiles, tmpdir)

    assert (staged / "rules" / "common" / "compat-ish.md").is_file()


def test_real_repo_stages_every_rule_but_the_excluded(tmp_path: Path) -> None:
    """Guards the actual repo: exactly OPENCODE_EXCLUDED_RULES is withheld."""
    module = _load_script()
    repo = Path(__file__).resolve().parent.parent

    tmpdir = tmp_path / "staging"
    tmpdir.mkdir()
    staged = module["stage_config"](repo, tmpdir)

    excluded = set(module["OPENCODE_EXCLUDED_RULES"])
    for source in sorted((repo / "rules").rglob("*.md")):
        relative = source.relative_to(repo / "rules").as_posix()
        staged_file = staged / "rules" / relative
        if relative in excluded:
            assert not staged_file.exists(), f"{relative} should not sync"
        else:
            assert staged_file.is_file(), f"{relative} should sync but did not"


def test_apply_rule_exclusions_reports_stale_entry(tmp_path: Path) -> None:
    """A renamed rule silently starts syncing unless the stale entry surfaces."""
    module = _load_script()

    rules = tmp_path / "rules" / "common"
    _write_rule(rules / "sudo.md", "tool: claude")

    missing = module["apply_rule_exclusions"](tmp_path / "rules")

    assert not (rules / "sudo.md").exists()
    assert "common/performance.md" in missing
    assert "common/tmux.md" in missing


def test_check_source_gate_flags_stale_exclusion(tmp_path: Path) -> None:
    """The pre-commit gate fails on an exclusion entry matching no file."""
    module = _load_script()

    claudefiles = tmp_path / "claudefiles"
    (claudefiles / "agents").mkdir(parents=True)
    (claudefiles / "agents" / "a.md").write_text("---\nmodel: sonnet\n---\n\nbody\n")
    _write_rule(claudefiles / "rules" / "common" / "keeps.md", "tool: claude")

    errors, _ = module["check_source_dispatch_patterns"](claudefiles)

    assert any("OPENCODE_EXCLUDED_RULES" in e for e in errors)


def test_check_source_gate_sees_uncovered_rules_directory(tmp_path: Path) -> None:
    """The `--check-source` pre-commit gate must be able to fail on an
    uncovered rules directory. It stages only skills/commands/agents, so
    before this fix check_instruction_globs() short-circuited on the missing
    rules/ and the gate reported clean no matter what.
    """
    module = _load_script()

    claudefiles = tmp_path / "claudefiles"
    (claudefiles / "skills").mkdir(parents=True)
    (claudefiles / "agents").mkdir()
    (claudefiles / "agents" / "a.md").write_text("---\nmodel: sonnet\n---\n\nbody\n")
    _write_rule(
        claudefiles / "rules" / "common" / "covered.md", "tool: claude, antigravity"
    )
    _write_rule(
        claudefiles / "rules" / "personal" / "uncovered.md",
        "tool: claude, antigravity",
    )

    errors, _ = module["check_source_dispatch_patterns"](claudefiles)

    glob_errors = [e for e in errors if "instructions` glob" in e]
    assert len(glob_errors) == 1, f"gate did not flag the uncovered dir: {errors}"
    assert "rules/personal" in glob_errors[0]


def test_check_source_gate_judges_the_tree_that_ships(tmp_path: Path) -> None:
    """A rules directory left empty by the exclusions needs no `instructions`
    glob, so the gate must not demand one -- it has to judge the same tree
    stage_config() produces, not the raw source.
    """
    module = _load_script()

    claudefiles = tmp_path / "claudefiles"
    (claudefiles / "agents").mkdir(parents=True)
    (claudefiles / "agents" / "a.md").write_text("---\nmodel: sonnet\n---\n\nbody\n")
    for relative in module["OPENCODE_EXCLUDED_RULES"]:
        _write_rule(claudefiles / "rules" / relative, "tool: claude")

    errors, _ = module["check_source_dispatch_patterns"](claudefiles)

    assert [e for e in errors if "instructions` glob" in e] == []


def test_check_variant_names_flags_unresolvable_agent_variant(
    tmp_path: Path,
) -> None:
    """An unknown `variant:` resolves to nothing and drops the agent to the
    provider default -- the same silent failure as the old `effort` key, so it
    must fail the lint rather than only a test.
    """
    module = _load_script()

    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "good.md").write_text("---\nmodel: x\nvariant: high\n---\n\nbody\n")
    (agents / "bad.md").write_text("---\nmodel: x\nvariant: highest\n---\n\nbody\n")

    errors = module["check_variant_names"](tmp_path)

    assert len(errors) == 1
    assert "bad.md" in errors[0]
    assert "highest" in errors[0]


def test_check_variant_names_clean_on_real_tier_map(tmp_path: Path) -> None:
    module = _load_script()

    assert module["check_variant_names"](tmp_path) == []


def test_check_variant_names_flags_agent_declaring_no_variant(
    tmp_path: Path,
) -> None:
    """An agent with no `variant:` anywhere falls back to the provider default
    just as silently as one with a misspelled name -- checking only
    invalid-but-present names would leave the original `effort` bug reachable
    by simply dropping the key.
    """
    module = _load_script()

    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "silent.md").write_text("---\nmodel: x\n---\n\nbody\n")

    errors = module["check_variant_names"](tmp_path)

    assert len(errors) == 1
    assert "silent.md" in errors[0]
    assert "no `variant:`" in errors[0]


def test_check_variant_names_ignores_frontmatter_less_markdown(
    tmp_path: Path,
) -> None:
    """A .md file with no frontmatter isn't an agent definition, so the
    missing-variant check must skip it rather than claim a README "runs at the
    provider default". process_agent_frontmatter() already skips these; the
    lint has to agree, or an ordinary `agents/README.md` fails the blocking
    --check-source gate and every sync against the live config directory.
    """
    module = _load_script()

    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "README.md").write_text("# Agents directory\n\nconventions doc\n")

    assert module["check_variant_names"](tmp_path) == []


def test_check_variant_names_accepts_frontmatter_gap_pinned_by_config_json(
    tmp_path: Path,
) -> None:
    """Worker agents and TIER_MAP builtins carry their variant in config.json,
    not frontmatter, so the missing-variant check must consult it before
    failing -- otherwise every sync errors on the workers it just generated.
    """
    module = _load_script()

    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "worker-standard.md").write_text("---\nmodel: x\n---\n\nbody\n")
    (tmp_path / "config.json").write_text(
        json.dumps({"agent": {"worker-standard": {"model": "x", "variant": "high"}}})
    )

    assert module["check_variant_names"](tmp_path) == []


def test_check_variant_names_flags_unresolvable_config_json_variant(
    tmp_path: Path,
) -> None:
    """A config.json pin is only a rescue when OpenCode can resolve it."""
    module = _load_script()

    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "worker-standard.md").write_text("---\nmodel: x\n---\n\nbody\n")
    (tmp_path / "config.json").write_text(
        json.dumps({"agent": {"worker-standard": {"model": "x", "variant": "turbo"}}})
    )

    errors = module["check_variant_names"](tmp_path)

    assert len(errors) == 1
    assert "turbo" in errors[0]


def test_run_lint_surfaces_variant_errors(tmp_path: Path) -> None:
    """check_variant_names() must be wired into run_lint(), not merely defined
    -- OPENCODE_VARIANTS previously documented a guard only pytest enforced.
    """
    module = _load_script()

    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "bad.md").write_text("---\nmodel: x\nvariant: turbo\n---\n\nbody\n")

    errors, _ = module["run_lint"](tmp_path)

    assert any("turbo" in e for e in errors)


def test_tier_map_variants_are_names_opencode_resolves() -> None:
    """Every TIER_MAP `variant` must be a name OpenCode can resolve.

    Agent-level variant resolution drops any name missing from the model's
    synthesized `variants` map without warning, so a typo here reproduces the
    exact bug the `effort` -> `variant` rename fixed: config that looks
    correct while every subagent silently runs at the provider default.
    """
    module = _load_script()

    for tier_name, tier in module["TIER_MAP"].items():
        assert tier["variant"] in module["OPENCODE_VARIANTS"], (
            f"TIER_MAP[{tier_name!r}]['variant'] = {tier['variant']!r} is not a "
            "reasoning-effort name OpenCode accepts"
        )


def test_build_agent_config_never_emits_claude_effort_key() -> None:
    """`effort` is Claude Code's key. OpenCode's AgentConfig has no such
    field and does not reject unknown ones, so emitting it is a silent no-op
    that leaves every agent at the provider's default reasoning effort.
    """
    module = _load_script()

    config = module["build_agent_config"](["engineering-backend-developer-opus"])

    assert config, "expected at least one pinned agent entry"
    for name, entry in config.items():
        assert "effort" not in entry, f"{name} still pins the ignored `effort` key"
        assert entry["variant"] in module["OPENCODE_VARIANTS"]
        # A variant only applies when the agent's own model is the resolved
        # one, so the two must always ship together.
        assert entry["model"], f"{name} pins a variant with no sibling model"


def test_process_agent_frontmatter_rewrites_effort_to_tier_variant(
    tmp_path: Path,
) -> None:
    """Claude's `effort:` becomes OpenCode's `variant:`, valued from the tier
    the `model:` line names -- the same way the tier supplies the model ID.
    """
    module = _load_script()
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "reviewer.md").write_text(
        "---\nname: reviewer\nmodel: sonnet\neffort: high\n"
        "color: blue\ndescription: A reviewer.\n---\n\n# Body\n"
    )

    modified = module["process_agent_frontmatter"](agents_dir, dry_run=False)

    result = (agents_dir / "reviewer.md").read_text()
    sonnet = module["TIER_MAP"]["sonnet"]
    assert modified == 1
    assert f"variant: {sonnet['variant']}\n" in result
    assert "effort:" not in result
    assert f"model: {sonnet['model']}\n" in result
    assert "color:" not in result
    assert "# Body" in result


def test_process_agent_frontmatter_rewrites_effort_declared_before_model(
    tmp_path: Path,
) -> None:
    """The tier is resolved in its own pass, so an `effort:` line above the
    `model:` line still picks up the right variant instead of being dropped.
    """
    module = _load_script()
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "reviewer.md").write_text(
        "---\neffort: high\nname: reviewer\nmodel: haiku\n---\n\n# Body\n"
    )

    module["process_agent_frontmatter"](agents_dir, dry_run=False)

    result = (agents_dir / "reviewer.md").read_text()
    assert f"variant: {module['TIER_MAP']['haiku']['variant']}\n" in result
    assert "effort:" not in result


def test_process_agent_frontmatter_drops_unresolvable_effort_with_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no tier-resolvable `model:`, the intended variant is unknowable.

    Passing `effort:` through would leave a key OpenCode ignores while
    implying a reasoning level the agent isn't getting -- the failure mode
    this whole rename exists to remove. Drop it and say so.
    """
    module = _load_script()
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "orphan.md").write_text(
        "---\nname: orphan\nmodel: openai/gpt-5.6-terra\neffort: high\n---\n\n# Body\n"
    )

    module["process_agent_frontmatter"](agents_dir, dry_run=False)

    result = (agents_dir / "orphan.md").read_text()
    assert "effort:" not in result
    assert "variant:" not in result
    assert "orphan.md" in capsys.readouterr().err


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
    _write_specialist_source(agents_dir, name)

    generated = generate(agents_dir, dry_run=False)

    assert generated == [f"{name}-opus"]
    variant = (agents_dir / f"{name}-opus.md").read_text()
    assert f"name: {name}-opus" in variant
    opus_model = module["TIER_MAP"]["opus"]["model"]
    assert f"model: {opus_model}" in variant
    # The variant exists to escalate reasoning depth along with the model --
    # copying the base specialist's `variant: medium` verbatim would silently
    # cap it below the opus tier's reasoning effort, defeating the escalation.
    opus_variant = module["TIER_MAP"]["opus"]["variant"]
    assert f"variant: {opus_variant}" in variant
    assert "variant: medium" not in variant
    assert "description: A specialist." in variant
    assert generated_file_marker in variant
    assert "# Specialist body" in variant
    assert "Do the thing." in variant

    warnings = capsys.readouterr().err
    for missing in specialist_agents[1:]:
        assert missing in warnings


def test_generate_specialist_opus_variants_skips_foreign_file_at_target_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The orphan-cleanup loop already protects a hand-authored `<name>-opus.md`
    from deletion when its base specialist has no source (see the orphan test
    below) -- but that protection is separate from the write step. Without an
    equal ownership check at write time, a hand-authored file that collides by
    name with a *current* specialist's variant would be silently destroyed on
    every sync, since the write is otherwise unconditional.
    """
    module = _load_script()
    generate = module["generate_specialist_opus_variants"]
    specialist_agents = module["SPECIALIST_AGENTS"]
    name = specialist_agents[0]

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    _write_specialist_source(agents_dir, name)
    foreign_content = "---\nname: hand-authored\n---\nA user's own subagent.\n"
    (agents_dir / f"{name}-opus.md").write_text(foreign_content)

    generated = generate(agents_dir, dry_run=False)

    assert generated == []
    assert (agents_dir / f"{name}-opus.md").read_text() == foreign_content
    warnings = capsys.readouterr().err
    assert f"{name}-opus.md" in warnings
    assert "hand-authored" in warnings.lower()


def test_generate_specialist_opus_variants_overwrites_own_prior_variant(
    tmp_path: Path,
) -> None:
    """A file the function itself generated on a prior sync (marked with
    GENERATED_FILE_MARKER) must still be refreshed on the next sync -- the
    write-time ownership check must not block legitimate regeneration.
    """
    module = _load_script()
    generate = module["generate_specialist_opus_variants"]
    specialist_agents = module["SPECIALIST_AGENTS"]
    generated_file_marker = module["GENERATED_FILE_MARKER"]
    name = specialist_agents[0]

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    _write_specialist_source(agents_dir, name)
    (agents_dir / f"{name}-opus.md").write_text(
        f"---\nname: {name}-opus\n---\n{generated_file_marker}\nStale prompt.\n"
    )

    generated = generate(agents_dir, dry_run=False)

    assert generated == [f"{name}-opus"]
    variant = (agents_dir / f"{name}-opus.md").read_text()
    assert "Stale prompt." not in variant
    assert "# Specialist body" in variant


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


def test_generate_specialist_opus_variants_removes_stale_variant_when_source_gone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A name staying in SPECIALIST_AGENTS is not enough to keep its prior-sync
    variant alive -- if the specialist's own source file disappears (curated
    sync, stale entry not yet cleaned up), the stale <name>-opus.md must be
    pruned too, not preserved indefinitely just because the base name still
    matches the list. Left alive, it would never be regenerated (generation
    warns and skips a missing source) and would carry no config.json pin
    (build_agent_config only pins the actually-generated list) -- a stale,
    unpinned, but still dispatchable-by-name file.
    """
    module = _load_script()
    generate = module["generate_specialist_opus_variants"]
    specialist_agents = module["SPECIALIST_AGENTS"]
    generated_file_marker = module["GENERATED_FILE_MARKER"]
    name = specialist_agents[0]

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    # No {name}.md source file written -- simulates it having disappeared
    # since the prior sync that generated this variant.
    (agents_dir / f"{name}-opus.md").write_text(
        f"---\nname: {name}-opus\n---\n{generated_file_marker}\nStale prompt.\n"
    )

    generated = generate(agents_dir, dry_run=False)

    assert generated == []
    assert not (agents_dir / f"{name}-opus.md").exists()
    assert name in capsys.readouterr().err


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
