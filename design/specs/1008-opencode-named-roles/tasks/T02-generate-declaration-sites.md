---
task_id: "T02"
title: "Generate performance.md and install.py from agent frontmatter"
status: "done"
depends_on: ["T01"]
implements: ["FR#8", "FR#9", "FR#10", "FR#11", "FR#23", "FR#29", "AC#6", "AC#7", "AC#18", "AC#22", "AC#28"]
---

## Summary

Collapse three agent-metadata declaration sites into one. Agent frontmatter becomes the single source of truth; `rules/common/performance.md`'s agent list and `install.py`'s per-bundle `agents=(...)` tuples become generated artifacts with a staleness check that fails when they diverge. `bin/lint-agent-models` is extended into the generator rather than a new script being added — it already parses all three sites in the same direction this generates. Agent files themselves are never written to. The obsolete "Skill files with inline model declarations" list and the check that validates it are deleted.

## Target Files

- modify: `bin/lint-agent-models` — becomes generator + staleness check + frontmatter completeness check; delete `SKILL_BULLET` (`:29`), its parse branch (`:66-67`), and its assertion loop (`:119-132`)
- modify: `rules/common/performance.md` — agent list becomes a generated region; delete the "Skill files with inline model declarations" list at `:69-83`
- modify: `install.py` — the per-bundle `agents=(...)` tuples become a generated region
- modify: `prek.toml` — wire the staleness and frontmatter-completeness checks
- create: `tests/test_lint_agent_models.py`
- modify: `tests/test_install.py` — bundle contents become generated
- read: `design/specs/1008-opencode-named-roles/design.md`
- read: `bin/opencode-sync` — `GENERATED_FILE_MARKER` convention at `:189`
- read: `tests/test_opencode_variant_audit.py` — the `runpy` test pattern for `bin/` scripts
- read: `agents/*.md` — the frontmatter the generator reads

## Prompt

Read `design/specs/1008-opencode-named-roles/design.md`, sections **Architecture → The declaration site**, **Implementation Preferences**, **Replacement Targets**, **Convention Examples**, and FR#8–11, FR#23, FR#29.

**1. Extend `bin/lint-agent-models` into a generator.**

It already parses agent frontmatter, `performance.md`'s list, and `install.py`'s bundle tuples, and already treats frontmatter as ground truth (`:41-44`, `:69-91`). Add:

