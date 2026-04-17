# Design: Challenge Caller Manifest Migration

**Date:** 2026-04-16
**Status:** approved
**Research:** design/research/2026-04-16-challenge-caller-manifest/research.md

## Problem

The per-finding resolution manifest flow (spec 015, `findings-protocol.md`) eliminates bundled AskUserQuestion prompts by giving users an editor-based interface to set verbs per finding. But this flow only covers standalone `/mine.challenge`. Three callers bypass it with their own bundled gates:

- **mine.specify** (SKILL.md:378-389): `Apply all / Let me cherry-pick / Skip revisions` — Anti-Patterns #1 (bundling), #4 (meta-gate), #8 (bail-out)
- **mine.design** (SKILL.md:314-326): identical bundled gate, synced via `<!-- SYNC: -->` marker with specify
- **mine.orchestrate** (SKILL.md:783-794): `Address findings / Accept and ship / Stop here` — bundles all challenge findings into one "fix everything" dispatch to a subagent, with no per-finding user control

Spec 015 explicitly deferred caller migration as future work. This design completes it.

## Non-Goals

- Migrating `mine.tool-gaps` or `mine.visual-qa` (on the explicit migration-exempt list in `findings-protocol.md:294`)
- Changing the standalone `/mine.challenge` flow contract
- Redesigning the verb vocabulary
- Changing `bin/edit-manifest`

## Architecture

### Shared protocol: `skills/mine.challenge/caller-protocol.md`

New protocol file, peer to `findings-protocol.md`, at `skills/mine.challenge/caller-protocol.md`.

**Scope**: Covers structured doc-edit callers (mine.specify, mine.design) and code-fix callers (mine.orchestrate). Inline-revision callers (`i-*` family) are out of scope — they do not generate manifests and do not use `--findings-out`. See `skills/mine.challenge/SKILL.md` Known Callers section for the full caller taxonomy.

**Content specification** (required sections in `caller-protocol.md`):

1. **Scope statement** — which caller types this protocol covers and which it excludes
2. **Unified caller flow** — the shared sequence (pre-routing → manifest → editor → detection → validation → commit gate → execution → post-execute hooks)
3. **Doc target field** — format spec (`<doc-name> SS <section-name>`), matching algorithm, and error handling
4. **Pre-execution validation pass** — verify all Doc target sections exist before applying any edits
5. **Doc-edit verb execution table** — per-verb action table for doc-edit callers, including the TENSION+fix row
6. **Code-fix verb execution table** — per-verb action table for orchestrate, including fix brief format
7. **Per-verb execution logging** — same format as standalone (`{timestamp} verb_executed finding={id} verb={verb} result=...`), required for all callers
8. **Post-execute hook protocol** — extension point specification, trigger conditions, worked examples
9. **Compaction recovery** — resume detection via orphaned manifest
10. **Worked examples** — one doc-edit example (Auto-apply + TENSION + User-directed manifest), one code-fix example (orchestrate fix brief generation)

All four files (`caller-protocol.md` + three caller SKILL.md updates) MUST ship in one commit.

**Location rationale**: Commit `a5026f0` moved `findings-protocol.md` OUT of `rules/common/` because auto-loading added ~144KB per challenge run. `caller-protocol.md` MUST NOT go into `rules/common/` — it stays in `skills/mine.challenge/` and is loaded on-demand via explicit `Read`.

Callers reference it via `${CLAUDE_HOME:-~/.claude}/skills/mine.challenge/caller-protocol.md`. Each caller's SKILL.md MUST include an explicit `Read` instruction: "Read `${CLAUDE_HOME:-~/.claude}/skills/mine.challenge/caller-protocol.md` before proceeding with the manifest flow." This prevents LLMs from following remembered protocol instead of the live file.

### Unified caller flow

All three callers follow the same structural pattern. The differences are in the pre-routing pass and verb execution, not the protocol mechanics.

