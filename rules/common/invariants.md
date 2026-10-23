# Design Invariants

Named invariants that must hold across all code written in this setup. Each is defined in the rule or reference file named after it; this file promotes them to a proactive checklist. Entries pointing at `rules/common/` are summaries of text normally already loaded; entries pointing at `references/common/` are the only always-present surface for guidance that otherwise loads on demand.

## When to Check

Scan this list at two points: **before writing code** (catch structural violations before they're written) and **before claiming completion** (catch process violations before they're committed). Not a gate requiring explicit confirmation — just a mental pass at each point.

## Severity Tiers

- **Must** — no exceptions. Always a violation. Fix before committing.
- **Should** — wrong unless there's a documented, deliberate reason. If you're violating this, you can articulate why.
- **Consider** — worth a quick check. Neither right nor wrong — context decides.

## Invariant Library

Bare filenames are in `rules/common/`; others are prefixed `references/common/` (both under `${CLAUDE_CONFIG_DIR:-~/.claude}/` when installed).

### Must

- **Immutability** — create new objects, never mutate existing ones; PySpark DataFrame reassignment is exempt. (`coding-style.md`)
- **No Compatibility Shims for Convenience** — never keep an old name, field, or re-export alive just to avoid updating its references (tests and imports included); migrate every caller, then delete the old path (the staged sequence in `sequence-verifiable-units.md` is fine; an old path outliving it is not). Exception: the thing itself is part of a declared, versioned public API or a wire format another system parses. Internal helpers and tests never qualify. (`coding-style.md`)
- **No Future Annotations** — never add `from __future__ import annotations`; it breaks Pydantic, FastAPI, dataclasses, and runtime type inspection. (`python.md`)
- **No Optional[X]** — use `X | None`. (`python.md`)
- **No Lazy Imports** — all imports at the top of the file; only `TYPE_CHECKING` guards are exempt. (`python.md`)
- **Mock at Boundaries Only** — mock external APIs, databases, time, filesystem; use real instances for internal collaborators. (`references/common/testing.md`)
- **Dependencies as Parameters** — functions and classes receive collaborators as parameters rather than creating them inline. If testing needs `mock.patch` more than one level deep, restructure. (`references/common/dependency-injection.md`)
- **No Log Capture Tests** — test the behavior that produces the log, not the log output. (`references/common/testing.md`)
- **Evidence Before Claims** — never claim work is done without command output proving it. (`verification.md`)
- **No `any`** (TypeScript) — use `unknown` for external data and narrow before use. (`references/common/typescript.md`)
- **No `as` Casts** (TypeScript) — except after full validation at system boundaries, and branded type constructors whose preceding validation is the only path to the type. (`references/common/typescript.md`)
- **No Enums** (TypeScript) — use `as const` objects or union types. (`references/common/typescript.md`)
- **Functional Components Only** — no React/Preact class components. (`references/common/frontend.md`)
- **Effect Cleanup** — every `useEffect` that subscribes, listens, or opens a connection returns a cleanup function. (`references/common/frontend.md`)
- **Input Validation at Boundaries** — external data (user input, API responses, file reads, env vars) is validated and parsed at the boundary; internal code trusts it. (`references/common/security.md`)
- **Timeouts on External Calls** — every external call has an explicit timeout. (`references/common/reliability.md`)
- **Shared State Protection** — first ask whether sharing is necessary; if not, give each actor its own state. When it is, protect it with locks, queues, or atomic operations. (`references/common/reliability.md`)
- **Parallel Executor Isolation** — 2+ subagents writing to the git working directory in parallel each use `isolation: "worktree"` — shared directories lose changes to index races and pre-commit stash collisions. (`references/common/agents.md`)
- **Library Code Never Configures Logging** — imported modules call `logging.getLogger()` and nothing else; no `basicConfig()`, handlers, or `setLevel()`. (`logging.md`)

### Should

