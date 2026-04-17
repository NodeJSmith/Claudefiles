---
proposal: "Extend the per-finding resolution manifest flow (skills/mine.challenge/findings-protocol.md) to cover mine.specify and mine.design callers, eliminating the bundled 'Apply all / Cherry-pick / Skip revisions' AskUserQuestion prompt and the SYNC block shared between the two skills."
date: 2026-04-16
status: Draft
flexibility: Decided
motivation: "The manifest flow from archived spec 015 is the structural replacement for bundled AskUserQuestion prompts. It works for standalone /mine.challenge, but callers mine.specify and mine.design bypass it with their own 'Apply all / Cherry-pick / Skip revisions' gate, which literally instantiates Anti-Patterns #1 (bundling), #4 (meta-gate), and #8 (bail-out) from findings-protocol.md. This is an unfinished migration."
constraints: "Must not break standalone /mine.challenge contract. Manifest verbs (fix/file/A/B/C/defer/skip/ask) are canonical; new verbs need strong justification. bin/edit-manifest pre-hash/shadow-file mechanics must keep working. mine.tool-gaps and mine.visual-qa are migration-exempt — out of scope."
non-goals: "Migrating mine.tool-gaps or mine.visual-qa. Changing the standalone challenge flow's contract. Redesigning the verb vocabulary."
depth: normal
---

# Research Brief: Extend Manifest Flow to mine.specify / mine.design Callers

**Initiated by**: Finishing the 015 manifest migration. Callers currently reproduce the bundling anti-patterns that 015 eliminated for standalone challenge.

## Context

### What prompted this

Archived spec 015 (`design/specs/015-per-finding-resolution-manifest/design.md`) landed in commit `4d5bc25` and introduced the per-finding resolution manifest flow for standalone `/mine.challenge`. The flow:

1. Writes `<tmpdir>/resolutions.md` with one markdown block per finding and a pre-populated `**Verb:**` line
2. Presents a single Consent Gate
3. Invokes `bin/edit-manifest` (tmux new-window + nvim + shadow-file autosave)
4. Detects changes via `pre_hash`/`post_hash`/`shadow_hash`
5. Validates verbs
6. Presents a single Commit Gate
7. Executes verbs in deterministic order: Phase 1 immediate (fix/A/B/ask/defer/skip), Phase 2 batched `file`, Phase 3 summary

Spec 015 explicitly **excluded** structured callers (mine.specify, mine.design, mine.orchestrate) as a non-goal, describing them as "unaffected by this design's changes, not by the underlying problem." The underlying problem was left as future work.

Today, when the user picks "Challenge this spec first" or "Challenge this design", the caller:

1. Invokes `/mine.challenge --findings-out=<path> --target-type=<spec|design-doc>`
2. Reads findings.md in-context
3. Generates a revision plan in prose and presents it
4. Emits this AskUserQuestion:

```
question: "How would you like to handle these revisions?"
options:
  - "Apply all" — Apply auto-apply changes directly; prompt me for each user-directed decision
  - "Let me cherry-pick" — I'll say which revisions to apply
  - "Skip revisions" — I've seen the findings — loop back to sign-off without changing the doc
```

This is a textbook **Anti-Pattern #4** (Meta-gate: relabeled Proceed Gate with new semantics). "Apply all" is **Anti-Pattern #1** (bundling N findings into one approval). "Skip revisions" is **Anti-Pattern #8** (bail-out option that violates 'all findings must be resolved'). The same bundled gate lives in both `mine.specify` (SKILL.md:378-389) and `mine.design` (SKILL.md:314-326) and is coupled by a `<!-- SYNC: -->` marker.

### Current state

**Three paths findings flow through today**:

```
                                    ┌──────────────────────────────────────┐
                                    │  mine.challenge Phase 1-3 (shared)   │
                                    │  - Critics, synthesis                │
                                    │  - Write findings.md                 │
                                    └──────────────────┬───────────────────┘
                                                       │
                              mode: standalone         │         mode: structured
                                    │                  │                  │
                                    ▼                  ▼                  ▼
                   ┌────────────────────────┐  ┌─────────────┐  ┌─────────────────────┐
                   │ findings-protocol.md   │  │ passthrough │  │ CALLER consumes     │
                   │                        │  │ (research/  │  │ findings.md in-ctx  │
                   │ 1. Consent Gate        │  │ brainstorm) │  │                     │
                   │ 2. Generate manifest   │  │             │  │ mine.specify        │
                   │ 3. bin/edit-manifest   │  │ Summary     │  │ mine.design         │
                   │ 4. Detection           │  │ only — no   │  │ mine.orchestrate    │
                   │ 5. Validate            │  │ gate        │  │                     │
                   │ 6. Commit Gate         │  │             │  │ CALLER builds its   │
                   │ 7. Execute (fix/file/  │  │             │  │ own revision plan   │
                   │    A/B/C/ask/defer)    │  │             │  │                     │
                   └────────────────────────┘  └─────────────┘  │ CALLER emits bundled│
                                                                │ "Apply all / Cherry-│
                                                                │  pick / Skip" gate  │
                                                                │                     │
                                                                │ CALLER applies edits│
                                                                │ to spec.md/design.md│
                                                                └─────────────────────┘
                                                                (ANTI-PATTERNS #1/#4/#8)
```

**Caller-specific logic** that exists on top of the bundled gate:

