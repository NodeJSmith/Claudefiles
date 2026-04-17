<!-- caller-protocol-version: 1 -->
<!-- Increment the protocol version above on any change to verb execution
     semantics, hook behavior, or manifest format. This is a maintainer
     changelog marker — not a runtime contract; no skill checks this value
     at runtime. -->

# Caller Protocol — Doc-Edit and Code-Fix Callers

Extension protocol for skills that consume challenge findings and execute resolutions against structured targets. Peer to `findings-protocol.md`, which defines the core manifest format, verb vocabulary, Consent Gate, editor session, Detection Logic, Manifest Validation, Commit Gate, and Re-edit Loop Cap — all reused here without modification.

> **Cap at two protocol files.** If a third variant is needed, restructure into core + overlays first.

## 1. Scope

This protocol covers two caller families:

- **Doc-edit callers** (mine.specify, mine.design) — findings target sections of a structured document (spec.md, design.md). Verb execution applies text edits to the named section.
- **Code-fix callers** (mine.orchestrate) — findings target code locations. Verb execution dispatches a focused fix brief to a subagent.

**Out of scope**: Inline-revision callers (`i-*` family) do not generate manifests and do not use `--findings-out`. See `SKILL.md` Known Callers section for the full caller taxonomy.

## 2. Unified Caller Flow

All three callers follow the same structural sequence. Caller-specific logic is confined to the pre-routing pass and verb execution phase.

```
Challenge returns findings.md (unchanged contract)
       |
       v
Caller pre-routing pass (CALLER-SPECIFIC)
  - Read each finding's contract tags (severity, resolution, recommendation, design-level)
  - Compute default verb + Doc target per finding
  - When a finding plausibly targets multiple sections, default to ask — do not best-fit
       |
       v
Caller writes <tmpdir>/resolutions.md
  - Manifest format per findings-protocol.md
  - Each section includes **Doc target:** field
       |
       v
Consent Gate (per findings-protocol.md)
       |
       v
bin/edit-manifest (unchanged contract)
       |
       v
Detection + Validation + Commit Gate (per findings-protocol.md)
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

**Deriving `<section>` for Doc targets:** Derive `<section>` from the finding's evidence field (file:line or section references) when available; fall back to inferring from the finding's summary and type fields. When a finding plausibly targets multiple sections (content spans two or more categories), the pre-routing pass MUST default to `ask` — do not attempt to pick the best-fit section. The manifest editor is a secondary safeguard, not the primary mechanism for catching misrouted Doc targets.

**Shared mechanics reused from `findings-protocol.md`** (do not re-implement):
- Verb Vocabulary and Default Verb Selection tables
- Resolution Manifest format and Manifest Header Format
- Consent Gate (including zero-findings guard)
- Editor Session (pre-hash, editor invocation, tertiary fallback)
- Detection Logic (hash comparison, shadow file handling)
- Manifest Validation Spec (verb check, ID check, option letter check, deleted row handling)
- Commit Gate
- Re-edit Loop Cap
- Per-verb execution logging format
- Named Anti-Pattern Catalog

## 3. Manifest Header Extension — Base Dir

In addition to the standard manifest header fields from `findings-protocol.md`, caller manifests include:

```
**Base dir:** <absolute-path-to-feature-dir>
```

Placed after the `<!-- Valid verbs: ... -->` comment and before the first `## F` section. The pre-routing pass populates this with the absolute path to the feature directory (e.g., `/home/user/project/design/specs/001-user-auth/`). The verb executor uses this to resolve bare filenames in Doc targets (e.g., `spec.md` resolves to `<Base dir>/spec.md`). This field survives compaction — the executor does not need in-context memory to locate the target files.

## 4. Doc Target Field

Each manifest section includes a `**Doc target:**` field immediately after the severity/type/raised-by line and before `**Problem:**`. This field tells the verb executor where to apply edits.

### Format

One-line string. Three forms:

| Caller type | Format | Example |
|---|---|---|
| Doc-edit | `<doc-name> SS <section-name>` | `spec.md SS Acceptance Criteria` |
| Code-fix | `(code)` | `(code)` |
| Non-edit | `(none -- <reason>)` | `(none -- flag for implementation)`, `(none -- TENSION, files as issue)` |