```
Challenge returns findings.md (unchanged contract)
       |
       v
Caller pre-routing pass (CALLER-SPECIFIC)
  - Read each finding's contract tags
  - Compute default verb + Doc target per finding
       |
       v
Caller writes <tmpdir>/resolutions.md
  - Manifest format from findings-protocol.md
  - Each section has **Doc target:** field
       |
       v
Consent Gate (reused from findings-protocol.md)
       |
       v
bin/edit-manifest (unchanged contract)
       |
       v
Detection + Validation + Commit Gate (reused)
       |
       v
Caller verb execution (CALLER-SPECIFIC)
       |
       v
Post-execute hooks (CALLER-SPECIFIC)
       |
       v
Return to caller's sign-off gate
```

### Doc-edit callers (mine.specify, mine.design)

**Verb execution:**

| Verb | Action |
|---|---|
| `fix` (Auto-apply) | Apply `better-approach` text edit to Doc target location via Edit tool |
| `fix` (User-directed) | Apply recommendation to Doc target location |
| `fix` (TENSION) | Emit one AskUserQuestion presenting `side-a` and `side-b` as options with `deciding-factor` as context; apply the chosen option's edit to the Doc target location |
| `A`/`B`/`C` | Apply chosen option's edit to Doc target location |
| `ask` | Emit one AskUserQuestion with finding's options; apply chosen action |
| `file` | Batched `gh-issue create` (Phase 2, identical to standalone) |
| `defer` | Record in session summary; no doc edit (uniform semantics) |
| `skip` | Record in session summary; no doc edit |

All doc edits reference the **Doc target** field for the target file and section. Callers MUST log each verb execution to `<tmpdir>/editor-log.md` using the same format as standalone: `{timestamp} verb_executed finding={id} verb={verb} result={applied|filed|ask-issued|deferred|skipped|error}`. On failure mid-execution, callers read the log to determine which findings already applied and offer to resume from the first unexecuted finding.

**Post-execute hooks (mine.specify):**
1. Sweep findings where Doc target contains "Open Questions" AND `verb: defer` — append bullets to the specified doc's `## Open Questions` section (spec.md or design.md, per the Doc target)
2. Re-run 12-item quality validation on updated spec

**Post-execute hooks (mine.design):**
1. Sweep findings where Doc target contains "Open Questions" AND `verb: defer` — append bullets to design.md `## Open Questions`

The `defer` verb stays uniform ("no action, record in summary"). The OQ-append is a post-execute caller hook triggered by the Doc target field, not by verb semantics. Because TENSION findings have their Doc target populated with the actual OQ destination (e.g., `spec.md SS Open Questions`), the user sees the routing in the manifest editor and can change it — setting `verb: skip` or changing the Doc target prevents the OQ-append. This keeps verb definitions clean while making routing visible and controllable.

### Code-fix caller (mine.orchestrate)

**Verb execution (split dispatch):**

| Verb | Handled by |
|---|---|
| `fix`/`A`/`B`/`C` | Collected into a focused fix brief; dispatched to fresh subagent |
| `ask` | Resolved via AskUserQuestion before dispatch; result feeds subagent or file/defer/skip |
| `file` | Orchestrator batches `gh-issue create` |
| `defer`/`skip` | Orchestrator records in session summary |

The subagent receives ONLY the fix-verb findings — not the full findings file. This is a strict improvement: today the subagent gets all findings and is told to "fix only the listed findings" (no filtering); after migration, the subagent gets a pre-filtered set matching exactly what the user approved.

**Fix brief format**: The fix brief is a filtered copy of `<tmpdir>/challenge-findings.md` containing only the `## Finding N:` blocks whose corresponding manifest entry has verb `fix`, `A`, `B`, `C`, or (resolved) `ask`. Write to `<tmpdir>/challenge-fix-brief.md`. Pass this path to the subagent via the `**Findings files to read:**` field in the retry-prompt template. Using the same findings.md format makes subagent parsing trivial.