`mine.specify` (SKILL.md:345-412):
- Scans each finding's `design-level` tag
- Routes `design-level: Yes` findings through a spec-vs-design heuristic (Functional Requirements / Goals / User Scenarios / Acceptance Criteria → spec; architecture / data model / API → design)
- Routes `design-level: No` findings to "flag for implementation, no spec change"
- Routes `TENSION` findings to spec.md's `## Open Questions` section
- Routes design-phase-flagged findings to `<feature_dir>/design.md` stub under `## Open Questions`, deduplicating by line match
- Applies text edits to spec.md via Edit tool calls
- Re-runs 12-item validation
- Loops back to sign-off gate

`mine.design` (SKILL.md:289-334):
- Scans findings the same way
- Checks `design.md` existing `## Open Questions` for prior `(from spec challenge on` markers to avoid duplicates
- Routes `design-level: Yes` to design doc sections (architecture/alternatives/etc.) or to Open Questions for TENSION
- Routes `design-level: No` to "flag for implementation" (no doc change)
- Applies text edits to design.md
- Loops back to sign-off gate

**Key constraint discovered in git history**: commit `a5026f0` moved `findings-protocol.md` OUT of `rules/common/` (where it was auto-loaded into every subagent context for ~144KB per challenge run) INTO `skills/mine.challenge/`. Any solution that puts the shared protocol back under `rules/common/` reverses that perf win. The protocol is now loaded on-demand, not automatically.

### Key constraints

- **Compaction safety**: All gates and state must survive context compaction. The manifest flow already does this via pre-hash comments embedded in the manifest file and state recovery from `<tmpdir>/manifest.md`. Extending the flow must preserve this property.
- **Verb vocabulary is canonical**: New verbs require strong justification. The doc-edit semantics must fit within `fix`/`file`/`A`/`B`/`C`/`defer`/`skip`/`ask` or extend with minimal discipline.
- **bin/edit-manifest contract**: Takes one manifest path. Returns exit 0 (done), 1 (error), 2 (no interactive editor — tertiary fallback). Writes shadow file. Writes `editor-log.md`. This contract cannot break.
- **mine.tool-gaps / mine.visual-qa exemption**: Both remain on the legacy collect-then-fix path for now.
- **Standalone-path contract preservation**: The Consent Gate → editor → detection → Commit Gate → execute sequence is the contract.
- **Perf**: Don't regress the context size improvement from `a5026f0` by auto-loading the protocol.

## Feasibility Analysis

### What would need to change

| Area | Files affected | Effort | Risk |
|------|---------------|--------|------|
| Shared doc-edit protocol file | 1 new file (e.g., `skills/mine.challenge/caller-protocol.md`) | Medium | Low — modeled after existing `findings-protocol.md` |
| `findings-protocol.md` extension — verb semantics for doc edits | 1 file (~40 lines added) | Small | Low if semantics are clean; Medium if doc-edit `fix` semantics get subtle |
| mine.specify revision handler | `skills/mine.specify/SKILL.md` lines 339-412 — remove bundled gate, replace with manifest reference | Small | Medium — caller-specific routing (TENSION → OQ, design-level:No pass-through, spec-vs-design heuristic, deferred-findings persistence) must be preserved |
| mine.design revision handler | `skills/mine.design/SKILL.md` lines 283-332 — remove bundled gate, replace with manifest reference | Small | Medium — similar caller-specific routing |
| SYNC marker reconciliation | Remove or narrow SYNC blocks on both sides | Small | Low |
| `bin/edit-manifest` | **No change** — same contract, same mechanics | None | None |
| `findings-protocol.md` Manifest Validation Spec | May need one bullet about ID-stability across caller-specific reroutes | Small | Low |
| `mine.challenge` SKILL.md | No functional change. Possibly add a mode doc for caller-execution handoff | Trivial | None |

**Typical caller migration diff per caller**: delete ~50 lines of bundled-gate logic, replace with ~10 lines that delegate the manifest flow and specify caller-specific "verb-to-edit adapter". Net lines decrease.

### What already supports this

1. **The manifest flow is mechanism-agnostic by design** — `findings-protocol.md` was written to delegate *what to do with each verb* to the invoking skill. The Execution section describes verb semantics abstractly ("apply `better-approach`", "apply the recommended option") — it never hardcodes "modify source code". For doc callers, "apply the recommended option" can mean "apply this text edit to spec.md" with zero protocol changes.

2. **`bin/edit-manifest` doesn't know or care what the verbs mean**. It only opens the file, watches for changes, and signals back. Reuse is free.

3. **Caller tmpdir already exists**. Both `mine.specify` and `mine.design` already run `get-skill-tmpdir mine-<slug>-challenge` to get a known path for `findings.md`. The resolutions manifest can live in the same dir.

4. **Pre-hash / shadow-file / detection logic is agnostic to finding type**. The detection decision table in `findings-protocol.md` (exit_code/pre_hash/post_hash/shadow) doesn't care whether the verb applies to code or prose. Whatever the verb means, the editor mechanics are unchanged.

5. **Caller-specific revision plans are already built from findings.md in-context** — the caller reads findings from disk and currently *presents* the revision plan in prose. Swapping the prose plan for a manifest file is a structural change with no new information requirements. The caller already has all the data it needs.

6. **Other skills use subfiles alongside `SKILL.md`** as a shared-content pattern. `skills/mine.orchestrate/` contains `retry-prompt.md`, `implementer-prompt.md`, `spec-reviewer-prompt.md`, etc. alongside its `SKILL.md`. `skills/mine.challenge/` already contains `findings-protocol.md`. Placing caller-facing protocol files next to the challenge skill matches this convention and does not resurrect the auto-load issue (commit `a5026f0`).

### What works against this

1. **The verbs were designed for code**. `fix` on Auto-apply means "apply `better-approach`"; on User-directed means "apply recommended option"; on TENSION means "apply after disambiguation." For doc findings, "apply" means "edit spec.md/design.md text at an identified section." This has to be made explicit without adding new verbs.