The `SS` delimiter is a human-readable section separator.

### Matching Algorithm

When a verb executor resolves a Doc target of the form `<doc-name> SS <section-name>`:

1. Open `<doc-name>` (relative to the `**Base dir:**` from the manifest header; fall back to working directory if Base dir is absent)
2. Scan for `## <section-name>` headings using **case-insensitive prefix match**
3. **First match wins** — if multiple headings match the prefix, use the first occurrence
4. **Empty sections are valid targets** — content is inserted after the heading
5. **Section not found**: surface a named error: `"Section '<section-name>' not found in '<doc-name>' -- Revise manifest or skip this finding?"`

The user can correct Doc targets in the manifest editor before execution. The matching algorithm runs at execution time, not at manifest generation.

## 5. Pre-Execution Validation Pass

Before executing any verb, scan all manifest rows whose verb is `fix`, `A`, `B`, or `C`. For each:

1. Verify the Doc target is present and well-formed (matches `<doc-name> SS <section-name>`, `(code)`, or `(none -- <reason>)`). If the Doc target is blank, malformed, or missing on an edit verb, treat as a validation failure — route to "Revise manifest" rather than proceeding with an unresolvable target.
2. For Doc targets using the `<doc-name> SS <section-name>` format: verify the target file exists
3. Verify the named section resolves via the matching algorithm (section 4)

If **any** section is unresolvable, surface **all** failures before applying a single edit:

```
Unresolvable Doc targets:
  - F2: spec.md SS Acceptance Critiera  -> no matching section (typo?)
  - F5: design.md SS Data Modle         -> no matching section (typo?)

Revise the manifest to fix these Doc targets, or change their verbs to skip/defer.
```

This converts mid-execution corruption into a pre-execution abort. After validation passes, verb execution proceeds in manifest order.

`ask` verbs are excluded from pre-validation — for doc-edit callers, their Doc target is resolved after the user responds; for the code-fix caller, `ask` verbs carry `(code)` as the Doc target and are resolved before subagent dispatch per section 7. For doc-edit callers, `ask`-verb findings with a blank Doc target must be caught at execution time per §6's routing ambiguity case — the executor must not attempt an edit without a resolved Doc target. `file`, `defer`, and `skip` verbs do not reference Doc targets for edits.

## 6. Doc-Edit Verb Execution Table

For doc-edit callers (mine.specify, mine.design). Each verb applies an edit to the Doc target location via the Edit tool.

| Verb | Action |
|---|---|
| `fix` (Auto-apply) | Apply `better-approach` text edit to Doc target section via Edit tool. When `better-approach` is a natural-language description that cannot be resolved to a specific `old_string`, emit an `ask` prompt presenting the proposed text rather than attempting a blind Edit tool call. |
| `fix` (User-directed) | Apply recommendation to Doc target section via Edit tool |
| `fix` (TENSION) | Emit one AskUserQuestion presenting `side-a` and `side-b` as options with `deciding-factor` as context; apply the chosen option's edit to the Doc target section |
| `A` / `B` / `C` | Apply the chosen option's edit to Doc target section via Edit tool |
| `ask` | Emit one AskUserQuestion with the finding's options; apply chosen action to Doc target section. If the user picks "File as issue" or "Skip", handle identically to `file`/`skip` verbs — no doc edit, record in session summary and file-verb batch respectively. When the Doc target is also unresolved (routing ambiguity case — Doc target field is blank in the manifest), the AskUserQuestion must include the target document/section as part of the options or ask separately after the verb choice. |
| `file` | Batched `gh-issue create` (Phase 2, identical to standalone per `findings-protocol.md`) |
| `defer` | Record in session summary; no doc edit |
| `skip` | Record in session summary; no doc edit |

**TENSION + fix**: When a user explicitly changes a TENSION finding's default verb from `defer` to `fix`, the executor treats it as an interactive resolution. Read `side-a` and `side-b` from the findings file (path from manifest header or Base dir) before presenting AskUserQuestion — do not attempt to parse them from the manifest's `**The disagreement:**` prose. Present the tension's sides for the user to choose. After the user chooses, re-compute the Doc target at execution time: scan the chosen side's text for the section under debate, then emit an AskUserQuestion asking where to apply the chosen approach (since the pre-routing Doc target of "Open Questions" is incorrect for a fix action). This matches the standalone execution semantics defined in `findings-protocol.md`.