**The subagent's existing context** is preserved alongside the fix brief: design.md, WP files, `implementer-prompt.md`, `retry-prompt.md`, `tdd.md`. The fix brief replaces the current unfiltered challenge findings handoff.

**Impl-review suggestions** remain separate. They are not structured as challenge findings and do not enter the manifest. The subagent receives them as unstructured context alongside the fix brief, same as today.

**Re-challenge cycle**: After the subagent completes, the existing re-test → re-review → re-challenge loop continues unchanged. Each re-challenge produces a new findings file and a new manifest — manifest files MUST use iteration-suffixed paths matching their findings file (`resolutions-2.md` alongside `challenge-findings-2.md`). Callers are responsible for path uniqueness, same rule as already stated for findings files. The prior manifest is complete.

### Manifest section format

The three existing templates from `findings-protocol.md` are reused with one addition: a `**Doc target:**` field after the severity/type/raised-by line.

**Auto-apply (doc-edit caller):**
```markdown
## F3: Acceptance criterion is untestable
**Severity:** HIGH | **Type:** Gap | **Raised by:** Senior (1/5)
**Doc target:** spec.md SS Acceptance Criteria

**Problem:** AC-4 says "respond quickly" with no measurable threshold.

**Why it matters:** Cannot verify implementation against this AC.

**Better approach:** Edit spec.md SS Acceptance Criteria AC-4: "respond quickly" -> "Respond within 200ms p95 under 100 RPS load."

**Verb:** fix
```

**Auto-apply (orchestrate — code finding):**
```markdown
## F2: Missing retry logic on external API call
**Severity:** HIGH | **Type:** Fragility | **Raised by:** Adversarial Reviewer (2/5)
**Doc target:** (code)

**Problem:** user_service.py:47 calls the auth API with no retry.

**Why it matters:** Transient failures propagate to callers.

**Better approach:** Add exponential backoff with 3 retries in user_service.py:47.

**Verb:** fix
```

**Doc target field format**: one-line string.
- Doc-edit callers: `<doc-name> SS <section-name>` (e.g., `spec.md SS Acceptance Criteria`, `design.md SS Open Questions`)
- Orchestrate: `(code)` — code findings target specific files/lines described in Problem/Better approach
- Non-edit findings: `(none -- flag for implementation)`

The `SS` delimiter is a human-readable section separator. **Matching algorithm** (specified in `caller-protocol.md`): section lookup uses case-insensitive prefix match against `## <section-name>` headings in the target file. If not found, surface a named error: "Section `<section-name>` not found in `<doc-name>` — Revise manifest or skip this finding?" If multiple headings match, use the first match. Empty sections are valid targets (content is inserted after the heading).

**Pre-execution validation pass**: Before executing any verb, scan all `fix`/`A`/`B`/`C` verb rows in the resolved manifest and verify their Doc target sections exist in the target file. If any section is unresolvable, surface all failures before applying a single edit. This converts mid-execution corruption into a pre-execution abort. After validation passes, verb execution proceeds in manifest order.

### Pre-routing tables

**mine.specify:**

| Finding property | Default verb | Doc target |
|---|---|---|
| `severity: TENSION` | `defer` | `spec.md SS Open Questions` |
| `design-level: Yes` + routes to spec (functional reqs, goals, user scenarios, ACs, non-goals) | `fix` / letter / `ask` (per Default Verb Selection) | `spec.md SS <section>` |
| `design-level: Yes` + routes to design (architecture, data model, API) | `defer` | `design.md SS Open Questions` |
| `design-level: No` | `skip` | `(none -- flag for implementation)` |

**mine.design:**

| Finding property | Default verb | Doc target |
|---|---|---|
| `severity: TENSION` | `defer` | `design.md SS Open Questions` |
| `design-level: Yes` | `fix` / letter / `ask` | `design.md SS <section>` |
| `design-level: No` | `skip` | `(none -- flag for implementation)` |

