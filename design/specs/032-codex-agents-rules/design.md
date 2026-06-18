# Design: Codex always-on rules via global AGENTS.md

**Date:** 2026-06-18
**Status:** draft
**Scope-mode:** hold
**Research:** design/research/2026-06-18-codex-always-on-rules/research.md

## Problem

Claudefiles ships 28 always-on behavioral rules (`rules/common/*.md`) that Claude Code loads every session. The same machine also runs OpenAI Codex CLI, which gets none of them — so Codex operates without the immutability rules, Python conventions, commit format, verification discipline, etc. that govern Claude's work. Codex has no directory-based prose-rules discovery; its only always-on prose channel is the `AGENTS.md` chain. Prior research (see Research link) established that concatenating rules into a single global `~/.codex/AGENTS.md` is the dominant, empirically-verified way to deliver them, and that the documented byte cap does **not** apply to the global file. What's missing is the mechanism to generate that file from the repo's rules.

A naive "concat every rule" is wrong: several rules are Claude-Code-harness-specific (skill routing, hook docs, tool-name mappings, model policy, tmux/sudo helpers) that Codex cannot act on and that would mislead it (e.g. instructing it to "run the code-reviewer agent"). The rules must be classified before concatenation. Classification is **whole-file**: each rule is either portable to Codex or it isn't.

## Goals

- A repeatable generator that produces `~/.codex/AGENTS.md` from `rules/common/*.md`, carrying only the rules portable to Codex.
- Each rule declares its own cross-tool disposition on the artifact (encode-in-structure) via a `tool:` frontmatter allowlist, so the include/exclude decision is not a hidden list in the generator.
- The generated file is deterministic (same inputs → byte-identical output) and clearly marked as generated.
- The generator runs both standalone (regenerate on demand) and as part of `install.py` (machine state materialized from the repo, alongside the existing symlinks).
- Verifiable that Codex actually loads the result.

## Non-Goals

- Personal Dotfiles rules (`~/Dotfiles/.../rules/personal/`) — out of scope this pass; common rules only.
- Codex agents, hooks, and permissions — those go through rulesync (separate work); this design is rules only.
- Antigravity CLI rules — Antigravity reads a real `.agents/rules/` directory (rulesync target), so it does **not** need the AGENTS.md concat. This mechanism is Codex-specific.
- The skills symlink to `~/.agents/skills/` — separate piece of the multi-tool sync.
- Per-repo (project-root) `AGENTS.md` generation — only the global user file.
- **Mirroring the per-category install selection** — Codex gets *all* portable common rules regardless of which optional categories you installed. Selection-mirroring was deliberately dropped: the worst case is Codex picking up one extra behavioral rule you deselected for Claude, which is near-zero harm and not worth a shared install/generator config path.
- **Section-level (surgical) extraction within a file** — disposition is whole-file. A rule that mixes portable and harness-specific guidance is resolved by **splitting the rule file** into a portable file and a Claude-only file (both stay in `rules/common/`, so Claude loads both; only the portable file lists `codex` in its `tool:`), not by in-file fences. `git-workflow.md` is split this way (see Architecture).

## User Scenarios

### Jessica: Claudefiles maintainer (single actor)
- **Goal:** keep Codex CLI governed by the same always-on rules as Claude Code.
- **Context:** runs `install.py` to materialize machine config from the repo; occasionally edits rules and wants Codex to pick up changes.

#### Install materializes Codex rules

1. **Runs `uv run install.py`** (from the main repo, not a worktree)
   - Sees: existing install summary, now also a line reporting the Codex AGENTS.md was written (N rules included, M excluded, K bytes).
   - Then: `~/.codex/AGENTS.md` exists with the portable rules; Codex loads them next run.

2. **Edits a rule, or changes one's `tool:` disposition, then regenerates**
   - Runs `codex-rules-sync` standalone (no full reinstall).
   - Sees: a summary of included/excluded files and output size.
   - Then: `~/.codex/AGENTS.md` reflects the change, byte-identical on a repeat run with no edits.

## Functional Requirements

