"""Tests for bin/opencode-sync.

Covers a PR #503 review fix (`stage_config()` creates `rules/common/`
before writing the compat rule, instead of raising FileNotFoundError when
the source tree lacks it) and a `run_opkg()` behavior: it accepts an
optional `home_override` that redirects the opkg install to a scratch HOME
(via `--cwd` + the `HOME` env var) instead of the real one, and always
installs for real (never appends `--dry-run`) in that mode -- this is what
lets `--dry-run` preview the staged content instead of scanning stale
output from the last real sync.

Reduced by design/specs/1008-opencode-named-roles (T05): every dispatch now
names a real agent file directly, so worker generation, opus-variant
generation, dispatch rewriting, `resolve()` routing, the dispatch-
translation regexes, and config-level agent pinning (`build_agent_config()`,
`_config_json_pins()`, `check_collisions()`) all lost their subject and
their tests went with them. `check_variant_names()` was narrowed rather
than removed -- see the `test_check_variant_names_*` tests below, most of
which still apply.
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


def test_generate_config_points_instructions_at_synced_rules(tmp_path: Path) -> None:
    """Rules that opkg puts on disk are inert unless `instructions` names them.

    OpenCode's only other global instruction source is the first existing of
    `[<config>/AGENTS.md, ~/.claude/CLAUDE.md]`; nothing globs `<config>/rules/`.

    `instructions` now has two entries -- opencode/config-data.json's
    `instruction_dirs` names both `rules/common` and `rules/personal` (T01
    added the second entry over the original single-directory constant).
    """
    module = _load_script()

    content = module["generate_config"](tmp_path, dry_run=False)
    config = json.loads(content)

    assert config["instructions"] == [
        str(tmp_path / "rules/common/*.md"),
        str(tmp_path / "rules/personal/*.md"),
    ]


def test_generate_config_emits_no_agent_key(tmp_path: Path) -> None:
    """config.json carries no `agent` key (FR#17, AC#9) -- OpenCode resolves
    every agent's model and reasoning variant from that agent's own
    frontmatter, so config-level pinning would only duplicate it.
    """
    module = _load_script()

    content = module["generate_config"](tmp_path, dry_run=False)
    config = json.loads(content)

    assert "agent" not in config


def test_build_instructions_never_uses_recursive_glob() -> None:
    """For an absolute pattern OpenCode globs `basename` inside `dirname` and
    does not recurse, so a `**` entry matches nothing -- silently, which is
    indistinguishable from having no rules at all.
    """
    module = _load_script()

    for entry in module["build_instructions"](Path("/tmp/oc")):
        assert "**" not in entry, f"{entry} will silently match nothing"
        assert entry.endswith("*.md")


def test_check_instruction_directory_coverage_flags_uncovered_rules_directory(
    tmp_path: Path,
) -> None:
    """A new rules subdirectory the shared instruction-directory list
    (opencode/config-data.json) doesn't name must fail the check rather than
    shipping rules nothing ever loads. Retargeted (T03) to take the `rules/`
    root directly, not a config dir + INSTRUCTION_ROOT.
    """
    module = _load_script()
    rules_root = tmp_path / "rules"
    covered = rules_root / "common"
    covered.mkdir(parents=True)
    (covered / "a.md").write_text("# covered\n")
    uncovered = rules_root / "other"
    uncovered.mkdir()
    (uncovered / "b.md").write_text("# uncovered\n")

    errors = module["check_instruction_directory_coverage"](rules_root)

    assert len(errors) == 1
    assert "rules/other" in errors[0]
    assert "instruction_dirs" in errors[0]
    assert "opencode/config-data.json" in errors[0]


def test_check_instruction_directory_coverage_clean_when_every_rules_dir_covered(
    tmp_path: Path,
) -> None:
    module = _load_script()
    rules_root = tmp_path / "rules"
    covered = rules_root / "common"
    covered.mkdir(parents=True)
    (covered / "a.md").write_text("# covered\n")

    assert module["check_instruction_directory_coverage"](rules_root) == []


def test_check_instruction_directory_coverage_ignores_directory_with_no_rules(
    tmp_path: Path,
) -> None:
    """An empty or purely structural directory has nothing to load, so
    flagging it would fail the check over a non-problem.
    """
    module = _load_script()
    rules_root = tmp_path / "rules"
    (rules_root / "common").mkdir(parents=True)
    (rules_root / "scratch").mkdir()

    assert module["check_instruction_directory_coverage"](rules_root) == []


def _write_rule(path: Path, tool_line: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = f"---\n{tool_line}\n---\n" if tool_line else ""
    path.write_text(f"{frontmatter}# {path.stem}\n")


def test_stage_config_drops_only_excluded_rules(tmp_path: Path) -> None:
    """Include is the default: OPENCODE_COMPAT_RULE translates Claude-only
    references, so only rules that are actively wrong for OpenCode are
    withheld. Deriving this from `tool:` frontmatter instead excluded seven
    rules OpenCode wants -- that marker answers "does this go to Antigravity?"

    Only `common/sudo.md` is withheld now (T03: stage_config() reads
    opencode/config-data.json's `excluded_rules`, which T01 already shrank
    to that one entry -- design.md, Key Decisions #8). performance.md and
    tmux.md's exclusion rationale went stale post-1008, so this test's
    original three-entry exclusion set no longer matches reality; updated
    rather than left to assert a behavior that no longer holds.
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
    assert (staged_rules / "performance.md").is_file()
    assert (staged_rules / "tmux.md").is_file()
    assert not (staged_rules / "sudo.md").exists()
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
    """Guards the actual repo: exactly opencode/config-data.json's
    excluded_rules is withheld.
    """
    module = _load_script()
    repo = Path(__file__).resolve().parent.parent

    tmpdir = tmp_path / "staging"
    tmpdir.mkdir()
    staged = module["stage_config"](repo, tmpdir)

    # OPENCODE_EXCLUDED_RULES no longer exists as a module constant (T03) --
    # this test still exercises stage_config(), so it reads the same shared
    # list stage_config() itself now loads from.
    excluded = set(module["_load_config_data"]()["excluded_rules"])
    for source in sorted((repo / "rules").rglob("*.md")):
        relative = source.relative_to(repo / "rules").as_posix()
        staged_file = staged / "rules" / relative
        if relative in excluded:
            assert not staged_file.exists(), f"{relative} should not sync"
        else:
            assert staged_file.is_file(), f"{relative} should sync but did not"


def test_excluded_rules_shrinks_to_one_entry_and_no_longer_filters_performance_or_tmux(
    tmp_path: Path,
) -> None:
    """The exclusion list loaded from opencode/config-data.json shrank from
    three entries to one (design.md, Key Decisions #8): performance.md's and
    tmux.md's exclusion rationale went stale post-1008, and only
    common/sudo.md remains -- with no hook firing under OpenCode, a bare
    `sudo` hits a passwordless prompt with no TTY and hangs. This is the
    behavior change users actually feel, so it needs its own assertion
    rather than riding along on the other exclusion tests, none of which
    check the count.
    """
    module = _load_script()
    excluded = module["_load_config_data"]()["excluded_rules"]

    assert excluded == ["common/sudo.md"]
    assert "common/performance.md" not in excluded
    assert "common/tmux.md" not in excluded

    claudefiles = tmp_path / "claudefiles"
    for name in ("sudo.md", "performance.md", "tmux.md"):
        _write_rule(claudefiles / "rules" / "common" / name, "tool: claude")

    tmpdir = tmp_path / "staging"
    tmpdir.mkdir()
    staged = module["stage_config"](claudefiles, tmpdir)

    staged_rules = staged / "rules" / "common"
    assert not (staged_rules / "sudo.md").exists()
    assert (staged_rules / "performance.md").is_file()
    assert (staged_rules / "tmux.md").is_file()


def test_find_unmatched_rule_exclusions_reports_stale_entry(tmp_path: Path) -> None:
    """A renamed rule silently starts syncing unless the stale entry
    surfaces. Non-mutating (T03) -- unlike its predecessor
    apply_rule_exclusions(), it must not delete the file it did match.
    """
    module = _load_script()

    rules = tmp_path / "rules" / "common"
    _write_rule(rules / "keeps.md", "tool: claude")

    missing = module["find_unmatched_rule_exclusions"](tmp_path / "rules")

    assert missing == ["common/sudo.md"]
    assert (rules / "keeps.md").is_file()


def test_check_source_gate_flags_stale_exclusion(tmp_path: Path) -> None:
    """The pre-commit gate fails on an exclusion entry matching no file."""
    module = _load_script()

    claudefiles = tmp_path / "claudefiles"
    (claudefiles / "agents").mkdir(parents=True)
    (claudefiles / "agents" / "a.md").write_text("---\nmodel: sonnet\n---\n\nbody\n")
    _write_rule(claudefiles / "rules" / "common" / "keeps.md", "tool: claude")

    errors, _ = module["check_source_dispatch_patterns"](claudefiles)

    assert any("config-data.json" in e and "common/sudo.md" in e for e in errors), (
        errors
    )


def test_check_source_gate_sees_uncovered_rules_directory(tmp_path: Path) -> None:
    """The `--check-source` pre-commit gate must be able to fail on an
    uncovered rules directory. It reads this repo's own `rules/` tree
    directly rather than a staged copy, so this proves the coverage check
    is wired into check_source_dispatch_patterns() and not just defined.

    Uses `rules/other`, not `rules/personal` -- the real
    opencode/config-data.json now names both `rules/common` and
    `rules/personal`, so `rules/personal` is no longer an uncovered
    directory to test against.
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
        claudefiles / "rules" / "other" / "uncovered.md",
        "tool: claude, antigravity",
    )

    errors, _ = module["check_source_dispatch_patterns"](claudefiles)

    coverage_errors = [e for e in errors if "instruction_dirs" in e]
    assert len(coverage_errors) == 1, f"gate did not flag the uncovered dir: {errors}"
    assert "rules/other" in coverage_errors[0]


def test_check_source_gate_flags_dispatch_naming_nonexistent_agent(
    tmp_path: Path,
) -> None:
    """FR#18/AC#10: a dispatch naming an agent with no file in agents/ fails
    the gate -- the reimplemented check's whole job, now that there is no
    rewriter to translate a stale name into a real one.
    """
    module = _load_script()

    claudefiles = tmp_path / "claudefiles"
    agents = claudefiles / "agents"
    agents.mkdir(parents=True)
    (agents / "code-reviewer.md").write_text(
        "---\nname: code-reviewer\nmodel: x\n---\n\nbody\n"
    )
    skills = claudefiles / "skills"
    skills.mkdir()
    (skills / "example.md").write_text(
        "Launch subagent_type: nonexistent-agent for this task.\n"
    )

    errors, _ = module["check_source_dispatch_patterns"](claudefiles)

    assert any("nonexistent-agent" in e for e in errors)


def test_check_source_gate_passes_on_dispatch_naming_real_agent(
    tmp_path: Path,
) -> None:
    """The mirror case: a dispatch naming an agent that does have a file in
    agents/ raises no error.
    """
    module = _load_script()

    claudefiles = tmp_path / "claudefiles"
    agents = claudefiles / "agents"
    agents.mkdir(parents=True)
    (agents / "code-reviewer.md").write_text(
        "---\nname: code-reviewer\nmodel: x\n---\n\nbody\n"
    )
    skills = claudefiles / "skills"
    skills.mkdir()
    (skills / "example.md").write_text(
        "Launch subagent_type: code-reviewer for this task.\n"
    )

    errors, _ = module["check_source_dispatch_patterns"](claudefiles)

    assert errors == []


def test_check_source_gate_flags_agent_type_flag_naming_nonexistent_agent(
    tmp_path: Path,
) -> None:
    """The `cfl dispatch ... --agent-type <name>` telemetry-form dispatch is
    a distinct shape from `subagent_type:` and was silently unchecked --
    this shape is unambiguously a dispatch (no prose-vs-mention
    disambiguation problem), so the gate must catch it too.
    """
    module = _load_script()

    claudefiles = tmp_path / "claudefiles"
    agents = claudefiles / "agents"
    agents.mkdir(parents=True)
    (agents / "code-reviewer.md").write_text(
        "---\nname: code-reviewer\nmodel: x\n---\n\nbody\n"
    )
    skills = claudefiles / "skills"
    skills.mkdir()
    (skills / "example.md").write_text(
        "cfl dispatch foo --agent-type nonexistent-agent\n"
    )

    errors, _ = module["check_source_dispatch_patterns"](claudefiles)

    assert any("nonexistent-agent" in e for e in errors)


def test_check_source_gate_passes_on_agent_type_flag_naming_real_agent(
    tmp_path: Path,
) -> None:
    """The mirror case: `--agent-type` naming an agent that does have a file
    in agents/ raises no error.
    """
    module = _load_script()

    claudefiles = tmp_path / "claudefiles"
    agents = claudefiles / "agents"
    agents.mkdir(parents=True)
    (agents / "code-reviewer.md").write_text(
        "---\nname: code-reviewer\nmodel: x\n---\n\nbody\n"
    )
    skills = claudefiles / "skills"
    skills.mkdir()
    (skills / "example.md").write_text("cfl dispatch foo --agent-type code-reviewer\n")

    errors, _ = module["check_source_dispatch_patterns"](claudefiles)

    assert errors == []


def test_check_source_gate_flags_residual_model_clause(tmp_path: Path) -> None:
    """FR#18's second half: a raw `model:` tier clause at a dispatch site is
    also an error -- model tier now lives only in the agent's own
    frontmatter.
    """
    module = _load_script()

    claudefiles = tmp_path / "claudefiles"
    agents = claudefiles / "agents"
    agents.mkdir(parents=True)
    (agents / "code-reviewer.md").write_text(
        "---\nname: code-reviewer\nmodel: x\n---\n\nbody\n"
    )
    skills = claudefiles / "skills"
    skills.mkdir()
    (skills / "example.md").write_text(
        "Launch subagent_type: code-reviewer, model: sonnet for this task.\n"
    )

    errors, _ = module["check_source_dispatch_patterns"](claudefiles)

    assert any("model: sonnet" in e for e in errors)


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


def test_check_variant_names_flags_frontmatter_variant_with_no_model(
    tmp_path: Path,
) -> None:
    """A resolvable `variant:` still needs a model pin to take effect.

    process_agent_frontmatter() drops an `effort:` line whose file has no
    tier-resolvable `model:` for this reason; a `variant:` written directly
    into a source file bypasses that path, so the lint has to hold the same
    invariant.
    """
    module = _load_script()

    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "orphan.md").write_text("---\nvariant: high\n---\n\nbody\n")

    errors = module["check_variant_names"](tmp_path)

    assert len(errors) == 1
    assert "orphan.md" in errors[0]
    assert "no `model:`" in errors[0]


def test_check_variant_names_reports_name_and_model_faults_independently(
    tmp_path: Path,
) -> None:
    """Both faults surface at once rather than one hiding behind the other.

    Fixing the name doesn't supply a model and fixing the model doesn't fix
    the name, so reporting only the first would send the reader back for a
    second lint cycle to discover the second.
    """
    module = _load_script()

    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "both.md").write_text("---\nvariant: turbo\n---\n\nbody\n")

    errors = module["check_variant_names"](tmp_path)

    assert len(errors) == 2
    assert any("turbo" in e for e in errors)
    assert any("no `model:`" in e for e in errors)


def test_check_variant_names_missing_variant_does_not_also_flag_model(
    tmp_path: Path,
) -> None:
    """With no variant anywhere there is nothing to resolve, so a missing
    model pin is moot -- reporting it as a second fault would be noise.
    """
    module = _load_script()

    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "bare.md").write_text("---\ndescription: b\n---\n\nbody\n")

    errors = module["check_variant_names"](tmp_path)

    assert len(errors) == 1
    assert "no `variant:`" in errors[0]


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


def test_check_source_gate_flags_tier_map_variant_opencode_does_not_resolve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every opencode/config-data.json `tier_map` entry's `variant` must be a
    name in that same file's `variants` list, checked by
    check_source_dispatch_patterns() (T03) so `--check-source` exits non-zero
    on a bad one.

    Formerly `test_tier_map_variants_are_names_opencode_resolves`, which
    asserted this property directly against the in-script `TIER_MAP` and
    `OPENCODE_VARIANTS` constants. Those constants are gone from this
    script's routing role in FR#27's shared-data design -- `tier_map` and
    `variants` are authored once, in opencode/config-data.json, so this is
    where the check has to live now. Agent-level variant resolution drops
    any name missing from the model's synthesized `variants` map without
    warning, so an unresolvable name here reproduces the exact bug the
    `effort` -> `variant` rename fixed (#514): config that looks correct
    while every subagent silently runs at the provider default.
    """
    module = _load_script()

    claudefiles = tmp_path / "claudefiles"
    agents = claudefiles / "agents"
    agents.mkdir(parents=True)
    (agents / "a.md").write_text("---\nmodel: x\n---\n\nbody\n")

    # runpy.run_path() returns a *copy* of the executed namespace, not the
    # live one -- module["check_source_dispatch_patterns"].__globals__ is a
    # different dict than `module` itself (confirmed empirically), so a
    # replacement has to land in that live __globals__ dict or the function's
    # own lookup of `_load_config_data` never sees it.
    monkeypatch.setitem(
        module["check_source_dispatch_patterns"].__globals__,
        "_load_config_data",
        lambda: {
            "tier_map": {"sonnet": {"model": "openai/x", "variant": "turbo"}},
            "variants": ["none", "low", "medium", "high", "xhigh", "max"],
            "excluded_rules": [],
            "instruction_dirs": ["rules/common"],
        },
    )

    errors, _ = module["check_source_dispatch_patterns"](claudefiles)

    assert any("turbo" in e and "tier_map" in e for e in errors), errors


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


def test_find_orphaned_definitions_clean_when_helper_is_referenced() -> None:
    """FR#25/AC#21: a module-level function whose name reappears elsewhere in
    the file (its caller) is not an orphan.
    """
    module = _load_script()
    find_orphaned = module["find_orphaned_definitions"]

    # `run` is referenced by the `__main__` epilogue, same as the real
    # script's own `def main(): ...` / `sys.exit(main())` pattern -- without
    # it, `run` itself would appear on only its own definition line and get
    # flagged too, which would defeat the point of this "clean" case.
    source = (
        "def helper():\n"
        "    return 1\n"
        "\n"
        "\n"
        "def run():\n"
        "    return helper()\n"
        "\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    run()\n"
    )

    assert find_orphaned(source) == []


def test_find_orphaned_definitions_flags_stranded_helper() -> None:
    """AC#21's second scenario: removing a function but not its private
    helper leaves the helper referenced nowhere but its own definition line
    -- the exact shape this check exists to catch.
    """
    module = _load_script()
    find_orphaned = module["find_orphaned_definitions"]

    source = (
        "def _stranded_helper():\n"
        "    return 1\n"
        "\n"
        "\n"
        "def run():\n"
        "    return 2\n"
        "\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    run()\n"
    )

    assert find_orphaned(source) == ["_stranded_helper"]


def test_find_orphaned_definitions_flags_unreferenced_constant() -> None:
    """The check also covers ALL_CAPS module-level constant bindings, not
    just function defs.
    """
    module = _load_script()
    find_orphaned = module["find_orphaned_definitions"]

    source = (
        'UNUSED_CONSTANT = "x"\n'
        "\n"
        "\n"
        "def run():\n"
        "    return 1\n"
        "\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    run()\n"
    )

    assert find_orphaned(source) == ["UNUSED_CONSTANT"]


def test_find_orphaned_definitions_ignores_local_assignments() -> None:
    """Only module-level statements are walked -- an ordinary local variable
    inside a function body (even an ALL_CAPS one) is not a definition site
    this check has any opinion about.
    """
    module = _load_script()
    find_orphaned = module["find_orphaned_definitions"]

    source = (
        "def run():\n"
        "    LOCAL = 1\n"
        "    return LOCAL\n"
        "\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    run()\n"
    )

    assert find_orphaned(source) == []


def test_check_orphans_clean_against_the_real_script() -> None:
    """Running the checker against the real, current bin/opencode-sync
    reports zero orphans -- a regression guard that fires the moment a
    future deletion wave leaves a stranded helper behind, the same failure
    mode enumerating removal targets by hand has repeatedly missed.
    """
    module = _load_script()
    check_orphans = module["check_orphans"]

    assert check_orphans(SCRIPT) == []