**mine.orchestrate:**

| Finding property | Default verb | Doc target |
|---|---|---|
| `severity: TENSION` | `file` | `(none -- TENSION, files as issue)` |
| `resolution: Auto-apply` | `fix` | `(code)` |
| `resolution: User-directed` + recommendation present | option letter | `(code)` |
| `resolution: User-directed` + no recommendation | `ask` | `(code)` |

### SYNC marker elimination

Delete `<!-- SYNC: -->` markers from:
- `skills/mine.specify/SKILL.md:343`
- `skills/mine.design/SKILL.md:287`

Replace the bundled gate section in each caller with an explicit `Read` instruction and delegation: "Read `${CLAUDE_HOME:-~/.claude}/skills/mine.challenge/caller-protocol.md`, then follow the manifest flow defined there."

Content that remains inline per caller (irreducibly specific):
- **mine.specify**: spec-vs-design routing heuristic, deferred findings persistence to design.md stub, 12-item re-validation
- **mine.design**: section routing within design.md, prior spec-challenge deferred-findings merge
- **mine.orchestrate**: split-dispatch logic, subagent context assembly, re-challenge cycle

### Compaction recovery

If context compacts between Consent Gate and verb execution, callers MUST NOT regenerate the manifest — doing so loses all user verb edits. Recovery procedure (specified in `caller-protocol.md`):

1. Before generating a new manifest, check for an existing `<tmpdir>/resolutions.md`
2. If the file exists and is non-empty, skip manifest generation and the Consent Gate
3. Re-read the existing manifest and proceed directly to Detection Logic
4. Each caller's SKILL.md references this section

This mirrors orchestrate's checkpoint-read detection pattern (`skills/mine.orchestrate/SKILL.md` "Resuming after context compaction" section).

### Routing heuristic precision

The spec-vs-design routing heuristic in mine.specify currently uses prose categories ("routes to spec if finding implicates functional requirements"). After migration, this heuristic determines the Doc target field, which feeds the verb executor's Edit tool call. To prevent wrong-document edits:

- When the routing heuristic cannot unambiguously classify a finding, default the verb to `ask` — this emits an AskUserQuestion at execution time, converting routing ambiguity into a user prompt rather than a silent wrong-document edit
- The manifest editor serves as a secondary safety valve: users can correct wrong Doc targets before execution

### Discoverability

Add a pointer in `findings-protocol.md` Skill-Specific Overrides section:

> For doc-edit and code-fix callers (mine.specify, mine.design, mine.orchestrate), see `skills/mine.challenge/caller-protocol.md`.

This keeps the primary protocol file as the entry point for discovering the caller extension.

### Protocol versioning