## 7. Code-Fix Verb Execution Table

For the code-fix caller (mine.orchestrate). Verb execution uses a split-dispatch pattern.

| Verb | Handled by |
|---|---|
| `fix` / `A` / `B` / `C` | Collected into a focused fix brief; dispatched to fresh subagent |
| `ask` | Resolved via AskUserQuestion **before** dispatch; result feeds subagent (if fix) or file/defer/skip |
| `file` | Orchestrator batches `gh-issue create` |
| `defer` / `skip` | Orchestrator records in session summary |

### `ask` Resolution Before Dispatch

All `ask` verbs MUST be resolved before dispatching the subagent. The manifest contract says `ask` emits one AskUserQuestion at execution time — the orchestrator is the executor, not the subagent. After the user responds, the result determines whether the finding enters the fix brief (`fix`/letter) or is handled by the orchestrator (`file`/`defer`/`skip`).

### Fix Brief Format

The fix brief is a filtered copy of `<tmpdir>/challenge-findings.md` containing only the `## Finding N:` blocks whose manifest entry has verb `fix`, `A`, `B`, `C`, or a resolved `ask` that mapped to a fix action.

- **Write to**: `<tmpdir>/challenge-fix-brief.md` (first iteration) or `<tmpdir>/challenge-fix-brief-<N>.md` (subsequent iterations, matching findings/manifest suffix — e.g., `challenge-fix-brief-2.md` alongside `challenge-findings-2.md`)
- **Format**: Same `findings.md` format (preserves `## Finding N:` blocks verbatim) — subagent parsing is trivial
- **Pass to subagent**: Via the `**Findings files to read:**` field in the retry-prompt template

The subagent receives ONLY the fix-verb findings — not the full findings file. Findings with `file`, `defer`, or `skip` verbs never reach the subagent.

### Subagent Context

The subagent's existing context is preserved alongside the fix brief: design.md, WP files, `implementer-prompt.md`, `retry-prompt.md`, `tdd.md`. The fix brief replaces the current unfiltered challenge findings handoff. Impl-review suggestions remain separate — they are not structured as challenge findings and do not enter the manifest.

### Re-Challenge Cycle

After the subagent completes, the existing re-test / re-review / re-challenge loop continues unchanged. Each re-challenge produces a new findings file and a new manifest. Manifest files MUST use iteration-suffixed paths matching their findings file (`resolutions-2.md` alongside `challenge-findings-2.md`). The prior manifest is complete.

## 8. Per-Verb Execution Logging

Same format as standalone (defined in `findings-protocol.md`). Before any verbs run, write a sentinel entry to verify the log is writable:

```
{timestamp} execution_started findings={total_count}
```

If the sentinel write fails, warn: "Cannot write to `<tmpdir>/editor-log.md` — resume-from-failure recovery will be unavailable for this run. Proceed?" This surfaces the degraded mode before any destructive edits happen.

After each verb executes, append to `<tmpdir>/editor-log.md`:

```
{timestamp} verb_executed finding={id} verb={verb} result={applied|filed|ask-issued|deferred|skipped|error}
```

### Resume From Failure

On failure mid-execution, the caller reads the log to determine which findings already applied and offers to resume from the first unexecuted finding. The log is the authoritative record — do not rely on in-context memory for execution state.

**Resume Gate template:**

```
AskUserQuestion:
  question: "Execution failed after applying {applied} of {total} findings (last applied: F{last_id}). Resume from F{next_id}?"
  header: "Resume execution"
  multiSelect: false
  options:
    - label: "Resume from F{next_id}"
      description: "Continue execution; already-applied findings are skipped"
    - label: "Review log and abort"
      description: "Inspect <tmpdir>/editor-log.md; do not continue this session"
```

## 9. Post-Execute Hook Protocol

