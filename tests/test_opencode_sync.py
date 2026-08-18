"""Tests for bin/opencode-sync.

Reduced by design/specs/1008-opencode-named-roles (T05): every dispatch now
names a real agent file directly, so worker generation, opus-variant
generation, dispatch rewriting, `resolve()` routing, the dispatch-
translation regexes, and config-level agent pinning (`build_agent_config()`,
`_config_json_pins()`, `check_collisions()`) all lost their subject and
their tests went with them.

Reduced again by design/specs/1007-opencode-config-plugin (T04): OpenCode now
reads `~/.claude/` directly through a plugin instead of this script staging a
copy, invoking OpenPackage, rewriting frontmatter, generating skill-command
wrappers, or tracking sync state -- so every test covering that transport
machinery (`stage_config()`, `run_opkg()`, `uninstall_previous()`,
`generate_skill_commands()`, `build_instructions()`,
`process_agent_frontmatter()`, `check_variant_names()`, `run_lint()`) went
with it. What remains: the commit-time gate (`check_source_dispatch_patterns()`
and its `find_unmatched_rule_exclusions()`/
`check_instruction_directory_coverage()` helpers), the orphan checker
(`find_orphaned_definitions()`/`check_orphans()`), and the three-key
`config.json` writer (`generate_config()`).

Grown by design/specs/1007-opencode-config-plugin (T05): the construction
half. `bootstrap()`/`bootstrap_entry()` symlink the plugin and compatibility
rule into the config dir and write `config.json`, then run the full
`--verify` sweep as their final step. `prune()`/`prune_entry()` remove the
previously-installed `agents/`, `skills/`, `commands/`, `rules/` trees.
`verify()` shells out to `opencode debug agent <name>` per agent -- faked
via `monkeypatch.setattr(subprocess, "run", ...)` and
`monkeypatch.setattr(shutil, "which", ...)` in every test below, never the
real binary. The `--verify` pre-commit hook wired into `prek.toml` is
checked by parsing the TOML directly, not by eye.
"""

import json
import re
import runpy
import shlex
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
PREK_TOML = REPO_ROOT / "prek.toml"
SCRIPT = REPO_ROOT / "bin" / "opencode-sync"


def _load_script() -> dict:
    return runpy.run_path(str(SCRIPT))


def test_generate_config_emits_exactly_three_keys(tmp_path: Path) -> None:
    """config.json declares `$schema`, `plugin`, and `subagent_depth` and
    nothing else (FR#17, AC#8) -- no `agent` key, since OpenCode resolves
    every agent's model and reasoning variant from that agent's own
    frontmatter (mediated by the plugin's tier remap), so a config-level pin
    would only duplicate it.
    """
    module = _load_script()

    content = module["generate_config"](tmp_path)
    config = json.loads(content)

    assert set(config.keys()) == {"$schema", "plugin", "subagent_depth"}
    assert config["plugin"] == ["claudefiles.ts"]


def test_generate_config_never_touches_opencode_jsonc(tmp_path: Path) -> None:
    """FR#18: opencode.jsonc is the machine-local overlay for `permission`
    and `mcp`, owned by the user. generate_config() must never read, write,
    or move it -- a pre-existing file's bytes staying identical is the proof.
    """
    module = _load_script()

    jsonc_path = tmp_path / "opencode.jsonc"
    original_bytes = b'{\n  // machine-local overrides\n  "permission": {},\n}\n'
    jsonc_path.write_bytes(original_bytes)

    module["generate_config"](tmp_path)

    assert jsonc_path.read_bytes() == original_bytes


def test_parse_args_rejects_removed_check_flag() -> None:
    """FR#21/AC#12: `--check` reported sync staleness, a concept that no
    longer exists now that OpenCode reads live files -- `--verify` (T05)
    answers the question that replaces it.
    """
    module = _load_script()

    with pytest.raises(SystemExit):
        module["parse_args"](["--check"])


def test_parse_args_rejects_removed_lint_only_flag() -> None:
    """FR#23/AC#12: `--lint-only` ran the compatibility lint over installed
    files, which no longer exist -- `--check-source` absorbed the one check
    worth keeping.
    """
    module = _load_script()

    with pytest.raises(SystemExit):
        module["parse_args"](["--lint-only"])


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