2. **Caller-specific routing is pre-verb**. `mine.specify` routes findings to different destinations (spec.md sections, spec.md Open Questions, design.md stub Open Questions, "flag for implementation, no change") **before** the resolution plan is even presented. The manifest flow assumes default verbs are computed per-finding and then the user edits in the editor. Current caller routing doesn't fit this shape 1:1.

3. **Design-level/finding classification interacts with verb semantics**. A `design-level: No` finding in `mine.specify` produces no edit ("flag for implementation phase"). That classification currently produces no manifest row in the prose revision plan — it's listed separately. The manifest must handle this cleanly or exclude these findings from the manifest with a clear policy.

4. **Deferred findings persistence (mine.specify → design.md stub)**. After the revision plan is applied, `mine.specify` persists findings routed to "Defer to design phase" by writing them into the design.md `## Open Questions` section. This is **post-execute** caller-specific behavior. It must survive the migration.

5. **TENSION findings currently go to spec.md/design.md Open Questions, not a per-finding verb**. The default TENSION verb in `findings-protocol.md` is `defer`, which for standalone challenge means "record in session summary, take no action." For doc callers, the current behavior is a real edit — append to the Open Questions section of the doc. That's NOT the same as `defer`. Either the verb semantics need a mapping layer, or a caller-specific doc-edit variant (e.g., `defer` = "append to Open Questions" when verbs execute under a doc-edit caller).

6. **The SYNC marker is load-bearing today**. Both specify and design share the bundled gate. If one is migrated without the other, the SYNC invariant is harder to maintain (two different protocols, one of them the legacy bundled one).

## Options Evaluated

Per the Flexibility field (`Decided`), this section presents a single deep-dive on the chosen approach. The section ends with a Concerns callout flagging an important architectural tension that should feed the design phase.

### Option A: Caller-owned execution + shared protocol file

#### Summary