- **FR#1** The generator concatenates the body of each included `rules/common/*.md` file into a single output document.
- **FR#2** Classification is a `tool:` frontmatter allowlist: a rule is included only when its `tool:` value (a comma-separated list) contains `codex`. The key is read specifically (not a substring scan), so a body or comment mention of `tool: codex` does not affect classification; per-item quotes and an inline `# comment` after the value are tolerated.
- **FR#3** The default is **fail-closed**: a rule with no `tool:` key (or a `tool:` list lacking `codex`) is Claude-only and excluded from Codex. Reaching Codex is always an explicit `tool: ..., codex`. (Rationale: under-inclusion is a degraded result; over-inclusion injects directives Codex cannot act on — the failure the classification exists to prevent.)
- **FR#4** Each included file's content is preceded in the output by a source marker comment naming its repo-relative path (e.g. `<!-- from rules/common/coding-style.md -->`).
- **FR#5** The output's first two lines are a generated-file marker (`<!-- GENERATED BY codex-rules-sync — DO NOT EDIT MANUALLY. Run codex-rules-sync to regenerate. -->`) and a precedence note stating these are baseline rules a project-level `AGENTS.md` may override. The marker is a courtesy, not an ownership gate — the generator does not inspect the existing file before overwriting (no hand-authored `~/.codex/AGENTS.md` exists to protect).
- **FR#6** The generator writes the output to `$CODEX_HOME/AGENTS.md`, treating an unset *or empty* `$CODEX_HOME` as `~/.codex`, resolving the path (symlinks followed) so the temp file and target share a filesystem. The write is wrapped so an OSError (unwritable dir, cross-device) fails with a legible message and non-zero exit, not a traceback.
- **FR#7** Running the generator twice with no source changes produces byte-identical output (deterministic file ordering and rendering).
- **FR#8** The generator prints a summary: count of included files, count of excluded files, and total output byte size. A `--list` mode prints the per-file include/exclude breakdown and exits without writing (the runnable index of "which rules reach Codex").
- **FR#9** If the Codex home directory does not exist (Codex not installed), the generator skips writing and reports the skip rather than creating the directory. If the path exists but is not a directory, it errors.
- **FR#10** The generator refuses to run against its in-repo default `rules/common` when that repo is a git worktree checkout (detected by the `.claude/worktrees/` layout), unless `--allow-worktree` or an explicit `--rules-dir` is given. This prevents materializing in-progress worktree rules into the machine-global `~/.codex/AGENTS.md`. The installed symlink resolves to the main repo, so normal runs are unaffected; install.py also refuses to run from a worktree.

## Edge Cases

- **No rule tagged for Codex / empty result** — abort with an error rather than writing an empty AGENTS.md (signals a misconfiguration).
- **Unclosed frontmatter** (opening `---` with no closing `---`) — the opening line is dropped so it cannot leak into the output as a stray horizontal rule; the rest is treated as body with no frontmatter, so the rule is fail-closed (Claude-only, excluded from Codex), and a warning is printed to stderr.

## Acceptance Criteria

- **AC#1** After running the generator, `~/.codex/AGENTS.md` exists and contains the body text of an included rule (e.g. a sentinel string from `coding-style.md`). (FR#1, FR#6)
- **AC#2** A rule tagged `tool: claude` (or untagged) does **not** appear in the output (e.g. the `/mine-*` routing table from `capabilities-core.md` is absent). (FR#2, FR#3)
- **AC#3** Every included file's content is immediately preceded by its `<!-- from ... -->` source marker. (FR#4)
- **AC#4** The output's first line is the FR#5 generated-file marker and the precedence note is present. (FR#5)
- **AC#5** Two consecutive runs with no source edits produce identical files (`diff` is empty). (FR#7)
- **AC#6** `codex debug prompt-input` from a neutral directory shows a head-and-tail sentinel pair from the generated global file, confirming Codex loads it in full. (FR#6) *(Integration check — gated on the `codex` binary being present; skipped otherwise.)*
- **AC#7** Running with a Codex home that does not exist makes no filesystem changes and reports a skip; a path that exists but is not a directory errors. (FR#9)
- **AC#8** A rule tagged `tool: claude, codex` appears in the output; a body mention of `tool: codex` in a `tool: claude` file does not opt it in. (FR#2, FR#3)
- **AC#9** The run prints a summary line stating included/excluded counts and output byte size; `--list` prints the per-file breakdown and writes nothing. (FR#8)
- **AC#10** Given an input set where no file is tagged for Codex, the generator aborts (writes nothing) rather than producing an empty AGENTS.md, and does not clobber any pre-existing file. (Edge case)
- **AC#11** Run with the in-repo default rules dir from a worktree checkout without `--allow-worktree`, the generator refuses and writes nothing. (FR#10)