- **Test Co-location** — code and its unit tests ship in the same commit; integration tests may follow. Exempt: generated code, type definitions, config, constants, `__init__.py`, docs-only changes, logic-free migrations. (`references/common/testing.md`)
- **Errors Surfaced Not Swallowed** — every error path is handled or propagated; for intentional suppression use `contextlib.suppress` with a specific exception type. (`references/common/reliability.md`)
- **Reproduce Before Fixing** — reproduce a bug yourself before designing a fix. (`debugging-discipline.md`)
- **"Pre-existing" Means Verified Against the Default Branch** — verify against the actual default branch (`git-default-branch`, not `git-branch-base`), not a stash or an earlier commit on this branch. Doesn't apply to measurement baselines. (`pre-existing-verification.md`)
- **Pause Safely on Unplanned Interruption** — stop at an atomic boundary, commit with `wip:`, write `/tmp/<slug>-resume.md`, report position. (`pause-safely.md`)
- **Pin Behavior Before Refactoring** — capture current behavior with a characterization test first; type checks and lint are not a pin. (`refactoring-discipline.md`)
- **Exit Condition Before Iterating** — define done as a checkable predicate before a long-running task's first iteration. (`autonomous-run-discipline.md`)
- **Self-Contained Comments** — no narrating incidents or reviewer catches; state the durable invariant. (`coding-style.md`)
- **No Dark Operations** — every non-re-raising `except` and every external I/O boundary logs its outcome on failure. (`logging.md`)
- **Verify Review Findings Before Accepting** — check each finding against the actual code before implementing; reviewers make mistakes. If a suggested abstraction has no callers outside the changed files, skip it. (`references/common/receiving-code-review.md`)
- **Mandatory Challenge in Sketch** — challenge runs at sketch time and at ship time in `mine-sketch`'s build mode, and is never offered as optional. (`git-workflow.md`)

### Consider

Defined in `rules/common/` files, so this tier is a scan list only: **Laziness Protocol, Reader Load, Redesign from First Principles, Outcome-Oriented Execution, Encode Lessons in Structure, Exhaust the Design Space, Sketch Before Building, Sequence Verifiable Units, Experience First, Baseline Before Optimizing, Decompose Before Implementing, No Default Underscore Prefixes, Build the Lever, Model the Domain, File Size** (past ~800 lines: note a follow-up, don't refactor mid-change; functions <50 lines, nesting <4 levels).

These three live in on-demand `references/common/` files, so their summaries stay:

- **AI Prose Self-Audit** — after writing non-code text, ask "what makes this obviously AI-generated?" and fix it. Common tells: em dashes, hedging, significance inflation, synonym cycling. (`references/common/writing-quality.md`)
- **Screenshot Before and After UI Changes** — screenshot affected and sibling pages before and after; visual bugs only show in screenshots. (`references/common/frontend.md`)
- **Instruction Quality Checks** — when writing rules or skills, apply proportionally: diagnostic questions over thresholds, named failure modes, AI-bias acknowledgment, a generative value, "why" before "what", room for judgment. (`references/common/instruction-quality.md`)

## Domain References

**BLOCKING REQUIREMENT**: Before starting work that matches a row below, Read the reference file under `${CLAUDE_CONFIG_DIR:-~/.claude}/references/common/`. Do NOT proceed with domain work without loading the relevant guidance first.

| When working with... | Read |
|----------------------|------|
| `.ts`, `.tsx`, `.js`, `.jsx` files | `typescript.md` |
| Frontend components, CSS, UI | `frontend.md` |
| Backend services, async code, retries | `reliability.md`, `dependency-injection.md` |
| Tests, TDD, pytest | `testing.md` |
| Prose: PR descriptions, docs, skills, rules | `writing-quality.md` |
| Subagent orchestration, parallel executors | `agents.md` |
| Processing code review findings | `receiving-code-review.md` |
| Writing rules or skill files | `instruction-quality.md` |
| Asking the user to pick among options with a recommendation | `presenting-decisions.md` |
| API endpoints, auth handlers, user input | `security.md` |
| User-facing CLI tools: commands with flags, subcommands, help text, output design | `cli-ux.md` |
| Authoring `REVIEW.md` review-question files | `review-questions.md` |

## Adding Invariants

When a code review catches the same violation more than once, or a new rule is added that should be checked proactively, add a one-line entry under the right tier ending with its defining file. Keep Must items tight — they're the "never violate" set.
