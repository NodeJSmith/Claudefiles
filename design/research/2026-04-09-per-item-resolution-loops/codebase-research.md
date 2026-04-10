# Research Brief: Per-Finding Resolution Manifest for mine.challenge

## Summary

**Feasible.** Every investigation area is Green except #6 which is Yellow (user-interaction path requires a pragmatic compromise). The findings schema already carries everything a manifest renderer needs; Phase 4 has a clean, well-commented insertion point; and the blast radius on `rules/common/findings.md` is small (only four direct consumers: mine.challenge, mine.visual-qa, mine.tool-gaps, and one `description` string shared with `mine.visual-qa`'s gate). Structured callers (mine.design, mine.specify, mine.orchestrate) are completely unaffected — they bypass the resolve flow entirely.

**Recommended user interaction**: **Option D (hybrid)** — the skill writes a durable manifest file, displays it inline, and offers the user free-text edit ("change F4 to file, F7 to skip") OR direct file edits, with a single final confirmation AskUserQuestion before execution. This preserves the structural anti-bundling property (the manifest IS the per-finding review surface) while matching precedent from mine.design's "Revise" sign-off loop.

## Prior Art Context

The prior-art brief at `design/research/2026-04-09-per-item-resolution-loops/research.md` established that batch-collapse cannot be fixed with prose rules alone (IFScale, "When Instructions Multiply," "LLMs Get Lost in Multi-Turn Conversation"). Of six patterns surveyed, **Editable Decision Manifest** (Pattern 2, git rebase-i's todo file) was ranked highest-leverage because the manifest *is* the review surface — there is no prompt loop for the LLM to collapse. Pattern 6 (Named Anti-Pattern Catalog) was identified as a mandatory companion for defense-in-depth even with the manifest adopted. Pattern 4 (Group By Kind) was explicitly rejected because grouping is exactly what the LLM is already doing wrong.

## Findings by Area

### 1. Phase 4 Handoff Mechanics
**Feasibility**: Green

The handoff is unambiguous and the insertion point is obvious. Tracing the control flow from `skills/mine.challenge/SKILL.md`:

- **Phase 4 start**: line 431 (`## Phase 4: Present Findings`). The findings file already exists at this point (verified at line 427).
- **Per-finding rendering**: lines 443–488. The skill reads findings.md and renders each finding using the template at lines 449–488. This is purely a display loop — no user interaction yet.
- **"After presenting findings"**: lines 490–498. Lists critic report paths to the user.
- **Wrap-up dispatch**: lines 500–512. Reads `# mode:` from `<tmpdir>/manifest.md` (compaction-safe — session state lives on disk, not in LLM memory). Three branches:
  - `structured` → stop, caller takes over.
  - `passthrough` → summary only, no gate.
  - `standalone` → summary paragraph, then "follow the findings convention in `rules/common/findings.md`: present the Proceed Gate, collect all user-directed answers, then execute fixes." (Line 510.)

**State in scope at the handoff** (all recoverable from disk):
- `<tmpdir>` (known from manifest.md comment lines read at Phase 4 start, line 435)
- `<tmpdir>/findings.md` (the findings file, path derivable from manifest's `# findings-out:`)
- `<tmpdir>/manifest.md` (the session manifest, already being consulted)
- `# mode: standalone` (branch determinant)
- Target name, specialist list, target type (all in manifest comments)

**How the LLM "executes" `rules/common/findings.md`**: The rule file is loaded into context automatically (it's in `rules/common/`, which auto-loads per repo convention). Line 510 is a verbal delegation — the LLM re-reads the rule's prescriptions from its already-loaded content and follows them. There is no `Read()` call or execution semantics; it is a prompt-instruction chain.

**Insertion point for a manifest step**: Between line 508 (summary) and line 510 (delegate to findings.md). The minimal new instruction block would be:

> "Before delegating to `rules/common/findings.md`, write a per-finding resolution manifest to `<tmpdir>/resolutions.md`. Read each `## Finding N:` block from findings.md and emit one resolution line per finding with a default verb pre-selected from the finding's `resolution` field (`Auto-apply` → `fix`, `User-directed` → recommended option name or `ask`). The manifest is the review surface; the subsequent resolve flow executes from it."

The risk here is minimal — the insertion is additive, sits after display rendering, and happens before the rule-delegation sentence. No other phase or caller touches this interval.

### 2. Findings File Schema
**Feasibility**: Green

The findings file schema (defined at `skills/mine.challenge/SKILL.md:402–423`) has **exactly** the fields a per-finding manifest block needs:

| Manifest block field | Source in findings.md | Field status |
|---|---|---|
| Finding ID | `## Finding N:` heading (numeric) | Always present — synthesis numbers sequentially |
| Severity | `severity:` (line 403) | Contract field, always present, constrained vocabulary |
| Short description | `summary:` (line 409) | Always present |
| Resolution class | `resolution:` (line 407) | Contract field, always present, `Auto-apply` or `User-directed` |
| Recommended option | `recommendation:` (line 416) | User-directed only; always present for those |
| Option list | `options:` (line 415) | User-directed only; mutually exclusive with `better-approach` |
| Fix description | `better-approach:` (line 414) | Auto-apply only; mutually exclusive with `options` |
| TENSION side-a/side-b/deciding-factor | lines 417–419 | TENSION only |

**Mutual exclusivity is key** (lines 414–415): `better-approach` and `options` are explicitly mutually exclusive per resolution class. This is ideal for a manifest renderer — a single renderer can branch on `resolution:` and emit the correct "default verb" without ambiguity:

- `resolution: Auto-apply` → default verb `fix` (use `better-approach` text)
- `resolution: User-directed` → default verb `ask` or the recommended option letter (use `recommendation` + `options`)
- `resolution: TENSION` → default verb `defer` (use `deciding-factor`)

**Consistency check** — optional/absent fields are well-documented and all have graceful fallbacks:

- Presentation-only fields (`why-it-matters`, `evidence`, `references`, `design-challenge`) may be absent in pre-enrichment format-version 1 files. Phase 4 already handles this gracefully (lines 99–105, 445, 488). A manifest renderer can ignore these — none are needed for the manifest itself.
- `evidence: not cited` is a known sentinel (line 103, 380).
- Contract fields (`severity`, `type`, `design-level`, `resolution`) are always present per the synthesis rules (line 371 enforces the severity vocabulary; line 374 defaults `resolution` to User-directed when ambiguous).

**Critical non-issue discovered**: there is no `finding-id` field separate from the heading number. The manifest can key off the sequential numbering (`## Finding 1:`, `## Finding 2:`) because Phase 4 already requires findings be "numbered sequentially (`### 1.`, `### 2.`, etc.) for easy reference in conversation" (line 447).

**No field is missing.** The schema as it stands (post-PR #195 enrichment) is a superset of what a manifest needs. No changes to synthesis are required.

### 3. rules/common/findings.md Changes
**Feasibility**: Green

The current `rules/common/findings.md` is 54 lines and has three sections: "Principle," "Presenting Findings," "Proceed Gate," "Resolving Findings," "Skill-Specific Overrides." The file is entirely prescriptive-abstract — no anti-pattern enumeration, no concrete examples, no structural enforcement.

**Changes needed**:

1. **Add a "Resolution Manifest" section** describing the new primary flow, modeled structurally on the existing `interaction.md` "AskUserQuestion Blocks in Skills (CRITICAL)" section (`rules/common/interaction.md:31–49`). This becomes the new primary resolve flow. The manifest becomes the review surface; the post-manifest step is a single Proceed Gate (`Execute the manifest? Yes/No`) and then one AskUserQuestion per "ask" verb during execution.

2. **Add a Named Anti-Pattern Catalog** modeled verbatim on interaction.md's pattern. Enumerate the failure modes caught in logs:
   - **Bundling** — "Do not bundle N findings into a single 'Accept all?' AskUserQuestion. Emit one AskUserQuestion per User-directed finding during execution of the manifest."
   - **Multi-select-as-verb-selector** — "Do not use `multiSelect: true` to mean 'fix some, file others.' multi-select is for 'which items,' not 'which verb.' Verbs belong to the manifest, not to the gate."
   - **Double-gate after 'Yes'** — "Do not re-prompt 'Which findings?' after the Proceed Gate. The Proceed Gate's default is all findings; verb per finding comes from the manifest."
   - **Meta-gates with relabeled Proceed Gate** — "Do not rename the Proceed Gate with new labels (e.g., 'Review findings,' 'Triage findings') and re-implement its logic. There is one Proceed Gate per resolve flow."
   - **Options-showing-actions-instead-of-problems** — "Option labels describe the finding ('F3: Race in cache eviction'), not the action ('Fix it'). The action is the verb column of the manifest."
   - **Auto-apply mixed with judgment calls in one prompt** — "Do not interleave Auto-apply execution with User-directed questions. Auto-apply executes silently during manifest execution; User-directed triggers a per-finding prompt."

3. **Retain the Proceed Gate** but subordinate it to the manifest. The manifest is presented, the Proceed Gate asks "Execute manifest? Yes/No," and the Resolving Findings section uses the manifest as the source of truth rather than "collect all user-directed answers first."

4. **The current "Presenting Findings" section** (lines 9–17) stays unchanged — it governs how findings are presented *before* the manifest step, and the "Option A is Recommended" convention continues to apply.

**Blast radius from grep** (every reference to `rules/common/findings.md` in the repo — full list from the grep above):

| File | Line | Reference | Impact |
|---|---|---|---|
| `skills/mine.challenge/SKILL.md` | 11 | "When invoked standalone, challenge resolves findings via `rules/common/findings.md`" | Statement still true. No change needed. |
| `skills/mine.challenge/SKILL.md` | 510 | Phase 4 delegation: "follow the findings convention in `rules/common/findings.md`: present the Proceed Gate, collect all user-directed answers, then execute fixes." | **Requires update** — the prose describing the flow (`present the Proceed Gate, collect all user-directed answers`) needs to change to reference the new manifest-first flow. Minor rewrite. |
| `skills/mine.challenge/SKILL.md` | 524 | Principle 9: "When invoked standalone, challenge resolves findings via `rules/common/findings.md`." | Statement still true. No change needed. |
| `skills/mine.visual-qa/SKILL.md` | 284 | "skill-specific gate (per `rules/common/findings.md` Skill-Specific Overrides)" | Statement still true. Skill-Specific Overrides section stays. No change required (see caller impact below for detail). |
| `skills/mine.visual-qa/SKILL.md` | 301 | "follow `rules/common/findings.md` for the resolve flow (collect all user-directed answers first, then execute fixes)" | **Requires prose update** — same as challenge line 510. Change to "follow the resolution manifest flow in `rules/common/findings.md`." |
| `skills/mine.visual-qa/SKILL.md` | 305 | "**Fix issues** → follow `rules/common/findings.md` resolve flow" | No update strictly needed (the reference is path-level). |
| `skills/mine.tool-gaps/SKILL.md` | 178 | "skill-specific gate per `rules/common/findings.md` Skill-Specific Overrides" | No update needed — tool-gaps uses its own override gate with implement/issue/skip. |

**Total files requiring touch**: 3 (mine.challenge, mine.visual-qa, mine.tool-gaps — and tool-gaps is optional). All changes are prose-only, not contract changes. The `Format-version: 2` of findings.md is not affected; no caller needs to bump a version constant.

### 4. Caller Impact
**Feasibility**: Green

The hypothesis is **confirmed**: only standalone invocations are affected. Per-caller classification:

| Caller | File | Consumption pattern | Impact of manifest change |
|---|---|---|---|
| **mine.design** | `skills/mine.design/SKILL.md:283` | Structured — invokes `/mine.challenge --findings-out=<dir>/findings.md --target-type=design-doc`. Reads the findings file via line 292 comment `<!-- CHALLENGE-CALLER -->` and generates its own revision plan (lines 302–334). **Never touches the standalone resolve flow.** | **None.** Bypasses `rules/common/findings.md` entirely. The caller's own "Apply all / Cherry-pick / Skip" gate is unaffected. |
| **mine.specify** | `skills/mine.specify/SKILL.md:341` | Structured — same pattern as mine.design. Reads findings.md, generates its own revision plan with spec-specific routing (lines 352–414). The `<!-- SYNC -->` comment at line 345 explicitly notes this stays in sync with mine.design. | **None.** Bypasses the standalone resolve flow. |
| **mine.orchestrate** | `skills/mine.orchestrate/SKILL.md:756` | Structured — invokes `/mine.challenge --findings-out=<tmpdir>/challenge-findings.md --focus="design conformance"` during Phase 3. Reads the findings file directly (line 766) and feeds findings to its own "Address findings" subagent dispatch (lines 788–795). | **None.** Bypasses the standalone resolve flow. |
| **mine.grill** | `skills/mine.grill/SKILL.md:128,139` | Standalone caller — invokes `/mine.challenge --target-type=brief <feature_dir>/brief.md` (no `--findings-out`), waits for standalone flow to complete, then loops back to its handoff gate. | **Affected** — inherits whatever resolve flow mine.challenge Phase 4 dispatches when `mode: standalone`. The change is positive (no bundling) and behaviorally transparent (mine.grill doesn't care *how* resolution happened). |
| **mine.research** | `skills/mine.research/SKILL.md:184` (found in search) | Passthrough — invokes `/mine.challenge --mode=passthrough --target-type=research <brief>`. Challenge's Phase 4 explicitly skips the resolve flow for passthrough mode (line 512). | **None.** No resolve flow runs in passthrough mode. |
| **mine.brainstorm** | (passthrough per mine.challenge SKILL.md:128) | Passthrough — same as mine.research. | **None.** |
| **mine.visual-qa** | `skills/mine.visual-qa/SKILL.md:284,301,305` | Has a skill-specific override gate (line 284) per `rules/common/findings.md` Skill-Specific Overrides. When user selects "Fix issues now" from the override gate, it delegates to the resolve flow (line 301). | **Affected in the "Fix issues now" branch only.** Visual-qa's own skill-specific gate (with re-run and read-report options) stays. Only the post-fix-issues handoff changes — and it changes in a way that makes visual-qa's fix path *better*, not breaking. Visual-qa's findings are simpler than challenge's (no User-directed vs Auto-apply distinction), so the manifest rendering must handle a simpler schema — see open question below. |
| **mine.tool-gaps** | `skills/mine.tool-gaps/SKILL.md:178` | Skill-specific gate only. Does not delegate to the resolve flow — it has its own implement/issue/skip path. | **None.** No delegation to the standalone resolve flow. |
| **mine.build** | `skills/mine.build/SKILL.md:50` | Detection caller — scans for severity labels in prior context; does not read findings.md. | **None.** Detection is unaffected. |

**Breaking changes identified**: None in the contract sense. The findings.md schema is unchanged; the caller-facing contract (`Format-version: 2`, contract tag names, temp dir field) is unchanged. Only prose references in 2–3 files need updating.

### 5. Manifest File Location & Lifecycle
**Feasibility**: Green

**Recommended location**: `<tmpdir>/resolutions.md` — the same tmpdir the findings file already lives in.

**Reasoning**:

1. **Findings file precedent**: The findings file itself already lives in the tmpdir (`<tmpdir>/findings.md`, line 110). Putting the manifest alongside it is the obvious symmetry.
2. **Compaction safety is already handled at the tmpdir level**: mine.challenge has a well-documented "all session state lives in this file" pattern via `<tmpdir>/manifest.md` (lines 315, 502). The manifest for Phase 4 recovery (`manifest.md`) and a new `resolutions.md` are both compaction-safe because mine.challenge's Phase 4 already re-reads state from disk (line 435: "This is the compaction-safe recovery path — all session state lives in this file, not in LLM context recall").
3. **7-day cleanup is appropriate**: The tmpdir is cleaned after 7 days (CLAUDE.md convention). For an interactive session where the user is sitting at their terminal making decisions, 7 days is massively over-specified. Resolution decisions live and die with the session; there is no "pick up this resolve flow in 3 weeks" use case.
4. **No precedent for durable resolution artifacts**: Searching for `design/research/` or `design/challenge/` patterns turns up research briefs (`design/research/YYYY-MM-DD-topic/`) and design docs (`design/specs/NNN-slug/`), but nothing equivalent for challenge resolutions. Adding a new durable artifact type (`design/challenge/NNN-name/resolutions.md`) would create a new artifact class with no existing lifecycle management. This is a strong signal to keep resolutions.md ephemeral.
5. **Context compaction mid-resolve**: Handled by the same mechanism Phase 4 already uses — re-read `<tmpdir>/manifest.md` for session state, re-read `<tmpdir>/findings.md` for findings, re-read `<tmpdir>/resolutions.md` for the resolution state. The skill explicitly calls out this pattern at line 502: "The manifest is the authoritative source after potential compaction." Extending this pattern is free.

**Rejected alternative**: `design/challenge/NNN-name/resolutions.md` (durable). Rejected because:
- Adds a new artifact type with no existing lifecycle handling
- Resolutions are session-scoped by design — persisting them invites stale-artifact confusion
- The prior-art brief notes mine.prior-art saves durably only for briefs that feed downstream handoffs (design, build) — resolutions don't feed anything downstream
- Git-ignoring or Git-tracking the file is a new question to answer
- No caller needs resolutions.md to persist beyond the session

**Lifecycle**:
1. Phase 4 standalone wrap-up writes `<tmpdir>/resolutions.md` with default verbs pre-selected from findings.md.
2. User edits (see §6) to override defaults.
3. Skill re-reads the manifest before executing each verb.
4. After execution, the manifest remains in tmpdir as session history.
5. 7-day cleanup deletes the whole tmpdir.

**Crash/compaction recovery**: If the orchestrating context is compacted mid-resolve, the skill can recover state by re-reading `<tmpdir>/manifest.md` (to determine mode/target), `<tmpdir>/findings.md` (for finding content), and `<tmpdir>/resolutions.md` (for the user's verb choices so far). This is stronger than the current Phase 4 standalone flow, which has zero durable state for the resolve phase — a compaction mid-resolve today means the LLM has to re-derive everything from context scrollback.

### 6. User Interaction Path
**Feasibility**: Yellow

Claude Code has no `$EDITOR` popup mechanism. The user cannot `vim resolutions.md` the way `git rebase -i` opens an editor. The user interacts with the skill by typing messages or responding to AskUserQuestion. This constrains the manifest pattern and makes Option B (pure "edit the file, then say go") awkward.

**Evaluating the four candidate options**:

| Option | Anti-bundling force | Ergonomics | Precedent in repo |
|---|---|---|---|
| **A**: Manifest as display device + AskUserQuestion per finding to confirm/override | Strong — the per-finding loop is preserved, just grounded in the manifest reference. The manifest IS the source of truth, so bundling becomes obviously wrong ("finding 4 in the manifest, not findings 4-11"). | Medium — still requires N AskUserQuestion calls for N user-directed findings. Fatigue at 20+ findings. | Weak — no skill currently does this, though it's the minimum-change option. |
| **B**: Write manifest, tell user "edit this file, then say 'go'" | **Strongest** — eliminates the prompt loop entirely. The user edits the manifest directly via Edit tool calls in their next turn. Skill re-reads and executes. There is no "per-finding prompt" to bundle. | **Poor** — requires the user to issue Edit tool calls on a file path they just saw. Most users won't know to do that; they'll respond with "looks good" or free-text edits. Friction is the dominant failure mode. | **None** — no skill in the repo uses a "user edits a file then says go" pattern. The closest is mine.design's "Revise" sign-off, but even that uses free-text instructions that the skill applies (line 358). |
| **C**: Write manifest, user responds with free-text ("change F4 to file, F7 to skip"), skill parses and updates | Strong — the manifest is the shared reference and the user sees all findings at once. Free-text encourages batch edits ("F4 and F7 file, rest fix") without falling into the AskUserQuestion bundling trap because there's no "Accept all?" prompt. | **Good** — matches how mine.design handles revise: "Ask what to change. Apply the edits to the design doc. Re-present the updated doc." (mine.design line 358.) Precedent exists. | **Yes** — mine.design's Revise flow is structurally identical. |
| **D**: Hybrid — write manifest, display inline, accept free-text edits OR direct Edit tool calls, then ONE final Proceed Gate (`Execute manifest? Yes/No`) | Strong — same anti-bundling force as C, plus an explicit commitment gate that doesn't re-implement per-finding decisions. | **Best** — supports both user preferences (pro users who Edit the file, casual users who say "F4 file, rest fix"), and the final single AskUserQuestion is a legitimate commit gate, not a bundled decision prompt. | Partial — mine.design's Revise + "re-present + sign-off" is the closest analog. |

**Recommendation**: **Option D (hybrid)**.

**Reasoning**:
1. **Anti-bundling is preserved structurally**: The manifest is the review surface. The final AskUserQuestion asks "Execute this manifest? Yes/No" — it is NOT a bundled fix-vs-file prompt. The LLM has no path to bundle because the only decision at the gate is *whether to run the already-decided verbs*.
2. **Ergonomics**: Users can respond naturally ("change F4 to file") — no Edit tool knowledge required. But advanced users can also use Edit directly.
3. **Precedent exists**: mine.design's Revise flow (line 358) already uses the "skill writes an artifact, user says what to change in free text, skill applies edits, re-present" pattern. Extending this from design docs to resolution manifests is a natural generalization.
4. **Iteration loop is compaction-safe**: After each edit cycle, the skill writes `<tmpdir>/resolutions.md` and re-presents. State lives on disk.
5. **Execution-phase per-finding prompts still exist but are unbundlable**: For `ask` verbs (user-directed findings without a pre-selected option), execution emits ONE AskUserQuestion per finding with `(N/M)` position header. This is the Pattern 1 (Position Counter) fallback from the prior-art brief, used only for the subset of findings that actually need interactive choice at execution time. Most findings will have been pre-decided via the manifest, eliminating the bundling attack surface.

**Rejected**: Option A (adds no structural benefit over status quo — the manifest becomes a decorative header for the same bundled prompt). Option B (unworkable without an $EDITOR mechanism). Option C (no final commit gate feels ungrounded and risks "just do it" drift).

**Key test — does this prevent bundling?** Yes, structurally. The bundling failure mode requires the LLM to present N findings in one AskUserQuestion. With the manifest flow:
- **Presentation**: findings are already rendered per-finding in Phase 4's display loop (lines 443–488). No change.
- **Decision collection**: happens via free-text editing OR direct Edit tool calls. No AskUserQuestion at all.
- **Commitment**: one AskUserQuestion with two options (Yes, execute / No, revise). Not bundling — it's a single binary commit gate.
- **Execution of `ask` verbs**: one AskUserQuestion per finding, enforced by the manifest format (one row per finding = one prompt).

## Recommended Implementation Sketch

Minimum change set:

1. **`rules/common/findings.md`** — rewrite structure:
   - Add "Resolution Manifest" section as the new primary flow (before "Resolving Findings")
   - Add a Named Anti-Pattern Catalog section (modeled on `interaction.md:31–49`) enumerating the 6 failure modes listed in §3
   - Retain Proceed Gate but reposition as "Execute manifest? Yes/No" after the manifest is presented and edited
   - Retain Skill-Specific Overrides section (no change)
   - Update "Resolving Findings" to execute from manifest verbs rather than "collect all user-directed answers first"

2. **`skills/mine.challenge/SKILL.md` line 508–512** — insert manifest generation step:
   - After the summary paragraph, add: "Read findings.md and write a resolution manifest to `<tmpdir>/resolutions.md`. Emit one line per finding with a default verb: `fix` for Auto-apply, `ask`/`A`/`B` (the recommended option) for User-directed, `defer` for TENSION. Display the manifest inline. Then follow the Resolution Manifest flow in `rules/common/findings.md`."
   - Update line 510's prose from "present the Proceed Gate, collect all user-directed answers, then execute fixes" to "follow the Resolution Manifest flow."

3. **`skills/mine.visual-qa/SKILL.md` line 301** — minor prose update:
   - Change "follow `rules/common/findings.md` for the resolve flow (collect all user-directed answers first, then execute fixes)" to "follow the Resolution Manifest flow in `rules/common/findings.md`."

4. **Manifest file format** (new convention, lives in `rules/common/findings.md`):
   ```
   # Resolution Manifest — <target>
   # Verbs: fix | file | defer | skip | ask (user-directed only) | A | B | C (option selection)
   # Edit verbs below, or say "change FN to <verb>" in chat.

   F1  fix    CRITICAL   Race condition in cache eviction
   F2  fix    HIGH       Missing null check in auth handler
   F3  B      HIGH       Logging strategy (option B: structured)
   F4  ask    MEDIUM     Error handling boundary (user-directed)
   F5  defer  TENSION    Coupling between modules (critics disagree)
   F6  fix    MEDIUM     Unused import
   ```
   - Fixed-width columns: `F<N>`, `<verb>`, `<severity>`, `<summary>`
   - Comment header documents the verb vocabulary
   - One row per finding (structural anti-bundling)

5. **Execution flow** (in `rules/common/findings.md`):
   - Present manifest inline
   - Accept free-text edits or Edit tool calls; re-read and re-present after each edit
   - Single AskUserQuestion: `Execute manifest? [Yes / No, revise]`
   - On Yes: iterate manifest rows. For each `fix` verb → auto-apply. For each `file` verb → `gh-issue create`. For each `ask` verb → emit ONE AskUserQuestion with `(N/M)` header for this row only. For `A`/`B`/`C` → apply the pre-selected option. For `defer` or `skip` → no action.
   - Final summary

## Caller Contracts Requiring Updates

| File | Change | Risk |
|---|---|---|
| `rules/common/findings.md` | Full rewrite — add Resolution Manifest section, Named Anti-Pattern Catalog, update Resolving Findings | Low — this file is the contract surface, but only 3 consumers reference it by name and none depend on its internal structure |
| `skills/mine.challenge/SKILL.md` lines 508–512 | Insert manifest generation step; update line 510 prose | Low — Phase 4 standalone path only, structured callers unaffected |
| `skills/mine.visual-qa/SKILL.md` line 301 | Minor prose update for new flow name | Low — cosmetic |
| `skills/mine.challenge/SKILL.md` lines 11, 524 | No change — both say "resolves findings via `rules/common/findings.md`" which remains true | None |
| `skills/mine.tool-gaps/SKILL.md` line 178 | No change — uses Skill-Specific Overrides pattern, has its own gate | None |
| `skills/mine.design/SKILL.md` | No change — structured caller, bypasses resolve flow | None |
| `skills/mine.specify/SKILL.md` | No change — structured caller | None |
| `skills/mine.orchestrate/SKILL.md` | No change — structured caller | None |
| `skills/mine.grill/SKILL.md` | No change — delegates to standalone flow, inherits improved behavior | None |
| `skills/mine.research/SKILL.md`, `skills/mine.brainstorm/SKILL.md` | No change — passthrough callers, skip resolve flow | None |

**Total files touched**: 3 (1 rule + 2 skills). All prose-level changes. No contract tag or schema changes.

## Open Questions

- **Manifest renderer location**: Does the render logic live in `rules/common/findings.md` as normative prose (the LLM reads findings.md and writes the manifest in its next message), or does mine.challenge's Phase 4 own the render step explicitly? Recommendation: Phase 4 owns the render step for challenge specifically; findings.md describes the manifest format and the execution flow. This keeps the mine.visual-qa path (which also uses findings.md) from having to render identical content for a simpler schema.
- **Visual-qa manifest schema differences**: mine.visual-qa findings don't have `resolution: Auto-apply | User-directed` — they're uniformly fix-or-file. The manifest format should degrade gracefully: if `resolution` field is absent, default verb is `fix` (or `file` for findings explicitly marked "file as issue"). Needs confirmation that the resolutions.md format works for both challenge's 4-verb vocabulary and visual-qa's 2-verb reality.
- **Manifest row identity**: should finding rows use `F1 F2 F3` (stable within-session identifiers) or `#1 #2 #3` (matching the Phase 4 display numbering)? Recommendation: match Phase 4's `### 1.` numbering (so users can say "F3" after seeing "### 3." in the rendered findings). But this needs a decision.
- **Re-edit loop limit**: does the "edit and re-present" cycle have an iteration cap (like mine.design's sign-off loop)? Without a cap, a distracted user could loop indefinitely. Recommendation: no cap for now — the single commit gate bounds it in practice.
- **`file` verb execution**: does the manifest's `file` verb invoke `gh-issue create` synchronously during execution, or collect all file requests and batch them at the end? Current findings.md line 50 says "File issues for findings where 'file as issue' was selected, using `gh-issue create`." Recommendation: batch at the end of the manifest execution to keep file verb execution non-interactive.
- **Defaults for User-directed findings**: the manifest default for User-directed should be the recommended option letter (`A`/`B`), not `ask`. This means most user-directed findings don't need an execution-phase prompt — the user already saw the recommendation in the display and could have overridden it at manifest-edit time. Confirms the "most findings are pre-decided" claim in §6. Needs explicit statement in the rule.

## Risks

1. **"Just say go" laziness** — if defaults are good, users will approve the manifest without reading it. This is structurally identical to the current `Accept all?` failure. **Mitigation**: the manifest ENUMERATES every finding on its own line — the user physically sees N rows before approving. This is qualitatively different from a `Accept all?` prompt, which hides the N behind a single choice. Also: the Named Anti-Pattern Catalog explicitly lists "permissive defaults that collapse to 'accept all' in practice" as a failure mode the renderer should avoid (e.g., don't default User-directed findings to `fix` without an option pre-selected).

2. **Free-text parsing brittleness** — "change F4 to file, F7 to skip" needs to be parsed reliably. If the parse is wrong, the user's intent is lost. **Mitigation**: on any parse ambiguity, the skill re-renders the manifest with the attempted change highlighted and asks for confirmation. And the Edit tool call path bypasses parsing entirely for power users. The failure mode is "parse fails → ask again," not "parse succeeds silently wrong."

3. **`rules/common/findings.md` growing past IFScale limits** — adding a Resolution Manifest section + Named Anti-Pattern Catalog could balloon the rule file from 54 lines to 150+. The prior-art brief explicitly notes "IFScale and related research show instruction-following degrades with prompt density." **Mitigation**: the Named Anti-Pattern Catalog is the entire point per the research ("you cannot fix this with more prose rules" AND "anti-pattern catalog is must-have companion"). The density cost is acceptable because the manifest pattern *reduces* runtime prompt density (one AskUserQuestion per `ask` row instead of N-in-one bundled prompts). Net density goes down, not up.

4. **Execution-phase per-finding prompts reintroducing the bug** — for `ask` verbs, we still emit one AskUserQuestion per finding. If the LLM bundles these at the execution phase, we're back to square one. **Mitigation**: the Named Anti-Pattern Catalog enumerates this specific failure mode (Bundling at execution time); the manifest structurally constrains each `ask` row to produce exactly one AskUserQuestion call; the position counter `(N/M)` pattern (from prior-art Pattern 1) grounds each prompt in "this row, not all rows."

5. **Visual-qa/tool-gaps divergence** — if these two skills' gate semantics can't be expressed in the manifest format, they'll continue to use the Skill-Specific Overrides path and the standardization benefit is partial. **Mitigation**: visual-qa and tool-gaps already use skill-specific overrides (lines 284, 178 respectively) — they're not in scope for the manifest flow at all. This is an acceptable partial adoption; both skills have 2-verb (fix/file) or 3-verb (implement/issue/skip) vocabularies and already work without the bundling problem. The manifest flow is for mine.challenge's 4+ verb vocabulary, where bundling is actually a problem.