def test_find_unmatched_rule_exclusions_reports_stale_entry(tmp_path: Path) -> None:
    """A renamed rule silently starts syncing unless the stale entry
    surfaces. Non-mutating -- it must not delete the file it did match.
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


def _write_agent(agents_dir: Path, stem: str) -> None:
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / f"{stem}.md").write_text("---\nmodel: sonnet\n---\n\nbody\n")


def _fake_opencode_run(failing_stems: set[str]):
    """Fake replacement for subprocess.run() that reports success for every
    `opencode debug agent <name>` invocation except the given stems -- the
    boundary-fake pattern the TDD reference calls for, so no test in this
    file ever shells out to the real opencode binary.
    """

    def fake_run(cmd, **kwargs):
        stem = cmd[-1]
        returncode = 1 if stem in failing_stems else 0
        return subprocess.CompletedProcess(cmd, returncode, stdout="", stderr="")

    return fake_run


def test_prune_removes_all_four_trees_and_nothing_else(tmp_path: Path) -> None:
    """FR#19/AC#10: agents/, skills/, commands/, rules/ are gone; a
    pre-existing opencode.jsonc and node_modules/ (OpenCode auto-installs
    @opencode-ai/plugin there) survive untouched.
    """
    module = _load_script()

    config_dir = tmp_path / "opencode-config"
    for name in ("agents", "skills", "commands", "rules"):
        tree = config_dir / name
        tree.mkdir(parents=True)
        (tree / "x.md").write_text("stub\n")
    (config_dir / "opencode.jsonc").write_text('{\n  "permission": {},\n}\n')
    (config_dir / "node_modules" / "@opencode-ai" / "plugin").mkdir(parents=True)

    removed = module["prune"](config_dir)

    assert set(removed) == {"agents", "skills", "commands", "rules"}
    for name in ("agents", "skills", "commands", "rules"):
        assert not (config_dir / name).exists()
    assert (config_dir / "opencode.jsonc").is_file()
    assert (config_dir / "node_modules" / "@opencode-ai" / "plugin").is_dir()


def test_prune_is_a_noop_on_an_already_pruned_dir(tmp_path: Path) -> None:
    """A second --prune (or one against a dir that never had the trees) must
    not raise -- prune() only removes what's present.
    """
    module = _load_script()

    config_dir = tmp_path / "opencode-config"
    config_dir.mkdir()

    assert module["prune"](config_dir) == []


def test_verify_exits_zero_when_every_agent_resolves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR#20/AC#11: --verify with no argument checks every file under the
    given agents dir and exits zero when all resolve.
    """
    module = _load_script()

    agents_dir = tmp_path / "agents"
    _write_agent(agents_dir, "a")
    _write_agent(agents_dir, "b")

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/opencode")
    monkeypatch.setattr(subprocess, "run", _fake_opencode_run(set()))

    assert module["verify"](agents_dir, None) == 0


def test_verify_names_every_failing_agent_not_just_the_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """FR#20/AC#11: with two of three agents unresolvable, --verify exits
    non-zero and names both -- not just the first one it hits.
    """
    module = _load_script()

    agents_dir = tmp_path / "agents"
    _write_agent(agents_dir, "a")
    _write_agent(agents_dir, "b")
    _write_agent(agents_dir, "c")

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/opencode")
    monkeypatch.setattr(subprocess, "run", _fake_opencode_run({"a", "c"}))

    exit_code = module["verify"](agents_dir, None)
    captured = capsys.readouterr()

    assert exit_code != 0
    assert "'a'" in captured.err
    assert "'c'" in captured.err
    assert "'b'" not in captured.err


def test_verify_with_explicit_name_checks_only_that_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR#20/AC#11: an explicit agent name narrows the check to just that
    one -- "b" would fail if it were checked, but it isn't requested, so the
    call passes.
    """
    module = _load_script()

    agents_dir = tmp_path / "agents"
    _write_agent(agents_dir, "a")
    _write_agent(agents_dir, "b")

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/opencode")
    monkeypatch.setattr(subprocess, "run", _fake_opencode_run({"b"}))

    assert module["verify"](agents_dir, "a") == 0
    assert module["verify"](agents_dir, "b") != 0


def test_verify_reports_missing_opencode_binary_as_a_distinct_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A missing `opencode` binary must not be silently treated as "0 agents
    checked, 0 failed" (a false pass) -- it's a different failure than "an
    agent didn't resolve" and must be reported as such.
    """
    module = _load_script()

    agents_dir = tmp_path / "agents"
    _write_agent(agents_dir, "a")

    monkeypatch.setattr(shutil, "which", lambda name: None)

    exit_code = module["verify"](agents_dir, None)
    captured = capsys.readouterr()

    assert exit_code != 0
    assert "PATH" in captured.err