- **Generation** — write `performance.md`'s agent declaration list and `install.py`'s per-bundle `agents=(...)` tuples from `agents/*.md` frontmatter, keyed on each file's `bundle:` field (added in T01).
- **A staleness check** — regenerate into memory, diff against what is on disk, exit non-zero on divergence (FR#11).
- **A frontmatter completeness check** — reject any agent file missing `model`, `effort`, `tools`, `description`, or `bundle`, naming the file and the missing field (FR#23).

Keep it a `uv run --script` file with inline PEP 723 metadata and stdlib-only imports. The existing docstring at `:33-36` explains why it parses `install.py`'s source rather than importing it — `install.py` pulls in `rich`/`questionary` that the pre-commit environment does not provide. That constraint still holds for generation: rewrite the tuples textually.

**2. Mark the generated regions.**

Follow the existing `GENERATED_FILE_MARKER` convention (`bin/opencode-sync:189`) in `performance.md` and `install.py`. Agent files get no marker — nothing in them is generated (FR#8, AC#22).

**3. Delete the skill-declarations list and its check (FR#29).**

`rules/common/performance.md:69-83` lists fourteen skill files and asserts each contains a literal `model: <tier>` clause. `bin/lint-agent-models` validates that via `SKILL_BULLET` (`:29`), parsed at `:66-67` and asserted at `:119-132`. T04 removes every one of those clauses, so the check would fail on all fourteen. Delete both the list and the check. Do not retarget the list to agent names — FR#18 already verifies every dispatched name resolves to a file, which is the only claim a retargeted list could still make. Update the surrounding prose in `performance.md` so the "Agent Model Declarations" section no longer instructs manual maintenance.

**4. Wire the checks as prek hooks.**

Follow the shape at `prek.toml:114-121` (`entry`, `language = "system"`, `pass_filenames = false`, `always_run = true`, `stages = ["pre-commit"]`). There is an existing `lint-agent-models` hook at `:87-90` — extend its entry rather than adding a duplicate hook if the same invocation covers the new checks.

**5. Test it.**

There is no `tests/test_lint_agent_models.py` today — this script is currently untested. Create one following `tests/test_opencode_variant_audit.py`'s pattern: `runpy` to load the script, `pytest.mark.parametrize` for cases, `tmp_path` for filesystem fixtures. Cover at minimum: idempotent generation (byte-identical output on repeated runs from unchanged input), the staleness check firing on a mutated artifact, and the completeness check naming a file missing `bundle`.

`tests/test_install.py` already compares `bundle.agents` as sets (`:491-492`, `:637`), so order-independence holds and those assertions should survive; adapt only what breaks.

## Focus

**Generation direction is the whole point — do not invert it.** An earlier draft of this design had a separate `agents.toml` generating agent frontmatter, and it was rejected as lossy. A whole-block frontmatter generator erases the trailing `model:` rationale comments that thirteen of twenty-three agent files carry — three of them explicit "do not downgrade; pre-commit safety gate" warnings at `agents/code-reviewer.md:3`, `agents/integration-reviewer.md:3`, `agents/testing-reality-checker.md:3` — and drops the `color:`/`emoji:`/`vibe:` keys six files carry outside the five-field schema. Generation reads frontmatter and writes the other two sites. Never the reverse.

**Generating `install.py` is safe, and here is why.** Its bundle tuples are pure declarative data with no order or index dependence (`install.py:1028-1043`, `:1129-1130`; the only other use is a cosmetic join at `:1479`). Persisted config stores bundle keys and booleans only (`:378-453`), never agent names, so bundle contents can change without touching existing installs, and the v1→v2 migration never reads them.

**Parsing gotcha already solved in the file.** `INSTALL_AGENTS_TUPLE` (`:37`) relies on bundle tuples being flat `agents=("a", "b", ...)` literals with no nested parens, which is what makes `[^)]*` reliable. Generated output must preserve that flatness or the script stops being able to re-read what it wrote.

**Ordering note.** This task runs before T04, so at generation time the skill files still contain their `model:` clauses. Deleting the `performance.md` skill list early is therefore harmless — it is stale in the other direction (the list is still accurate but about to stop being so), and deleting it now avoids a broken intermediate state after T04.

**T01 hand-added the three new agents** to `performance.md` and `install.py` to keep the tree green. This task supersedes those hand-edits with generated output; the generated result should match what T01 wrote, and a diff is the cheapest confirmation that generation is correct.

## Verify

- [ ] FR#8: No file in `agents/` contains a generated-region marker, and running the generator does not modify any file under `agents/`.
- [ ] FR#9: `rules/common/performance.md`'s agent declaration list is produced by the generator from agent frontmatter.
- [ ] FR#10: `install.py`'s per-bundle `agents=(...)` tuples are produced by the generator from agent frontmatter.
- [ ] FR#11: Mutating a generated artifact without regenerating makes the staleness check exit non-zero.
- [ ] FR#23: An agent file missing any of `model`, `effort`, `tools`, `description`, or `bundle` is rejected by name.
- [ ] FR#29: `grep -n 'Skill files with inline model declarations' rules/common/performance.md` and `grep -n 'SKILL_BULLET' bin/lint-agent-models` both return no matches.
- [ ] AC#6: Running the generator with no changes to any agent file leaves the working tree clean (`git diff --exit-code`).
- [ ] AC#7: Mutating one frontmatter field in one agent file and running the staleness check without regenerating exits non-zero.
- [ ] AC#18: Removing any of the five required fields from an agent file's frontmatter makes the generator exit non-zero with a message naming the file and the missing field.
- [ ] AC#22: No file in `agents/` contains a generated-region marker; `git diff` after running the generator shows changes only under `rules/common/performance.md` and `install.py`.
- [ ] AC#28: `grep -n 'Skill files with inline model declarations' rules/common/performance.md` and `grep -n 'SKILL_BULLET' bin/lint-agent-models` both return no matches, and `bin/lint-agent-models` exits 0 against the migrated tree.