## Key Constraints

- **Do not use rulesync to generate the rules output.** rulesync writes non-root rules to `.codex/memories/`, which Codex does not read (issue #1765). This generator must own the rules path. **And this holds even if #1765 is fixed:** rulesync does zero content transformation — its pipeline only adjusts YAML frontmatter and flattens descriptions (findings.md), so even with a future `ruleDiscoveryMode: inline` it would concatenate all 28 rules including the harness-specific files Codex cannot act on. The classification step is what makes this generator necessary, independent of the bug — so "build our own" is the durable choice, not a workaround.
- **Do not target `.codex/rules/`** — that is Codex's Starlark command-execution policy subsystem, not prose.
- **Do not change `project_doc_max_bytes` or any `config.toml` field** — the global file is uncapped; touching the cap is unnecessary and out of scope.
- **No third-party YAML dependency for frontmatter** — match the stdlib-only `parse_frontmatter` convention in `bin/lint-agent-models`; the only key needed is `tool:`, parsed as a comma-separated list with an optional inline `# comment`.
- **Frontmatter leak is accepted, not solved here** — rules inject as raw text, so the one-line `tool:` frontmatter block is mildly visible to Claude in every rule file (Claude loads them all every session regardless of `tool:`). It is negligible and not worth a generator-side manifest that would split the decision off the artifact; keeping the disposition on the artifact is the point (encode-in-structure).

## Dependencies and Assumptions

- Assumes Codex resolves the global instruction file at `$CODEX_HOME/AGENTS.md` (default `~/.codex/AGENTS.md`) — verified on codex 0.139.0.
- Assumes `install.py` is the orchestrator for materializing machine state and can call the generator after its symlink phase.
- Integration (sentinel) verification depends on the `codex` binary being present; unit tests do not.
- The uncapped-global-file behavior is verified on codex 0.139.0. It is version-sensitive — re-run AC#6 after a Codex upgrade to confirm the global file still loads in full (and watch for `.agents/rules/` becoming canonical, which would supersede this approach).

## Architecture

A single stdlib-only Python generator, `bin/codex-rules-sync`, following the `bin/lint-agent-models` pattern (executable, `ROOT = Path(__file__).resolve().parent.parent`, argparse, stdlib only — no `uv` package needed because there is no third-party dependency).

Pipeline:

1. **Collect inputs.** Glob `rules/common/*.md`, sorted by filename (lexical) for a canonical, deterministic order. No install-config coupling — every common rule is a candidate; the `tool:` allowlist decides which reach Codex.
2. **Classify.** For each file, split frontmatter with the split-on-`---` helper, then read the `tool:` key (scanning frontmatter lines, not a substring match against the whole block — a body or comment mention must not affect classification). A rule is included iff its `tool:` list contains `codex` (FR#2). Absent/other → fail-closed, excluded (FR#3).
3. **Render body.** Strip the frontmatter block from the body and prepend the `<!-- from <relpath> -->` source marker (FR#4).
4. **Assemble.** Join in sorted-filename order under the generated-file marker + precedence note (FR#5). Determinism follows from the sorted glob (FR#7). If no file is tagged for Codex, abort (edge case / AC#10).
5. **Write.** Resolve `$CODEX_HOME`/`~/.codex` (symlinks followed); if absent → skip (FR#9); if not a directory → error. Write **atomically**: write to `$CODEX_HOME/AGENTS.md.tmp` (same filesystem) then `os.replace()` onto the final path, wrapped so an OSError fails legibly. The existing file is overwritten unconditionally (no ownership check, no backup — see Non-Goals). Print summary (FR#8). The worktree guard (FR#10) runs before any of this when the default rules dir is used.

**Concrete rule changes (the classification data):** every `rules/common/*.md` carries an explicit `tool:` frontmatter — the fail-closed default (FR#3) makes the disposition a forced, greppable, single-source decision rather than a convention that can silently rot.
- The 9 Claude-Code-harness-specific files carry `tool: claude  # harness-only: <reason>` (self-documenting per-file reason): `capabilities-core`, `performance`, `interaction`, `sudo`, `tmux`, `command-output`, `bash-tools`, `worktrees`, `git-workflow`.
- The 20 portable files carry `tool: claude, codex, antigravity` (the `antigravity` token is documentary — this generator filters on `codex`; Antigravity is delivered via the `.agents/rules/` dir, a separate piece).
- **Split `git-workflow.md` into two files** (whole-file granularity, no fences):
  - `commit-conventions.md` (new, `tool: claude, codex, antigravity`) carries the portable sections: Git Command Style, Local Verification Before Commit, Bug Fix Commits, Commit Message Format. This recovers Conventional Commits + verification guidance for Codex. (Test discovery is inlined rather than pointing at the Claude-only `references/common/testing.md`.)
  - `git-workflow.md` (`tool: claude`) keeps the Claude-only sections: Pre-commit Hook Validation, Mandatory Code Review Before Commit, Code Reviewer Loop, Code Review vs Challenge, Issue Creation Conventions, Task File Cleanup, plus Worktree Baseline Testing and the Commit Attribution note (both moved here to keep the portability boundary clean — worktree dev and the `~/.claude/settings.json` attribution fact are Claude-specific). These plant directives Codex cannot satisfy (run the `code-reviewer`/`integration-reviewer`/`wtf-reviewer` agents; run `spec-helper archive`), which is exactly why the file must not reach Codex.
  - Both files live in `rules/common/`, so Claude auto-loads both — Claude's behavior is unchanged. The new file must be registered in `install.py`'s `workflow` rule category (alongside `git-workflow.md`) so the "every `rules/common/` file is mapped" test stays green.
- **`invariants.md` is portable** (`tool: claude, codex, antigravity`). It is mostly a checklist pointing at *other* rules ("Defined in: rules/common/X"), so for Codex it is redundant reinforcement of rules already included via `coding-style.md`/`python.md` — low harm. Its only Codex-irrelevant content (the Domain References "Read `~/.claude/references/...`" table and the Parallel Executor Isolation entry) is inert prose, not an actionable directive, so whole-file inclusion is acceptable rather than worth a split.
- No in-file fences. Disposition is per-file via `tool:`.

**Composition with the broader multi-tool sync:** this is piece 3 of 4. `install.py` orchestrates: (1) existing `~/.claude` symlinks, (2) skills → `~/.agents/skills/` symlinks [future], (3) this Codex AGENTS.md generation, (4) rulesync for Codex agents/hooks/permissions [future]. Each is independent; this design only adds (3) and its `install.py` call site.

## Replacement Targets

No existing behavior is replaced. The change is additive plus one behavior-preserving split: a new `bin/codex-rules-sync` script, a new `install.py` call site (a single call after the symlink phase — no refactor of install.py's selection logic), `tool:` frontmatter on all 29 rule files (Claude loads every rule regardless of `tool:`, so its behavior is unchanged), and the `git-workflow.md` → `git-workflow.md` + `commit-conventions.md` split (content moved, not removed). Because install.py is not restructured, no characterization pin is required beyond its existing passing test suite.

## Convention Examples

### Stdlib frontmatter parsing

**Source:** `bin/lint-agent-models`

```python
def parse_frontmatter(text: str) -> str:
    # Splitting on "---" yields ["", frontmatter, body] for a well-formed file.
    parts = text.split("---", 2)
    return parts[1] if len(parts) >= 3 and text.startswith("---") else ""
```

### Repo-root resolution for a bin script

**Source:** `bin/lint-agent-models`

```python
ROOT = Path(__file__).resolve().parent.parent
PERFORMANCE_MD = ROOT / "rules" / "common" / "performance.md"
```

## Test Strategy

### Existing Tests to Adapt
`tests/test_install.py` asserts every `rules/common/` file is mapped to a rule category. Adding `tool:` frontmatter does not change category mapping. The new `commit-conventions.md` must be added to the `workflow` category's `files` tuple in `install.py` for that assertion to pass — that is the only install.py change to the selection logic. install.py is not otherwise refactored.

### New Test Coverage
`tests/test_codex_rules_sync.py` (pytest, matching the repo convention), using fixture rule files in a temp dir and `$CODEX_HOME` pointed at a temp dir:
- `tool: claude, codex` includes; `tool: claude` and untagged exclude (FR#2, FR#3, fail-closed).
- a body/comment mention of `tool: codex` does **not** opt a `tool: claude` file in; quoted list items and an inline `# comment` after the value parse correctly.
- source markers present and correctly placed (FR#4); generated-file marker is the first line and the precedence note is present (FR#5); a separate test runs over the real `rules/common` to exercise the repo-relative marker path.
- determinism: two runs byte-identical (FR#7).
- missing Codex home → skip, no writes; exists-but-not-a-directory → error (FR#9).
- no rule tagged for Codex → abort, no write, no clobber of an existing file (edge case / AC#10).
- unclosed frontmatter → excluded (fail-closed) + warn, no stray `---`, no crash (edge case).
- summary reports counts and byte size (FR#8); `--list` prints the breakdown and writes nothing.
- worktree guard refuses the default rules dir from a worktree (FR#10; skipped when not run from a worktree checkout).
- An integration test, skipped when `codex` is not on PATH, writes a sentinel global file and asserts `codex debug prompt-input` includes head and tail sentinels (AC#6).

### Tests to Remove
No tests to remove.

## Documentation Updates

- **REFERENCE.md** — `bin/codex-rules-sync` in the bin/ scripts table; `commit-conventions.md` in the Rules table; a "Codex disposition" note explaining the `tool:` convention and `--list` as the runnable index.
- **CLAUDE.md** — a "Making Changes" bullet: every new `rules/common/` rule sets its `tool:` frontmatter (fail-closed default).
- **ONBOARDING.md** — the Codex AGENTS.md generation and the `tool:` disposition.
- **`rules/common/` files** — the `tool:` frontmatter (with a `# harness-only: <reason>` comment on Claude-only files) is the in-place, single-source documentation of each rule's disposition.
- **`bin/lint-cli-conventions`** — the new bin script passes the CLI-convention lint (pre-commit hook).

## Impact

### Changed Files
- `bin/codex-rules-sync` — create — the generator (stdlib Python), incl. `--list` and the worktree guard.
- `install.py` — modify — call the generator after the symlink phase and report it (failure surfaced in red); add `commit-conventions.md` to the `workflow` rule category. No refactor of selection logic.
- `rules/common/*.md` (all 29) — modify — add `tool:` frontmatter (`tool: claude  # harness-only: …` on the 9 Claude-only files, `tool: claude, codex, antigravity` on the 20 portable).
- `rules/common/git-workflow.md` — modify — keep Claude-only sections; gain Worktree Baseline Testing + Commit Attribution.
- `rules/common/commit-conventions.md` — create — the portable git/commit sections split out of `git-workflow.md`.
- `rules/common/{autonomous-run-discipline,debugging-discipline,verification}.md`, `skills/mine-commit-push/SKILL.md` — modify — repoint cross-references for the moved sections.
- `tests/test_codex_rules_sync.py` — create — unit + gated integration tests.
- `REFERENCE.md`, `ONBOARDING.md`, `CLAUDE.md` — modify — docs above.

### Behavioral Invariants
- Claude Code rule loading must be unchanged — adding `tool:` frontmatter must not alter how Claude consumes these rules (it injects them as text; the frontmatter is inert prose to Claude, which loads every rule regardless of `tool:`).
- `install.py` existing symlink/ownership behavior and its test suite must keep passing; the generator call is additive. Both install.py and the standalone generator refuse to run from a worktree against machine-global state.
- `lint-agent-models` and the category-mapping test must still pass after frontmatter is added.

### Blast Radius
- Writes one machine-local file (`~/.codex/AGENTS.md`), which composes as the global entry in Codex's AGENTS.md chain (a per-repo `AGENTS.md` may add to or override it — the precedence note in the generated file states this). No repo files are generated. Affects only the local Codex CLI's behavior. No CI, no other consumers. Worktree dev is safe: the generator refuses the default rules dir from a worktree, and tests target a temp `$CODEX_HOME`.

## Open Questions

None. The `tool:` allowlist (fail-closed default), the `git-workflow.md` split, the worktree guard, and the chain-precedence note were all decided in the challenge pass and folded into Architecture/Impact above. The soft-size warning was deliberately left out (the byte count already surfaces growth; a threshold is speculative for a self-policed rule set).