- Create a new shared protocol file at `skills/mine.challenge/caller-protocol.md` (peer to `findings-protocol.md`). This file describes the doc-edit variant of the manifest flow, loaded on-demand by callers (not auto-loaded, preserving commit `a5026f0`'s perf win).
- Callers `mine.specify` and `mine.design` each invoke `/mine.challenge --findings-out=<path>` as today. Challenge produces `findings.md` and exits — unchanged contract.
- Caller reads `findings.md`, applies **caller-specific pre-routing pass** to compute each finding's destination (spec.md/design.md section OR Open Questions OR "no edit"), then writes `<tmpdir>/resolutions.md` using the manifest format from `findings-protocol.md` with caller-specific default verbs encoded.
- Caller invokes `bin/edit-manifest <tmpdir>/resolutions.md` — same mechanics as standalone challenge.
- Caller runs detection/validation/commit-gate per `findings-protocol.md`.
- Caller executes verbs itself (cannot reuse challenge's execution, because challenge doesn't know how to edit spec.md/design.md).
- Bundled "Apply all / Cherry-pick / Skip revisions" gate is deleted. The SYNC marker becomes narrower — only the caller-specific routing heuristics differ, and the shared protocol is via `caller-protocol.md` plus `findings-protocol.md`.

#### How it works in detail

**Ownership boundary**: mine.challenge owns the editor-launching UX and the standalone verb execution. Callers own their document-editing logic. Both share the protocol (format, gates, validation, verb vocabulary).

**Default verb pre-routing** happens BEFORE manifest generation. This is where caller-specific classification lives. For each finding, the caller computes:

| Finding property (from findings.md) | Default verb (in manifest) | Caller handles during execution |
|---|---|---|
| `severity: TENSION` | `defer` (caller re-maps internally to "append to Open Questions") | Caller's verb executor treats `defer` as "append bullet to doc's Open Questions section" when the finding is relevant to the doc |
| `design-level: Yes` + routes to this doc (per heuristic) | `fix` (Auto-apply) or `A`/`B`/`C` (User-directed with option letter) or `ask` (User-directed no clear letter) | Caller's verb executor applies text edit to identified doc section |
| `design-level: Yes` + routes to OTHER doc (specify → design OQ) | `defer` (repurposed: "persist to other doc's Open Questions") | Caller's post-execute pass writes the deferred finding bullet to design.md's OQ section (preserves `## Persist deferred findings` today) |
| `design-level: No` | `skip` (with explicit rationale written into manifest section: "Implementation-phase concern — no spec change") | Caller's verb executor records "flagged for implementation" in session summary |
| `file` (user-chosen) | `file` | Caller's verb executor invokes `gh-issue create` (batched, Phase 2 pattern) |

Key subtlety: for `mine.specify`, the classification "routes to spec" vs "routes to design" vs "no edit" is deterministic from the finding's contract tags (design-level + type) plus a heuristic table. This is already computed today in the prose plan generation. Moving it to "compute before writing the manifest" is structurally identical — the classification output just feeds different rendering.

**Manifest rendering** uses the three existing templates from `findings-protocol.md`:
- **Auto-apply template** for Auto-apply findings (Better approach = "Apply this change to <section> in <doc>: <concrete edit>")
- **User-directed template** for User-directed findings (Options = same as findings.md with the concrete edits per option)
- **TENSION template** for TENSION findings (defer = append to Open Questions by default)

Each manifest section has a caller-specific header line **Doc target**: (spec.md | design.md | design.md Open Questions stub | no doc — flag for impl) so the user sees where the edit would land before changing verbs. Example:

```markdown
## F3: Acceptance criterion is untestable
**Severity:** HIGH | **Type:** Gap | **Raised by:** Senior (1/5)
**Doc target:** spec.md § Acceptance Criteria
**Problem:** AC-4 says "respond quickly" with no measurable threshold.
**Why it matters:** Cannot verify implementation against this AC.
**Better approach:** Edit `spec.md` § Acceptance Criteria AC-4 → "Respond within 200ms p95 under 100 RPS load."
**Verb:** fix
```

**Consent Gate, Commit Gate, detection, and validation are reused verbatim** from `findings-protocol.md`. The caller calls them with its own findings count and target doc name inline.

**Verb execution is caller-owned**. The caller implements a small verb-to-edit table (specific to its doc type). This table lives in `caller-protocol.md` or inline in each caller SKILL.md — see SYNC consolidation below.

**Post-execute caller hook** for deferred findings persistence. After the main verb-execute pass, `mine.specify` runs its existing "persist deferred findings to design.md stub" logic using the set of findings whose verb was `defer` and whose Doc target was "design.md Open Questions stub". The hook is a documented extension point in `caller-protocol.md`.

**Loop back to sign-off gate** as today.

#### Pros (grounded in this codebase)

1. **Kills the SYNC block**. Both callers reduce to ~10 lines each: pre-route, write manifest, invoke edit-manifest, execute. The shared protocol lives in one file.
2. **Preserves the perf win from commit a5026f0**. `caller-protocol.md` is loaded only when a caller needs it (on-demand, via Read or explicit reference) — not auto-loaded.
3. **Compatible with 015's architecture**. Reuses `bin/edit-manifest`, the manifest format, the detection decision table, and the validation spec without reinterpretation.
4. **Matches the mine.orchestrate subfile pattern**. `skills/mine.challenge/caller-protocol.md` sits next to `findings-protocol.md` the way `skills/mine.orchestrate/retry-prompt.md` sits next to its `SKILL.md`.
5. **Eliminates all three anti-patterns for these callers**. No bundled gate (#1), no meta-gate (#4), no bail-out (#8). "Skip revisions" is no longer a top-level option — it's encoded per-finding as a `skip` verb with an explicit rationale field.
6. **TENSION handling becomes explicit, not implicit**. Currently the caller silently routes TENSION to Open Questions. In the manifest, the user sees the `defer` verb on each TENSION finding with the Doc target line showing "spec.md § Open Questions" — making the routing visible.
7. **Preserves caller-specific post-execute hooks**. Deferred findings persistence, sign-off loop, validation re-run — all remain exactly where they are today, but triggered after verb execution instead of after the bundled gate.
8. **Adds a real audit trail to caller flows**. The manifest + `editor-log.md` artifact exists after each caller invocation, not just standalone. Debug loops and compaction recovery both improve.
9. **Backward-compat for in-flight caller sessions**. None — the bundled flow is synchronous within a single caller run, there's no durable artifact that persists between runs under the old flow. Migration is atomic at the SKILL.md level.

#### Cons (grounded in this codebase)

1. **Verb vocabulary gets a doc-edit overlay**. `fix` means slightly different things across contexts (code/doc). This must be spelled out explicitly in `caller-protocol.md` to avoid confusion. Not a new verb, but a disciplined reuse.
2. **`defer` carries two meanings for doc callers**: "append to this doc's Open Questions" and "append to the other doc's Open Questions" (specify-to-design-stub case). These have to be disambiguated by the **Doc target:** field, which is a manifest-level affordance not a verb-level one.
3. **Caller writes a small custom verb executor**. Each caller has ~40 lines of "read verb → apply edit to doc" logic. This is not shared across callers. The shared piece is the protocol, gates, format, editor mechanics; the unique piece is "edit this spec.md section vs that design.md section." Acceptable — the unique logic is what the SYNC block was trying to keep in sync, and now it's localized.
4. **Manifest gets more fields for doc callers**. Doc target line is new. If `findings-protocol.md`'s template is treated as canonical, adding a field per-template is a modification — though the field is additive and optional (not required for standalone). Need a short extension point in the protocol spec.
5. **Protocol-version bump**. `findings-protocol.md` currently declares `manifest-protocol-version: 1`. Adding the Doc target field and the doc-edit overlay probably warrants `v2` as a changelog marker. Not a runtime contract (per the protocol file itself), but the version bump is visible to readers.
6. **Test validation for this work is session-level only** (no unit tests for skills/rules). Same as 015. The design doc should specify a mini dogfood protocol: run mine.specify on a real draft spec, produce challenge findings, observe manifest + verb execution path, verify no bundled prompts.

#### Effort estimate

**Small-to-Medium.** Breakdown:

- New file `caller-protocol.md`: ~150 lines. Most text is copy-edits from `findings-protocol.md` plus the doc-edit overlay table and the extension points. **Medium**.
- `mine.specify` rewrite: replace ~70 lines of bundled flow with ~15 lines of delegation + caller verb executor (~30 lines). **Small**.
- `mine.design` rewrite: replace ~50 lines with ~15 + ~25. **Small**.
- `findings-protocol.md` minor changes: add optional Doc target field note and a "Skill-Specific Overrides" mention of `caller-protocol.md` so it's discoverable. ~10 lines. **Trivial**.
- Dogfood validation (run on real artifact): one session. **Small**.

Total: Design and implement in one focused session if no surprises. Two sessions if TENSION-handling subtlety or the "other doc" deferred case gets complicated.

#### Dependencies

- Existing: `bin/edit-manifest`, `get-skill-tmpdir`, the challenge findings contract, the manifest format.
- No new external dependencies.
- No new configuration.

## Key Architectural Decisions (Per the 4 Questions)

### Question 1: Ownership model — new challenge mode or shared protocol file?

**Alternatives**:

- **A1. Shared protocol file, caller-owned execution** (recommended). Caller invokes challenge with `--findings-out=<path>` as today. Caller generates manifest, invokes `bin/edit-manifest`, runs detection/validation/gates, executes verbs against its doc. The shared protocol file (`skills/mine.challenge/caller-protocol.md`) describes the doc-edit overlay of the manifest flow. Extension points are documented in the shared file.
- **A2. New `--manifest-interactive` mode on `/mine.challenge`**. Challenge handles the manifest + editor + detection + commit gate internally, then returns the resolved manifest (path or structured content) to the caller for execution. Challenge does NOT execute verbs for doc callers (it doesn't know doc semantics). Caller receives a resolved manifest and applies verbs.
- **A3. Full inheritance**: challenge executes verbs for doc callers by reading a caller-supplied "doc editor" config or by being taught about spec.md/design.md structure. Most coupling.

**Trade-offs**:

| Concern | A1 Shared protocol | A2 New challenge mode | A3 Full inheritance |
|---|---|---|---|
| Simplicity | High — no new mode, no cross-skill orchestration | Medium — challenge gains a mode and a return-contract | Low — challenge learns doc-edit semantics it doesn't need |
| Decoupling | High — challenge output contract unchanged | Medium — challenge gains a new return shape | Low — spec/design knowledge bleeds into challenge |
| Precedent in codebase | Strong — see `mine.orchestrate/retry-prompt.md`, `skills/mine.challenge/findings-protocol.md` | None — no challenge mode uses a "do part of the flow then return mid-execution" pattern | None |
| Compaction-safety | High — same as standalone (tmpdir state, pre-hash) | Medium — need to design cross-skill handoff state | Medium — coupled |
| Effort | Small-to-Medium | Medium-to-Large | Large |
| Risk | Low — mostly a shape rewrite | Medium — new mode contract to maintain | High — conflates two skill responsibilities |
| Reversibility | High — protocol file is prose | Medium — mode contract cements | Low — hard to untangle |

**Recommendation: A1 (shared protocol file, caller-owned execution).**

**Why**: A2 looks appealing because it centralizes the manifest mechanics in challenge. But challenge would then need to return the manifest mid-flow, wait for the caller to execute, and resume — there's no existing pattern for that in the codebase, and it adds a new contract surface that has to survive compaction. The manifest flow's state is in the tmpdir; moving the "manifest file lives in MY tmpdir" ownership across a skill boundary is fragile. A3 buries doc-editing knowledge in challenge, which is exactly wrong: challenge's job is to produce findings, not edit specific kinds of documents. A1 matches an established repo pattern (`findings-protocol.md` already works this way for standalone challenge — the protocol IS the shared contract, and the standalone flow IS the caller — A1 just adds more callers to that pattern).

**Additional argument for A1**: The perf win from commit `a5026f0` came from taking protocol OUT of the auto-load path and putting it in a skill-local file. A2 would need challenge to have the protocol loaded into every caller's context (as part of the mode behavior), which risks undoing that. A1 keeps the protocol in `skills/mine.challenge/` on-demand, per the established convention.

---

### Question 2: Verb-to-doc-edit mapping

**The current caller transformations**, extracted from SKILL.md reads:

| Finding classification | Current mine.specify behavior | Current mine.design behavior |
|---|---|---|
| Auto-apply, design-level: Yes, routes to spec/design | "State the change directly" → user approves → Edit tool call to spec.md/design.md section | Same |
| User-directed, design-level: Yes, routes to spec/design | "State options and recommendation" → user picks → Edit tool call | Same |
| TENSION | Append bullet to spec.md § Open Questions | Append bullet to design.md § Open Questions |
| design-level: Yes, routes to OTHER doc (specify→design) | Append bullet to design.md § Open Questions (created if missing) | N/A (no cross-doc routing in design) |
| design-level: No | List as "Not a spec change — flag for implementation phase". No edit. | List as "Flag for implementation — no design doc change needed". No edit. |

**Options**:

- **B1. Same verbs, verb-executor per caller, Doc target header field.** Canonical verbs. Each caller implements a small verb executor that reads the **Doc target** field alongside the verb to determine the edit. `fix` becomes "apply the recommended change per the Better approach field to the Doc target location." `defer` on TENSION becomes "append a bullet to the Doc target's Open Questions." `skip` is literal. `file` is identical across callers.
- **B2. Extend verb vocabulary** (e.g., add `append-oq` or `route-to-oq`). Rejected: violates the constraint "new verbs require strong justification." The Doc target field already does the work without new verbs.
- **B3. Caller-level adapter function**. Functionally similar to B1. In this codebase (where skills are LLM prose), the adapter is a small procedure described inline in each caller's SKILL.md, or in `caller-protocol.md`. B1 and B3 collapse here — they're the same thing.

**Recommendation: B1 (same verbs, Doc target field, per-caller verb executor).**

**Rationale**:
1. Zero new verb vocabulary. `findings-protocol.md`'s Verb Vocabulary table stays the source of truth.
2. The semantic overlay is carried by the existing `**Better approach:**` and `**Options:**` fields, which already describe the edit in concrete terms — the caller just needs to know which doc/section the edit applies to. A new `**Doc target:**` field in the manifest section header carries that context.
3. The manifest section becomes the self-describing contract. When user reads a manifest section, they see: which doc, which section, the edit, the options — no hidden classification.
4. Matches how standalone execution already works: `fix` on Auto-apply applies `better-approach` to whatever file is referenced in the finding. Docs are just files.

**Recommendation for finding's `recommendation` field shape for doc findings**: Critics already produce findings with `better-approach` (Auto-apply) and `options` (User-directed). For doc findings, critics should produce:

- `better-approach`: "Edit <doc> § <section-name> to change '<old>' → '<new>'" with enough precision for the verb executor to apply without ambiguity.
- `options`: Same, with each option specifying the exact edit.

This is **already the case** for findings generated by the current flow — critics are given the doc and told to produce structured fix proposals. No change to the challenge side of the contract.

---

### Question 3: Caller-specific routing

Current routing happens **before** the revision plan is presented. The question is how it integrates with the manifest flow.

**Options**:

- **C1. Routing pre-step produces different default verbs per finding** (recommended). The caller's routing heuristic runs once, before manifest generation. Each finding gets a default verb AND a Doc target field. The user sees the routing in the manifest ("This finding will append to spec.md § Open Questions as a TENSION") and can override verbs. Routing decisions are visible and editable.
- **C2. Extended verb vocabulary** (`route-to-oq`, `route-to-other-doc`, etc.). Rejected per Question 2.
- **C3. Routing happens post-execute as a cleanup pass**. E.g., execute verbs normally, then sweep for `defer` verbs whose Doc target is an Open Questions section and apply the append. This separates concerns (routing from editing) but creates a hidden second pass that the user can't preview in the manifest. Worse for transparency.
- **C4. Routing runs per-verb inside the verb executor**. The executor inspects each finding, decides where it goes, applies. The manifest doesn't show routing. Same transparency loss as C3.

**Recommendation: C1 (routing pre-step produces default verbs + Doc target field).**

**Implications**:
- The caller's routing table moves from "prose revision plan generator" to "manifest default-verb generator." Same inputs, same outputs, different rendering.
- The manifest's per-finding section gains a **Doc target** line (added to the Auto-apply/User-directed/TENSION templates as a standard field — documented in `caller-protocol.md`).
- For `design-level: No` findings, default verb is `skip` and Doc target is "(none — flag for implementation)". The user sees these findings in the manifest as intentionally skipped with a rationale. No surprise "what happened to that finding?" post-flow.
- For TENSION findings routed to Open Questions, default verb is `defer` and Doc target is "spec.md § Open Questions". The user can change the verb to `skip` or `file`; the verb executor treats `defer` as "append to Doc target's OQ section" specifically when Doc target points to an OQ section.

**Tension with findings-protocol.md**: `findings-protocol.md`'s Default Verb Selection table maps `TENSION` → `defer` with semantics "record in session summary; take no action." For doc callers, `defer` means "append to OQ." This is a semantic overlay that SHOULD be documented in `caller-protocol.md` with an explicit "In the doc-edit overlay, `defer` on TENSION appends to Doc target when Doc target is an Open Questions section" clarification. This is not a verb redefinition — it's a context-dependent action of an existing verb. Manageable in prose.

---

### Question 4: SYNC consolidation — where does the shared protocol live?

**Options**:

- **D1. New file at `skills/mine.challenge/caller-protocol.md`** (recommended). Peer to `findings-protocol.md`. Describes the doc-edit overlay, verb semantics for doc callers, pre-routing discipline, Doc target field, extension points (post-execute hooks for deferred findings persistence, custom validation).
- **D2. Extension to `findings-protocol.md`**. Add a "Doc-edit caller variant" section in the existing file. Pros: one file, clear cross-reference. Cons: `findings-protocol.md` is already ~24KB. Growing it couples code-finding protocol to doc-edit protocol, and any future caller for a new target type (research, brief) would further bloat the file.
- **D3. New `rules/common/caller-protocol.md`** rule file. Rejected — this reverses the commit `a5026f0` perf win by putting the content back in the auto-loaded rules directory.
- **D4. Inline in each caller, no shared file**. Rejected — recreates the SYNC block problem.
- **D5. Repo-root `design/` doc** (e.g., `design/protocols/challenge-caller-protocol.md`). Considered but not idiomatic for skill-protocol content; the `skills/mine.challenge/` location matches existing conventions.

**Recommendation: D1 (new file at `skills/mine.challenge/caller-protocol.md`).**

**Rationale**:
1. **Matches existing pattern**. `findings-protocol.md` already lives there; a sibling file is the natural extension. Other skills (`mine.orchestrate/`) already have multiple prose files alongside `SKILL.md`.
2. **On-demand loading**. Like `findings-protocol.md`, it won't be auto-loaded into subagent contexts. Preserves commit `a5026f0`'s perf improvement.
3. **Discoverable**. Callers reference it via `${CLAUDE_HOME:-~/.claude}/skills/mine.challenge/caller-protocol.md`, same convention as `findings-protocol.md`.
4. **Scoped growth**. New callers (future doc types, future research-flow callers) extend `caller-protocol.md` without bloating `findings-protocol.md` or the rules auto-load path.
5. **Keeps challenge's skill boundary clean**. The protocol files live where mine.challenge lives; callers reference them without mine.challenge needing to actively load or re-export them. Documentation-by-convention.

**Existing patterns for "skill A and skill B share protocol X"**:
- `skills/mine.challenge/findings-protocol.md` — shared across mine.challenge (standalone), mine.visual-qa (legacy), mine.tool-gaps (legacy). Referenced by `${CLAUDE_HOME:-~/.claude}/...` paths. This is the canonical pattern.
- `skills/mine.orchestrate/retry-prompt.md` ↔ `rules/common/receiving-code-review.md` — SYNC markers on both sides, content duplicated in two locations. This is the **anti-pattern** of SYNC markers ("don't be this" if you can avoid it).
- `rules/common/testing.md` ↔ `skills/mine.implementation-review/reviewer-prompt.md` — content inlined in the reviewer prompt with a SYNC marker. Same anti-pattern.

The takeaway: when possible, **single-source the protocol in one file and have the other file REFERENCE it**. The SYNC-marker pattern is only used when duplication is unavoidable (typically because a reviewer prompt needs the content verbatim in its context window, and the rule file would otherwise auto-load elsewhere). For our case, duplication is avoidable — both callers can reference `skills/mine.challenge/caller-protocol.md` directly.

**Resulting SYNC block elimination**:
- `skills/mine.specify/SKILL.md:343` — delete SYNC marker
- `skills/mine.design/SKILL.md:287` — delete SYNC marker
- Replace with explicit `${CLAUDE_HOME:-~/.claude}/skills/mine.challenge/caller-protocol.md` reference
- The **remaining** caller-specific content (routing heuristic table, deferred-findings persistence for specify, post-execute sign-off loop) stays inline in each SKILL.md. This content is genuinely caller-specific and should not be shared; it reads different files and applies different post-hooks.

---

## Concerns

### Technical risks

1. **`defer` verb has context-dependent semantics in the doc-edit overlay**. In standalone challenge, `defer` means "record in session summary." In doc callers, `defer` on a TENSION finding with Doc target = OQ section means "append bullet to OQ section." This context dependence must be documented explicitly in `caller-protocol.md` with worked examples, or it will be misinterpreted. The Manifest Validation Spec might need to assert "when Doc target is an OQ section, `defer` is treated as an append; when Doc target is 'none', `defer` is a no-op." This is a semantic overlay, not a verb redefinition — but it's subtle and easy to get wrong.

2. **Pre-hash and shadow-file for manifests that trigger caller-owned execution**. Currently the manifest's pre-hash is computed before `bin/edit-manifest` launches. After the editor closes, detection runs, commit gate fires, then challenge executes verbs. For caller-owned execution, the same sequence must work: detection + validation + commit gate happen in the caller's flow, using the same decision table. The protocol file must be clear that these phases are caller-hosted (reusing the procedure from `findings-protocol.md`).

3. **Compaction mid-caller flow**. If compaction happens between Consent Gate and verb execution, the caller needs to resume. The manifest file in the tmpdir is the compaction-safe state (same as standalone). The caller's SKILL.md must describe recovery: "If resuming a caller-invoked manifest session, re-read `<tmpdir>/resolutions.md` and `<tmpdir>/findings.md`; do not regenerate the manifest." Same recovery pattern as standalone — works because the mechanics are identical.

4. **Post-execute hooks (deferred findings persistence for mine.specify)**. The current deferred-findings code runs after the bundled gate handles revisions. In the new flow, it runs after verb execution. The set of findings to persist is now "findings whose verb was `defer` AND whose Doc target is 'design.md Open Questions stub'" — a clean query. The risk is accidental inclusion of findings the user skipped or rerouted; the query must be precise.

5. **The edit-manifest fallback (exit 2, tertiary fallback)**. Doc-edit callers should inherit the tertiary fallback (write path + instruct user to edit + wait for chat signal) without modification. Test this explicitly in validation.

### Complexity risks

1. **Manifest template now has a Doc target field**. Three templates (Auto-apply / User-directed / TENSION) each gain the field. The protocol file has to keep these in sync. Small risk of drift if someone modifies one template later without the others. Adding an inline reminder in `caller-protocol.md` ("all three templates include **Doc target**") mitigates.

2. **Two protocol files feels like protocol creep**. `findings-protocol.md` and `caller-protocol.md` coexist; a third variant (e.g., for future `mine.research` or `mine.brainstorm` findings consumption) could emerge. This is a slippery slope worth naming now. Recommendation in the design doc: cap at two. If a third variant is needed, restructure into "core + overlays" before expanding.

3. **Verb executor per caller adds maintenance surface**. `mine.specify`'s executor edits spec.md. `mine.design`'s executor edits design.md. They're structurally similar but not identical (different section names, different Open Questions behavior for TENSION routing, different deferred-findings hook). Keeping them in sync requires vigilance — though the SYNC-block today is NO better, and this version is at least smaller and more scoped.

### Maintenance risks

1. **If `bin/edit-manifest` changes its contract later, both standalone challenge and doc callers are affected**. Today only standalone is affected. This is a new coupling — manageable because the contract is simple and well-defined, but worth flagging.

2. **Long-term, caller-protocol.md is a second "auto-load candidate"**. If someone decides to move it into `rules/common/` for convenience, they undo commit `a5026f0`'s perf win AGAIN. The design doc should name this explicitly: "Keep `caller-protocol.md` in `skills/mine.challenge/`. Do not move it to `rules/common/` — see commit `a5026f0`."

3. **Test strategy is session-level manual validation only**. Same as 015. The design doc should specify explicit validation scenarios: (a) run `/mine.specify` through to "Challenge this spec first"; verify manifest-based flow replaces the old bundled gate. (b) same for `/mine.design`. (c) verify deferred findings persistence still produces design.md stub. (d) verify no bundled AskUserQuestion appears. (e) verify TENSION handling still routes to OQ. (f) verify `design-level: No` findings are visible in the manifest as `skip` with clear rationale (not silently excluded).

### Concern callout — the chosen approach has a significant risk

**The doc-edit verb semantics overlay is subtle and may confuse readers** of `caller-protocol.md`. Specifically, `defer` having two meanings:
- Standalone challenge: "record in session summary, take no action."
- Doc caller (when Doc target is an OQ section): "append bullet to the OQ section."

This is not a verb redefinition — the verb still represents "user deferred this decision" — but the **action** taken under that verb depends on the Doc target. If the design doc does not make this crystal clear with worked examples, downstream maintainers could either:
- Misimplement the verb executor (treating `defer` always as "no action" and losing TENSION routing), or
- Conclude that a new verb is needed and add one without the required justification.

**Recommendation for the design phase**: consider adopting an alternative framing where the "append-to-OQ" behavior is a **post-execute routing pass** (Option C3 from Question 3) instead of an overlay on `defer`. Under C3:
- The verb executor treats `defer` uniformly: "no action, record in session summary."
- A separate post-execute caller hook sweeps findings whose `severity: TENSION` AND `verb: defer` AND computes the OQ append from the Doc target.
- This makes the verb semantics uniform and moves the doc-specific logic to a clearly-labeled caller hook.

The trade-off: the user can no longer change the TENSION-to-OQ routing by changing the verb in the manifest — the routing is implicit in the finding's tags + the caller's post-execute pass. But the user **also can't change it in today's bundled flow**, so there's no loss of functionality. And the verb semantics stay clean.

The design doc should decide between (Q3-C1 + overlay) and (Q3-C1 + post-execute hook). Both are viable; the post-execute hook is slightly simpler to explain and harder to misimplement.

## Open Questions

- [ ] **Exact shape of the Doc target field in the manifest template**. One-line string ("spec.md § Open Questions") or a structured sub-record (doc, section, sub-section)? Structured is better for validation; string is simpler for the user to read. Recommendation for design phase: one-line string; the caller's verb executor parses it.
- [ ] **Default verb for design-level: No findings in doc callers**. `skip` (recommended — user can override to `file` if they want to create a backlog issue) vs `file` (more forceful about "don't drop this" but may produce lots of issues users don't want). Recommendation: `skip` with an explicit rationale field in the manifest section.
- [ ] **Should `caller-protocol.md` include worked examples**? Strongly recommend YES — three examples (Auto-apply, User-directed, TENSION) each rendered as a manifest section, to prevent ambiguity about the Doc target field usage.
- [ ] **Do we rename the existing `findings-protocol.md` to `standalone-protocol.md`** for symmetry with `caller-protocol.md`? Answer: **NO**. Existing references use `findings-protocol.md`; the rename would be churn without benefit. Name describes content well enough.
- [ ] **Verb executor lives in caller SKILL.md inline, or as a sibling `verb-executor.md` file**? Recommendation: inline in each caller SKILL.md, because the verb-to-edit mapping references file paths specific to each caller.
- [ ] **Migration order — specify first or design first**? Both need migration. No strict order required; the protocol file must be written first so both callers can reference it. Recommend implementing both in one commit for test symmetry.
- [ ] **Skill-Specific Overrides section in `findings-protocol.md`** currently mentions visual-qa and tool-gaps as legacy. Should `caller-protocol.md` also be mentioned here? Answer: **YES** — add a pointer in `findings-protocol.md` Skill-Specific Overrides so readers discover `caller-protocol.md` from the primary protocol file.
- [ ] **Does this work require re-challenging spec 015**? The dogfood pass validated 015 itself; this extension is a follow-up design that should be challenged on its own merits before shipping. The design doc will go through `/mine.challenge` per convention.

## Recommendation

**Proceed to design doc with Option A (caller-owned execution + shared protocol file at `skills/mine.challenge/caller-protocol.md`).** The approach is structurally simple, matches existing repo conventions, eliminates the three anti-patterns at both caller sites, and does not regress the perf win from commit `a5026f0`.

**Explicit decisions for the design phase to lock in**:

1. Ownership: A1 — shared protocol file + caller-owned execution.
2. Verb mapping: B1 — same verbs, Doc target field, per-caller verb executor.
3. Routing: C1 — pre-route before manifest generation; routing produces default verbs + Doc target fields. **Consider** the Concerns-callout alternative (C3 for OQ-append) if design-phase critics find the `defer` overlay too subtle.
4. SYNC consolidation: D1 — new file at `skills/mine.challenge/caller-protocol.md`; delete SYNC markers; delete bundled gates; retain caller-specific routing/post-hook content inline per caller.

### Suggested next steps

1. **Write the design doc** via `/mine.design` with this brief as input. The design phase should:
   - Resolve the `defer` overlay vs post-execute hook question (Concerns callout).
   - Specify the exact Doc target field format.
   - Specify the exact section-matching logic for each caller's verb executor (how does "spec.md § Acceptance Criteria" translate into an Edit tool call?).
   - Decide whether to rename `findings-protocol.md` (recommended: no).
   - Define dogfood validation scenarios.
2. **Challenge the design doc** before approval — this is a non-trivial protocol extension and warrants adversarial review.
3. **Implement in one PR** (single commit or small set of commits): protocol file + both SKILL.md migrations + `findings-protocol.md` pointer update.
4. **Dogfood validate** on a real in-flight spec/design before merging. Capture the session as evidence of no bundling (same style as 015's session logs).
5. **After migration, update the "Structured callers" list** in `skills/mine.challenge/SKILL.md:116-118` and in findings-protocol.md's Skill-Specific Overrides section to reflect the new shape.

### What NOT to do

- Do NOT put the new protocol in `rules/common/` (reverses commit `a5026f0`).
- Do NOT add new verbs to the vocabulary (constraint).
- Do NOT add a new `--manifest-interactive` mode to `/mine.challenge` (A2) — over-complicates without benefit.
- Do NOT migrate `mine.tool-gaps` or `mine.visual-qa` as part of this work (out of scope per non-goals).
- Do NOT regress the standalone challenge flow's contract (constraint).

## Sources

None — this is a codebase-only investigation per the caller prompt's explicit instruction to treat the existing research (design 015, `design/research/2026-04-09-per-item-resolution-loops/research.md`) as context, not to repeat the prior-art work.