def test_bootstrap_twice_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR#25/AC#20: running --bootstrap twice against a scratch config dir
    leaves config.json and both symlink targets identical after the second
    run as after the first, with exit 0 both times.
    """
    module = _load_script()

    config_dir = tmp_path / "opencode-config"
    claude_root = tmp_path / "claude-root"
    _write_agent(claude_root / "agents", "a")

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_root))
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/opencode")
    monkeypatch.setattr(subprocess, "run", _fake_opencode_run(set()))

    first_exit = module["bootstrap"](config_dir, REPO_ROOT)
    first_config_bytes = (config_dir / "config.json").read_bytes()
    plugin_target_1 = (config_dir / "claudefiles.ts").resolve()
    compat_filename = module["resolve_compat_rule_filename"](REPO_ROOT)
    compat_target_1 = (config_dir / compat_filename).resolve()

    second_exit = module["bootstrap"](config_dir, REPO_ROOT)
    second_config_bytes = (config_dir / "config.json").read_bytes()
    plugin_target_2 = (config_dir / "claudefiles.ts").resolve()
    compat_target_2 = (config_dir / compat_filename).resolve()

    assert first_exit == 0
    assert second_exit == 0
    assert first_config_bytes == second_config_bytes
    assert (
        plugin_target_1
        == plugin_target_2
        == (REPO_ROOT / "opencode" / "claudefiles.ts").resolve()
    )
    assert (
        compat_target_1
        == compat_target_2
        == (REPO_ROOT / "opencode" / "opencode-compat.md").resolve()
    )


def test_bootstrap_propagates_verification_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """FR#26/AC#21: --bootstrap against a config dir whose agent(s) fail
    --verify's sweep exits non-zero and names the failing agent -- the tail
    that catches a plugin regression at the one moment it's most likely to
    have just been introduced.
    """
    module = _load_script()

    config_dir = tmp_path / "opencode-config"
    claude_root = tmp_path / "claude-root"
    _write_agent(claude_root / "agents", "broken-agent")

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_root))
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/opencode")
    monkeypatch.setattr(subprocess, "run", _fake_opencode_run({"broken-agent"}))

    exit_code = module["bootstrap"](config_dir, REPO_ROOT)
    captured = capsys.readouterr()

    assert exit_code != 0
    assert "'broken-agent'" in captured.err


def test_bootstrap_rejects_conflicting_non_symlink_at_plugin_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real file already sitting at <config_dir>/claudefiles.ts (not a
    symlink) is a conflict --bootstrap must fail loudly on, not clobber."""
    module = _load_script()

    config_dir = tmp_path / "opencode-config"
    config_dir.mkdir()
    (config_dir / "claudefiles.ts").write_text("// not a symlink\n")

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-root"))

    with pytest.raises(SystemExit):
        module["bootstrap"](config_dir, REPO_ROOT)


def test_bootstrap_rejects_symlink_pointing_at_unrelated_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A stale symlink already sitting at <config_dir>/claudefiles.ts that
    resolves to something other than opencode/claudefiles.ts (e.g. left
    over from a previous plugin location) is a conflict --bootstrap must
    fail loudly on, naming the unexpected target, rather than silently
    repointing it."""
    module = _load_script()

    config_dir = tmp_path / "opencode-config"
    config_dir.mkdir()
    unrelated_target = tmp_path / "unrelated-file.ts"
    unrelated_target.write_text("// not the real plugin\n")
    (config_dir / "claudefiles.ts").symlink_to(unrelated_target)

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-root"))

    with pytest.raises(SystemExit):
        module["bootstrap"](config_dir, REPO_ROOT)

    captured = capsys.readouterr()
    assert str(unrelated_target.resolve()) in captured.err


def test_resolve_compat_rule_filename_reads_the_plugins_own_literal() -> None:
    """FR#9: the compat-rule symlink's basename comes from
    opencode/claudefiles.ts's own COMPAT_RULE_PATH literal, not a second
    hardcoded guess in Python that could silently drift from it.
    """
    module = _load_script()

    assert module["resolve_compat_rule_filename"](REPO_ROOT) == "opencode-compat.md"


def _find_verify_hook() -> dict:
    prek_config = tomllib.loads(PREK_TOML.read_text())
    hooks = [
        hook
        for repo in prek_config["repos"]
        for hook in repo.get("hooks", [])
        if hook.get("id") == "verify-opencode-agents"
    ]
    assert len(hooks) == 1, f"expected exactly one --verify hook, found {hooks}"
    return hooks[0]


def test_prek_verify_hook_files_pattern_matches_plugin_and_shared_data_file() -> None:
    """FR#28/AC#24: the hook's `files` pattern matches
    opencode/claudefiles.ts and opencode/config-data.json, and does not
    match unrelated paths.
    """
    hook = _find_verify_hook()
    pattern = hook["files"]

    assert re.search(pattern, "opencode/claudefiles.ts")
    assert re.search(pattern, "opencode/config-data.json")
    assert not re.search(pattern, "bin/opencode-sync")
    assert not re.search(pattern, "opencode/opencode-compat.md")


def test_prek_verify_hook_is_not_always_run() -> None:
    """FR#28/AC#24: unlike the two existing lint-opencode-sync* hooks, the
    --verify hook must not set always_run = true -- it starts an OpenCode
    process and is too slow for every commit.
    """
    hook = _find_verify_hook()

    assert hook.get("always_run") is not True


def test_prek_verify_hook_skips_gracefully_when_opencode_binary_is_absent() -> None:
    """CI runs `prek run --all-files`, which matches this hook's `files`
    pattern against the whole repo regardless of the actual diff, so it
    fires on every CI run -- but `opencode` is never installed in CI
    (design.md's Gap note: no automated harness runs OpenCode there). The
    hook's own entry -- not verify()'s exit-non-zero-on-missing-binary
    logic, which a developer invoking `bin/opencode-sync --verify` directly
    still gets -- must detect the missing binary and skip with exit 0
    rather than fail every CI run on an unrelated diff.
    """
    hook = _find_verify_hook()
    argv = shlex.split(hook["entry"])

    result = subprocess.run(
        argv,
        cwd=REPO_ROOT,
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0
    assert "opencode" in result.stderr.lower()