Bump `findings-protocol.md` `manifest-protocol-version` from 1 to 2 as a changelog marker (not a runtime contract, per the protocol file's own annotation). The version bump signals the Doc target field addition and caller-protocol extension.

**Note**: The findings file `Format-version` (currently 2, checked by callers) is independent of `manifest-protocol-version`. The Doc target field lives in the manifest (`resolutions.md`), not in the findings file. No `Format-version` bump is needed — the findings file format has not changed. Do not conflate these two version signals.

## Alternatives Considered

### A2: New `--manifest-interactive` mode on `/mine.challenge`

Challenge handles manifest + editor + detection + commit gate internally, then returns the resolved manifest to the caller for execution.

**Rejected**: No existing pattern for a skill running a mid-flow handoff and returning state. Manifest tmpdir ownership crosses a skill boundary. Risks regressing the perf win from commit `a5026f0`. Adds a new contract surface that must survive compaction.

### A3: Full inheritance — challenge executes for all callers

Challenge learns to edit spec.md, design.md, and dispatch orchestrate subagents.

**Rejected**: Violates single-responsibility. Massive coupling — any change to caller workflows would require challenge changes. Challenge's job is producing findings, not editing documents or orchestrating subagents.

### `defer` overlay instead of post-execute hook

Make `defer` mean "append to Open Questions" when Doc target is an OQ section.

**Rejected**: Overloads `defer` with context-dependent semantics. The post-execute hook approach keeps verb definitions uniform across all contexts. The user can't change TENSION-to-OQ routing in the current flow either, so no functionality loss. Simpler to explain and harder to misimplement.

## Test Strategy

Session-level manual validation (same category as spec 015 — no unit tests for skills/rules).

**Validation scenarios:**

1. **mine.specify**: Run `/mine.specify` on a draft spec -> "Challenge this spec first" -> verify:
   - Manifest sections have Doc target fields
   - TENSION findings default to `defer`
   - `design-level: No` findings appear as `skip` with rationale
   - Post-execute hook appends TENSION findings to spec.md Open Questions
   - Deferred design-phase findings persist to design.md stub
   - No bundled "Apply all / Cherry-pick / Skip revisions" gate appears

2. **mine.design**: Same flow via "Challenge this design" -> verify identical manifest mechanics with design.md targeting

3. **mine.orchestrate**: Run through orchestration to auto-challenge step -> verify:
   - Manifest replaces bundled "Address findings" gate
   - User can set individual verbs per finding
   - Subagent receives only fix-verb findings (not the full set)
   - `file` verbs create GH issues
   - `defer`/`skip` findings don't reach the subagent
   - Re-challenge cycle produces a fresh manifest

4. **Negative**: Anti-patterns #1, #4, #8 are absent from all three callers

5. **Compaction recovery**: Simulate compaction mid-flow by manually resuming from a pre-existing `resolutions.md` — verify caller detects the orphaned manifest, skips regeneration, and proceeds to Detection Logic

6. **Regression**: standalone `/mine.challenge` flow unchanged

## Open Questions

- [ ] Should `ask` verbs in orchestrate be resolved before dispatching the subagent, or should the subagent resolve them? Recommendation: before — the manifest contract says `ask` emits one AskUserQuestion at execution time, and the orchestrator is the executor.
- [ ] Should `caller-protocol.md` include worked examples for all three callers or dedicate separate sections? Recommendation: one section per caller flavor (doc-edit, code-fix) with one worked example each.
- [ ] Cap at two protocol files (`findings-protocol.md` + `caller-protocol.md`). If a third variant is needed in the future, restructure into core + overlays before expanding.

## Impact

**New files:**
- `skills/mine.challenge/caller-protocol.md`

**Modified files:**
- `skills/mine.specify/SKILL.md` — replace ~70 lines of bundled gate (lines 339-412) with ~15 lines delegation + ~30 lines verb executor
- `skills/mine.design/SKILL.md` — replace ~50 lines (lines 283-334) with ~15 + ~25 lines
- `skills/mine.orchestrate/SKILL.md` — replace ~25 lines of bundled gate (lines 776-803) with ~20 lines manifest flow + split-dispatch logic
- `skills/mine.challenge/findings-protocol.md` — add pointer in Skill-Specific Overrides, bump protocol version, add `Doc target` as an optional field to the three manifest templates (one line each: "**Doc target:** _optional, caller-populated_")
- `skills/mine.challenge/SKILL.md` — update Known Callers descriptions for mine.specify, mine.design to note they use the manifest flow via `caller-protocol.md`
- `skills/mine.orchestrate/retry-prompt.md` — update `**Findings files to read:**` template to reference the filtered fix brief path (`<tmpdir>/challenge-fix-brief.md`)

**Unchanged:**
- `bin/edit-manifest`
- Standalone challenge flow

**SYNC markers deleted:** 2 (one in specify, one in design)
**Net lines:** decrease (~50-80 lines removed across callers; `caller-protocol.md` expected shorter than `findings-protocol.md` (412 lines) since it delegates the core flow to that file and references rather than repeats the manifest format spec)