Post-execute hooks are caller-specific extension points that run after all verb execution completes. They are triggered by the combination of Doc target content and the finding's execution outcome as recorded in the execution log (`editor-log.md`) — not directly by the manifest verb field.

### Trigger Condition

A hook fires when **both** conditions are met:
1. The finding's Doc target contains `"Open Questions"`
2. The finding's execution outcome is `deferred` — check the execution log (`editor-log.md`) for the `result=deferred` entry, not the manifest verb field. This correctly handles `ask`-resolved-to-defer cases where the manifest verb is `ask` but the user chose to defer at execution time.

### Hook Actions by Caller

Before appending each finding, check if an identical bullet line already exists in the target section — skip if present (dedup for re-runs).

**mine.specify:**
1. Sweep findings matching the trigger condition — append bullets to the document and section named in the Doc target (e.g., `spec.md SS Open Questions` appends to `spec.md`'s `## Open Questions` section)
2. Re-run the quality validation defined in `skills/mine.specify/SKILL.md` on the updated spec

**mine.design:**
1. Sweep findings matching the trigger condition — append bullets to `design.md`'s `## Open Questions` section (per the Doc target)

**mine.orchestrate:**
No post-execute hooks. Code-fix findings do not target document sections.

### Worked Example — OQ-Append Hook

Given a resolved manifest containing:

```markdown
## F4: No migration rollback strategy
**Severity:** TENSION | **Type:** Structural | **Raised by:** Senior (3/5)
**Doc target:** spec.md SS Open Questions

**Problem:** ...
**The disagreement:** ...
**Deciding factor:** ...

**Verb:** defer
```

After verb execution records F4 as deferred, the post-execute hook:
1. Detects Doc target contains "Open Questions" AND execution result is `deferred` (the manifest verb may have been `defer` or `ask`)
2. Opens `spec.md`, locates `## Open Questions` via the matching algorithm
3. Appends: `- **No migration rollback strategy** (from spec challenge on <date>, target: \`<spec_path>\`): NFR-1 says "sub-100ms p99" but AC-7 implies complex aggregation that cannot meet this — TENSION`

The user sees the Doc target routing in the manifest editor and can override it — for example, setting `verb: skip` means execution will not record a deferred result, which prevents the OQ-append, and changing the Doc target redirects it.

### Hook Execution Logging

After each hook action, append to `<tmpdir>/editor-log.md` using the same format as per-verb logging:

```
{timestamp} hook_executed hook={hook_name} finding={id} target={doc-name SS section-name} result={appended|skipped_duplicate|section_not_found|error}
```

On `section_not_found` or `error`, include the hook result in the session summary so the user sees the failure (e.g., "Post-execute OQ-append: 1 finding appended, 1 failed (F3: section not found in design.md)").

## 10. Compaction Recovery

If context compacts between the Consent Gate and verb execution, the manifest must not be regenerated — doing so loses all user verb edits.

**Early-exit check for callers:** Before generating a new manifest, callers should check for an existing `<tmpdir>/resolutions.md`. If present and non-empty, this is an orphaned manifest — skip manifest generation and proceed per the recovery procedure below. This check should be performed in the caller's SKILL.md flow regardless of whether caller-protocol.md has been re-read after compaction.

### Recovery Procedure

Before generating a new manifest, check for an existing `<tmpdir>/resolutions.md`. For iteration-suffixed orchestrate manifests, also check `resolutions-N.md` — use the highest-numbered file as the authoritative manifest:

1. If the file exists and is non-empty, this is an orphaned manifest from a compacted session
2. **Verify the paired findings file exists.** Check `<tmpdir>/challenge-findings.md` (or `challenge-findings-N.md` matching the manifest's iteration suffix). If the findings file is missing, surface a named error: "Orphaned manifest found at `<path>` but source findings are unavailable — cannot verify finding context." Offer the user a choice:
   ```
   AskUserQuestion:
     question: "Found manifest but findings file is missing. Re-run challenge to regenerate findings, or proceed with manifest only (finding context will be unavailable)?"
     header: "Recovery — missing findings"
     multiSelect: false
     options:
       - label: "Re-run challenge"
         description: "Discard the orphaned manifest and regenerate everything"
       - label: "Proceed with manifest only"
         description: "Execute verbs from the manifest; finding details will be unavailable for TENSION resolution"
   ```
   If the user chooses "Re-run challenge", treat as full compaction — regenerate both findings and manifest. If the findings file for the highest-numbered manifest is missing but a lower-numbered findings file exists, fall back to regenerating (treat as full compaction) rather than using a mismatched pair.
3. **Skip** manifest generation and the Consent Gate entirely
4. Re-read the existing manifest
5. Proceed directly to Commit Gate — skip Detection Logic. The manifest was reviewed in a prior session; hash comparison is not meaningful for orphaned manifests.

This mirrors orchestrate's checkpoint-read detection pattern. Each caller's SKILL.md must reference this section.

## 11. Worked Examples

### Doc-Edit Manifest (mine.specify)

A challenge run on `spec.md` produces 4 findings. The pre-routing pass generates:

```markdown
<!-- pre-hash: a1b2c3... -->
<!-- Resolution Manifest -- edit the **Verb:** line in each section, then save and close. -->
<!-- Valid verbs: fix | file | defer | skip | ask | A | B | C -->

**Base dir:** /home/user/project/design/specs/001-api-performance/

| Verb | Meaning |
|---|---|
| `fix` | Apply the recommended fix (auto-apply findings) or the `recommendation:` option (user-directed) |
| `file` | Create a GitHub issue (batched at end of execution) |
| `defer` | Record in session summary; no action this session |
| `skip` | Same as defer but for "not a real issue" |
| `ask` | Prompt me at execution time with the finding's options |
| `A` / `B` / `C` | Apply the specified option letter |

> **:q! is safe** -- your edits are autosaved to a shadow file every 2 seconds. Save normally or quit -- your changes will be recovered.

## F1: Acceptance criterion is untestable
**Severity:** HIGH | **Type:** Gap | **Raised by:** Senior (1/5)
**Doc target:** spec.md SS Acceptance Criteria

**Problem:** AC-4 says "respond quickly" with no measurable threshold.

**Why it matters:** Cannot verify implementation against this AC.

**Better approach:** Edit AC-4: "respond quickly" -> "Respond within 200ms p95 under 100 RPS load."

**Verb:** fix

## F2: Missing error handling requirement
**Severity:** MEDIUM | **Type:** Gap | **Raised by:** Adversarial Reviewer (2/5)
**Doc target:** spec.md SS Error Handling

**Problem:** No requirement specifies behavior on upstream timeout.

**Why it matters:** Implementers will guess or ignore.

**Options:**
- **A** *(recommended)*: Add requirement: "On upstream timeout (>5s), return cached response with staleness indicator"
- **B**: Add requirement: "On upstream timeout, return 504 with retry-after header"

**Why A:** Cached fallback preserves user experience; 504 causes visible failures.

**Verb:** A

## F3: Conflicting performance targets
**Severity:** TENSION | **Type:** Structural | **Raised by:** Senior (3/5)
**Doc target:** spec.md SS Open Questions

**Problem:** NFR-1 says "sub-100ms p99" but AC-7 implies complex aggregation that cannot meet this.

**The disagreement:** Side A argues the aggregation must be pre-computed. Side B argues the latency target should be relaxed to p95.

**Deciding factor:** Whether the aggregation query is on the critical path or can be deferred.

**Verb:** defer

## F4: Implementation detail in spec
**Severity:** MEDIUM | **Type:** Scope | **Raised by:** Adversarial Reviewer (4/5)
**Doc target:** (none -- flag for implementation)

**Problem:** Section 3.2 specifies "use Redis for caching" -- this is a design decision, not a requirement.

**Why it matters:** Locks implementation to a specific technology.

**Better approach:** Replace "use Redis" with "use a distributed cache" and defer technology choice to design.

**Verb:** skip
```

**Execution trace:**
- F1 (`fix`, Auto-apply): Edit tool applies the AC-4 change to `spec.md` at `## Acceptance Criteria`
- F2 (`A`): Edit tool applies Option A to `spec.md` at `## Error Handling`
- F3 (`defer`): Recorded in session summary; post-execute hook appends to `spec.md` `## Open Questions`
- F4 (`skip`): Recorded in session summary; no edit (Doc target is `(none)`)

### Code-Fix Manifest (mine.orchestrate)

A challenge run on WP03 implementation produces 3 findings. The resolved manifest contains (header omitted for brevity; includes `**Base dir:**` per §3):

```markdown
## F1: Missing retry logic on external API call
**Severity:** HIGH | **Type:** Fragility | **Raised by:** Adversarial Reviewer (1/5)
**Doc target:** (code)

**Problem:** user_service.py:47 calls the auth API with no retry.

**Why it matters:** Transient failures propagate to callers.

**Better approach:** Add exponential backoff with 3 retries in user_service.py:47.

**Verb:** fix

## F2: Race condition in cache invalidation
**Severity:** HIGH | **Type:** Correctness | **Raised by:** Senior (2/5)
**Doc target:** (code)

**Problem:** cache.py:112 deletes then re-fetches without a lock.

**Why it matters:** Concurrent requests see stale data during the gap.

**Options:**
- **A** *(recommended)*: Use atomic compare-and-swap via Redis WATCH/MULTI
- **B**: Add a distributed lock with TTL

**Why A:** Avoids lock contention; leverages Redis's built-in atomic ops.

**Verb:** A

## F3: TENSION — Sync vs async event dispatch
**Severity:** TENSION | **Type:** Structural | **Raised by:** Senior (3/5)
**Doc target:** (none -- TENSION, files as issue)

**Problem:** events.py:30 dispatches synchronously, blocking the request.

**The disagreement:** Side A argues async dispatch improves latency. Side B argues sync dispatch guarantees delivery order.

**Deciding factor:** Whether event ordering is a business requirement.

**Verb:** file
```

**Execution trace:**
1. F1 (`fix`) and F2 (`A`) are collected into the fix brief
2. F3 (`file`) is handled by the orchestrator — batched `gh-issue create`
3. Fix brief written to `<tmpdir>/challenge-fix-brief.md` containing only F1 and F2 blocks
4. Fresh subagent dispatched with fix brief path via `**Findings files to read:**`

## Routing Heuristic Precision

The pre-routing pass computes Doc targets based on finding contract tags and caller-specific heuristics (e.g., mine.specify's spec-vs-design routing). When the heuristic **cannot unambiguously classify a finding**, default the verb to `ask`. This converts routing ambiguity into a user prompt at execution time rather than a silent wrong-document edit.

The manifest editor serves as a secondary safety valve — users can correct wrong Doc targets before execution.

## Pre-Routing Tables

Callers populate default verbs and Doc targets using these tables. See `findings-protocol.md` Default Verb Selection for the evaluation order (TENSION first, then Auto-apply, then recommendation content).

### mine.specify

| Finding property | Default verb | Doc target |
|---|---|---|
| `severity: TENSION` | `defer` | `spec.md SS Open Questions` |
| `design-level: Yes` + routes to spec (functional reqs, goals, user scenarios, ACs, non-goals) | `fix` / letter / `ask` (per Default Verb Selection) | `spec.md SS <section>` |
| `design-level: Yes` + routes to design (architecture, data model, API) | `defer` | `design.md SS Open Questions` |
| `design-level: No` | `skip` | `(none -- flag for implementation)` |

### mine.design

| Finding property | Default verb | Doc target |
|---|---|---|
| `severity: TENSION` | `defer` | `design.md SS Open Questions` |
| `design-level: Yes` | `fix` / letter / `ask` (per Default Verb Selection) | `design.md SS <section>` |
| `design-level: No` | `skip` | `(none -- flag for implementation)` |

### mine.orchestrate

Note: `design-level` is not used in code-fix routing — all code findings route identically regardless of design-level. If a finding is `design-level: Yes` (structural architecture issue), the manifest editor is the appropriate place to override its verb to `ask` or `defer`.

| Finding property | Default verb | Doc target |
|---|---|---|
| `severity: TENSION` | `file` | `(none -- TENSION, files as issue)` |
| `resolution: Auto-apply` | `fix` | `(code)` |
| `resolution: User-directed` + recommendation present | option letter | `(code)` |
| `resolution: User-directed` + no recommendation | `ask` | `(code)` |
