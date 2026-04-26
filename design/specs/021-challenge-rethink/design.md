---
spec: "021"
title: "Challenge Skill Rethink"
status: approved
created: 2026-04-26
---

# Challenge Skill Rethink

**Status:** archived

## Problem

The adversarial review skill produces too many findings per run (15.6 average, up to 31), with 58% clustering at medium severity — a distribution that has effectively collapsed into a single tier. The resolution manifest (a vim-based editor where users set verbs per finding) is abandoned 44% of the time on standalone runs. Every run dispatches the maximum critic configuration regardless of the target's needs, resulting in 6 Sonnet subagent invocations per run. Users experience alert fatigue: the volume of output makes it hard to identify what actually matters, and the per-finding triage UX creates friction at the point of maximum cognitive load.

Session archaeology over 14 days (63 invocations, 826 findings) confirms: when users do complete the resolution flow, they act on 92% of findings — the quality is there, but the volume and interaction model are the problem.

## Goals

- Reduce the number of findings presented to the user to 5–7 per run, with overflow handled automatically
- Eliminate the manifest editing flow entirely — users should never set verbs per finding
- Reduce cost per run by 50–70% by dispatching only the critic perspectives the target actually needs
- Maintain the 92% action rate on findings that are presented (don't sacrifice quality for volume reduction)
- Keep the findings file as a structured artifact that callers can consume programmatically

## Non-Goals

- Feedback-driven learning (suppressing finding categories based on historical ignore rates) — future work
- Replacing the multi-critic architecture with a single agentic reviewer — future work
- Changing the severity taxonomy (CRITICAL/HIGH/MEDIUM/TENSION) — keep as-is
- Changing the finding type taxonomy (Structural/Approach/Fragility/Gap) — keep as-is

## User Scenarios

### Actor: Developer invoking standalone challenge

1. Developer asks Claude to challenge a design doc or code change
2. System reads the target and performs a lightweight triage to determine which critic perspectives are relevant
3. System dispatches only the relevant critics (1–2 instead of always 3–5)
4. System synthesizes critic reports, classifying each finding as auto-apply or user-directed
5. System auto-applies all confident findings without user interaction
6. System presents a summary: "Applied N findings automatically. M findings need your input."
7. For each user-directed finding, system presents an inline question with options (including the recommended choice)
8. Developer answers each question; system applies the chosen fix
9. System reports final summary: what was applied, what was skipped

### Actor: mine.define calling challenge on a design doc

1. mine.define invokes challenge with a design doc path and structured output path
2. Challenge runs the same triage → critics → synthesis → auto-apply flow
3. Auto-applied findings are applied directly to the design doc sections
4. User-directed findings are presented inline via the same one-at-a-time flow
5. mine.define receives the updated design doc and a summary of what changed
6. mine.define continues its quality validation on the updated doc

### Actor: mine.gap-close offering "run full challenge"

1. User selects "Run full challenge" from gap-close's sign-off gate
2. gap-close invokes challenge; challenge runs the streamlined flow
3. Results feed back to gap-close's loop

## Functional Requirements

### Hierarchical triage

- **FR1**: Before dispatching any Sonnet critics, the system must run a lightweight triage pass that reads the target and determines which 1–3 critic perspectives are relevant
- **FR2**: The triage pass must use a cheaper model tier (Haiku) to minimize cost
- **FR3**: The triage pass must select from the existing persona pool (3 generic + 8 specialist) — it does not invent new perspectives
- **FR4**: The triage pass must always select at least 1 critic and at most 3 critics
- **FR5**: The triage output must include a one-sentence rationale per selected critic explaining why that perspective is relevant to this target
- **FR6**: The `--focus` flag must still work — if provided, the focused specialist is always included in the roster regardless of triage recommendation
- **FR7**: Re-challenge runs must still use the reduced roster (max 2 critics), with triage selecting which 2

### Auto-fix by default

- **FR8**: The synthesis phase must classify every finding as either auto-apply or user-directed using the existing resolution field
- **FR9**: Auto-apply findings must be applied without user interaction — no consent gate, no manifest, no verb editing
- **FR10**: The system must report auto-applied findings as a summary after application: count, brief one-line description per finding, and what changed
- **FR11**: User-directed findings must be presented one at a time via an interactive prompt with the available options and a recommended choice
- **FR12**: For TENSION findings, the prompt must present both sides of the disagreement and a deciding factor, not a recommendation
- **FR13**: The user must be able to skip or file-as-issue any user-directed finding

### Finding cap

- **FR14**: CRITICAL and HIGH findings are always presented to the user regardless of cap
- **FR15**: MEDIUM findings are subject to a budget: after CRITICAL/HIGH are allocated, remaining slots (up to the cap) are filled by MEDIUM findings in priority order
- **FR16**: MEDIUM findings that exceed the cap are auto-applied if they have auto-apply resolution, or mentioned as a count if user-directed ("3 additional MEDIUM findings deferred — run with `--verbose` to see them")
- **FR17**: The default cap is 7 findings. The `--cap` flag allows overriding (e.g., `--cap=3` for strict, `--cap=15` for comprehensive)
- **FR18**: The `--verbose` flag shows all findings regardless of cap (but still auto-applies confident ones)

### Caller contract

- **FR19**: The findings file format must remain a structured markdown artifact with numbered findings, severity, type, design-level, and resolution fields
- **FR20**: The resolution manifest (resolutions.md), editor session, and verb-based flow must be removed entirely — from SKILL.md, findings-protocol.md, and caller-protocol.md
- **FR21**: Callers invoking challenge with `--findings-out` must receive the findings file with auto-applied findings marked as `status: applied` and user-directed findings marked as `status: pending`
- **FR22**: mine.define must be updated to consume the new findings contract: read findings, auto-apply design-level findings to design.md sections, present remaining user-directed findings inline
- **FR23**: mine.define's compaction recovery must be updated to work without the resolution manifest — use the findings file's status fields instead
- **FR24**: mine.gap-close's "Run full challenge" option must continue to work with the streamlined flow

### Removed components

- **FR25**: The pre-flight surface issue scan (Phase 1 Stage 1) must be removed — it duplicates what critics do and adds latency before the triage pass
- **FR26**: The pre-flight architecture smell test (Phase 1 Stage 2) must be removed — same rationale
- **FR27**: The Consent Gate ("Found N findings — ready to review?") must be removed — auto-apply makes it unnecessary
- **FR28**: findings-protocol.md must be simplified to document only the findings file format and the inline resolution flow, removing all manifest/editor/verb documentation
- **FR29**: caller-protocol.md must be simplified to document only the caller integration contract, removing manifest-specific sections

## Edge Cases

- Triage selects zero relevant critics (shouldn't happen per FR4, but if it does: fall back to the Senior Engineer generic as the minimum)
- All findings are auto-apply: present only the summary, no interactive prompts needed
- All findings are user-directed: present up to the cap, defer the rest with a count
- Cap is set to 0 via `--cap=0`: auto-apply everything, present nothing interactively — pure automation mode
- Target is empty or trivial: triage should be able to report "no meaningful review needed" and produce zero findings
- Re-challenge with `--focus`: focus specialist always included, triage fills the second slot
- Caller passes `--findings-out` but no user is present (structured mode): auto-apply findings, write status to findings file, skip all interactive prompts
- A CRITICAL finding is classified as auto-apply: this should not happen — CRITICAL findings must always be user-directed regardless of confidence

## Acceptance Criteria

- **AC1**: Average findings presented to user per run drops from 15.6 to ≤7
- **AC2**: Average Sonnet subagent invocations per run drops from 6 to ≤3 (1 triage Haiku + 1–2 Sonnet critics + 1 Sonnet synthesis)
- **AC3**: The manifest editor, verb editing, consent gate, and resolution manifest file are completely absent from the codebase
- **AC4**: Standalone challenge runs present user-directed findings one at a time via interactive prompts
- **AC5**: Auto-applied findings are reported as a summary with count and brief descriptions
- **AC6**: mine.define can invoke challenge and receive structured findings with applied/pending status
- **AC7**: mine.gap-close's "Run full challenge" option works end-to-end
- **AC8**: CRITICAL findings are never auto-applied
- **AC9**: The `--cap`, `--verbose`, and `--focus` flags work as specified
- **AC10**: Total SKILL.md line count is ≤400 (down from 744)

## Dependencies and Assumptions

- The existing persona files (3 generic + 8 specialist) remain unchanged — triage selects from them, doesn't modify them
- Haiku model is available and capable of reading a target artifact and selecting relevant critic perspectives
- The findings file format (markdown with numbered headings and metadata fields) remains the integration contract — callers parse it
- mine.define and mine.gap-close are the only callers that parse challenge output programmatically

## Architecture

### Phase restructure

Replace the current 4-phase flow (Gather Context → Launch Critics → Synthesize → Present) with:

1. **Phase 1: Triage** — Read target, classify type, dispatch Haiku subagent to select 1–3 critics from the persona pool. Output: critic roster with rationales. If `--focus` provided, include that specialist. Remove the pre-flight surface scan and architecture smell test entirely.

2. **Phase 2: Critique** — Dispatch selected critics in parallel (Sonnet, `subagent_type: general-purpose`). Same as today but with fewer critics. Each critic writes a report to the tmpdir.

3. **Phase 3: Synthesize + Classify** — Dispatch synthesis subagent (Sonnet). Same merge/dedup as today, but with additional responsibilities: (a) classify each finding as auto-apply or user-directed, (b) rank findings by priority, (c) enforce the cap — mark findings beyond the cap as `overflow: true`, (d) mark CRITICAL findings as always user-directed regardless of other signals.

4. **Phase 4: Execute** — Back in the orchestrator context. Read the findings file. Auto-apply all auto-apply findings (edit the target files directly). Present user-directed findings one at a time via `AskUserQuestion`. Report summary.

### Findings file format changes

Add two new fields per finding:
- `status: applied | pending | overflow | skipped` — tracks execution state
- `overflow: true | false` — whether this finding exceeded the cap

Remove:
- All references to the resolution manifest, verb vocabulary, consent gate, editor session, hash-based change detection

### Triage subagent prompt structure

The Haiku triage subagent receives:
- The full target content
- The target type classification
- The list of available personas (name + one-line description from each persona file's frontmatter)
- The `--focus` constraint if provided

It returns a JSON-structured response:
- `critics`: array of 1–3 persona filenames
- `rationale`: object mapping each filename to a one-sentence reason
- `target_summary`: one-sentence description of what the target does (passed to critics as context)

### Caller contract changes

**mine.define**: Replace the manifest-based integration with:
1. Invoke challenge with `--findings-out=<path> --target-type=design-doc <doc-path>`
2. Read the findings file after challenge completes
3. For `status: applied` findings with `design-level: Yes`: verify the edit was applied to the correct design.md section
4. For `status: pending` findings: these were already presented to the user during challenge — check their final status
5. Remove: pre-routing tables, default verb selection, manifest generation, editor session, compaction recovery via manifest hash

**mine.gap-close**: No structural changes needed — it just invokes challenge and loops back. The invocation interface (`/mine.challenge <path>`) is unchanged.

### Files to modify

| File | Action | Notes |
|------|--------|-------|
| `skills/mine.challenge/SKILL.md` | Rewrite | Target ≤400 lines. New 4-phase flow. |
| `skills/mine.challenge/findings-protocol.md` | Rewrite | Document findings file format + inline resolution flow only. Remove manifest/editor/verb docs. Target ≤150 lines. |
| `skills/mine.challenge/caller-protocol.md` | Rewrite | Simplified caller contract. Remove manifest sections. Target ≤100 lines. |
| `skills/mine.define/SKILL.md` | Edit | Update challenge integration sections. Remove manifest consumption logic. |
| `skills/mine.gap-close/SKILL.md` | Verify | Should work as-is since invocation interface unchanged. Minor edits if needed. |
| `rules/common/performance.md` | Edit | Update mine.challenge model declaration (add Haiku for triage). |

### Files to delete

None — persona files stay, directory structure stays. The resolution manifest is a runtime artifact, not a checked-in file.

## Alternatives Considered

### Single agentic reviewer (BugBot pattern)

Replace all critics with one deep agentic reviewer. Highest resolution rate in the industry (70–80%). Rejected for now because: (a) design documents benefit from multi-perspective review more than code does, (b) would require completely new prompt engineering rather than adapting existing personas, (c) can be evaluated separately once the cost/volume improvements from triage are measured.

### Feedback-driven learning (CodeRabbit pattern)

Track which findings get ignored and suppress similar ones. Powerful ratchet but requires persistence infrastructure (finding categories, resolution rates, per-repo learnings). Rejected for this iteration — the cap + auto-fix changes should reduce volume enough. Can layer in later using the memory system.

### Verification-gated findings

Add a deterministic or second-agent verification step after synthesis. Would reduce false positives but adds latency and cost (another subagent invocation). Partially addressed by the triage step (fewer critics = fewer low-confidence findings). Can be added later if false positive rate remains high.

## Test Strategy

This is a prompt-based skill (no executable code), so testing is behavioral:
- Run the reworked challenge against 3–4 representative targets: a design doc, a code file, a skill file, and a brief
- Verify finding count is within cap for each run
- Verify triage selects different critic rosters for different target types
- Verify auto-apply findings are applied without user interaction
- Verify user-directed findings use inline AskUserQuestion
- Verify mine.define integration works end-to-end (invoke challenge on a design doc, receive updated doc)
- Compare cost (subagent count) before/after: expect ≤3 Sonnet invocations vs previous 6

## Documentation Updates

- `rules/common/performance.md`: Add Haiku declaration for challenge triage subagent
- `README.md`: No changes needed (mine.challenge entry stays, behavior changes are internal)
- `rules/common/capabilities-core.md`: No changes needed (trigger phrases unchanged)

## Impact

- **skills/mine.challenge/**: SKILL.md rewritten, findings-protocol.md rewritten, caller-protocol.md rewritten
- **skills/mine.define/**: Challenge integration sections updated
- **skills/mine.gap-close/**: Minimal verification pass
- **rules/common/performance.md**: New model declaration
- **Persona files**: Unchanged
- **Downstream callers**: mine.define and mine.gap-close — both updated in scope
- **Blast radius**: Limited to the challenge skill and its two direct callers. No changes to the findings severity/type taxonomy, persona pool, or invocation syntax (`/mine.challenge <target>`)

## Open Questions

None.
