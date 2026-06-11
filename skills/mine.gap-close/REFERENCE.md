# Gap Close — Reference

Per-artifact-type checklists, answer-to-artifact conversion rules, and example walkthroughs. Referenced by SKILL.md — do not reference further files from here.

---

## How This Differs From Other Skills

| Skill | What it checks |
|-------|----------------|
| `mine.define` quality validation | Structure: mandatory sections present and non-empty |
| `mine.challenge` pre-flight | Quality of existing content: contradictions, handwaving, vagueness |
| **`mine.gap-close`** | **Content completeness: required information is present, not absent** |

Gap-close targets **missing content**, not flawed content. If the Problem section exists but uses circular reasoning, that's challenge territory. If the Problem section exists but omits the business cost of the problem, that's gap-close territory.

---

## Severity Classes

| Severity | Meaning | Sign-off behavior |
|----------|---------|-------------------|
| **Blocker** | Missing information that prevents implementation or acceptance. The artifact cannot be acted on without it. | Must be filled before sign-off |
| **Should-address** | Missing information that reduces quality or increases risk, but work can proceed | Strongly encouraged before sign-off |
| **Nice-to-have** | Missing information that would strengthen the artifact but is genuinely optional | Skipped in fast-track reviews |

---

## Artifact Type Detection

Before applying a checklist, identify which checklist applies:

| Signal | Artifact type |
|--------|---------------|
| Contains `**Status:** draft` or `**Status:** approved` AND has `## Problem` heading | Design doc |
| Contains `## Key Decisions` OR `## Scope Boundaries` | Brief |
| Contains `## Deliverables` OR first heading starts with `# WP` | Work package |
| None of the above | General-purpose |

When in doubt, ask the user to confirm the artifact type before surveying.

---

## Checklist: Design Doc

Design docs follow the caliper workflow template. Check each item against the content of design.md.

Items complement mine.define's Phase 5 quality validation — the quality validation checks structural correctness (sections present, identifier formats, tech-agnostic boundaries, conditional section rules); these items check that the content within each section is complete. Items that mine.define's interview process consistently produces well (named actors, testable requirements, alternatives with rationale, etc.) are intentionally excluded — this checklist focuses on gaps that mine.define systematically misses.

### Problem / Goals

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-01 | Blocker | Is the business or user cost of not solving this problem quantified or at least characterized? | Problem |
| DD-02 | Blocker | Does each goal have a measurable success metric (number, percentage, threshold, or binary outcome)? | Goals |
| DD-03 | Should-address | Is the scope boundary stated — what this feature does AND does not change? | Goals |

### User Scenarios

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-04 | Should-address | Are there scenarios for the primary happy path AND at least one error/failure path? | User Scenarios |
| DD-05 | Should-address | Do the scenarios cover the entry point (how the user reaches this feature) as well as the core action? | User Scenarios |

### Functional Requirements

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-06 | Blocker | Are requirements free of ambiguous qualifiers like "appropriate", "reasonable", "as needed", "user-friendly"? | Functional Requirements |

### Edge Cases

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-07 | Should-address | Are concurrent or race-condition scenarios identified where the feature touches shared state? | Edge Cases |

### Acceptance Criteria

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-08 | Blocker | Does every Functional Requirement have at least one corresponding acceptance criterion? | Acceptance Criteria |

### Architecture / Alternatives

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-09 | Nice-to-have | Are the trade-offs of the chosen architecture stated (what it optimizes for, what it sacrifices)? | Architecture |

### Failure Modes

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-10 | Should-address | Are at least two operational failure modes identified (e.g., dependency unavailable, data corruption, timeout)? | Edge Cases (preferred) or a dedicated Failure Modes section if one exists |
| DD-11 | Should-address | Is the expected system behavior on failure defined (graceful degradation, error message, fallback)? | Same section as DD-10 |

### Replacement Targets / Migration

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-12 | Blocker | If the feature replaces existing code, does the Replacement Targets section list each pattern being superseded and what replaces it? | Replacement Targets |
| DD-13 | Should-address | If a Migration section is present, does it address what happens to existing data and whether the migration is reversible? | Migration |

### Test Strategy

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-14 | Blocker | Does the Test Strategy identify specific existing test files that will break or need updating (with file paths), or explicitly state none are affected? | Test Strategy > Existing Tests to Adapt |
| DD-15 | Should-address | Does the New Test Coverage subsection map new behaviors to Functional Requirements (FR#N)? | Test Strategy > New Test Coverage |

### Impact

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-16 | Should-address | Does the Impact section identify behavioral invariants — existing behaviors that must not change? | Impact > Behavioral Invariants |

---

## Checklist: Brief

Briefs follow the mine.grill output format: Idea, Key Decisions Made, Open Questions, Scope Boundaries, Risks and Concerns, Codebase Context. Items that mine.grill consistently produces well (clear idea statement, explicit pain point) are excluded.

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| BR-01 | Blocker | Are at least three key decisions recorded — things that were ambiguous and are now pinned down? | Key Decisions Made |
| BR-02 | Should-address | Does each key decision include the reason it was made (not just the decision itself)? | Key Decisions Made |
| BR-03 | Blocker | Are scope boundaries stated in both directions: what is IN and what is OUT or DEFERRED? | Scope Boundaries |
| BR-04 | Should-address | Is the scope boundary specific enough to prevent scope creep? (Not "we won't gold-plate" but "we won't add X") | Scope Boundaries |
| BR-05 | Should-address | Are open questions distinguished from risks? (Open questions = unknown; risks = known uncertainty with potential downside) | Open Questions / Risks |
| BR-06 | Should-address | Does each open question have enough context for someone to research or resolve it independently? | Open Questions |
| BR-07 | Blocker | Are technical risks that could block implementation identified? | Risks and Concerns |
| BR-08 | Should-address | Are the risks accompanied by any mitigation ideas or contingency thinking? | Risks and Concerns |
| BR-09 | Should-address | Is there codebase context — existing patterns, integration points, or constraints — that shapes the approach? | Codebase Context |

---

## Checklist: Task File

Task files define a bounded unit of implementation work within a caliper plan.

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| TF-01 | Blocker | Is the task's deliverable stated as a concrete artifact or observable behavior — not a process? ("Implement X" → "X exists and does Y", not "Work on X") | Summary |
| TF-02 | Blocker | Does the Summary describe what done looks like — observable, not aspirational? | Summary |
| TF-03 | Blocker | Are Prompt instructions specific enough that an executor could follow them without reading anything else? | Prompt |
| TF-04 | Should-address | Are all Prompt instructions mutually exclusive — no two instructions duplicate effort or produce conflicting artifacts? | Prompt |
| TF-05 | Should-address | If this task has dependencies on other tasks, are they listed and accurate? | depends_on |
| TF-06 | Blocker | Is the scope bounded — is there a clear statement of what this task does NOT include? | Summary or Prompt |
| TF-07 | Should-address | Does the Focus section provide concrete domain context (design tokens, API contracts, data model rationale) — not generic guidance? | Focus |
| TF-08 | Should-address | Does the task avoid implementation detail that belongs in a later or sibling task? (No cross-task scope bleed) | Prompt |
| TF-09 | Blocker | Is the task small enough to be completed in one session? (If Prompt instructions exceed ~8 items, split into two tasks) | Prompt |
| TF-10 | Blocker | Does every Verify criterion reference a specific FR or AC identifier? | Verify |

---

## Checklist: General-Purpose

Applies to any document that doesn't match the above types — research docs, ADRs, specs, playbooks, etc.

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| GP-01 | Blocker | Are there any `TBD`, `TODO`, `FIXME`, or `[placeholder]` markers that indicate incomplete content? | Entire document |
| GP-02 | Should-address | Is the scope bounded — what topics are in and out of scope for this document? | Introduction or Scope section |
| GP-03 | Should-address | Are claims and recommendations verifiable — either cited to evidence or stated as assumptions? | Any claims sections |
| GP-04 | Should-address | Is ambiguous language ("should", "may", "some", "often", "generally") replaced with specific language where precision matters? | All sections |

---

## Answer-to-Artifact Conversion Rules

When the user answers a gap question, convert the answer into artifact content using the appropriate pattern below. Apply the edit to the artifact with the Edit tool.

### Pattern 1: Acceptance Criteria — Testable Statement

**Use when:** The answer provides conditions and expected outcomes for a requirement.

**Format:** Match the artifact's existing AC style. If no style exists, use concise declarative statements with a clear precondition, action, and outcome. Given/When/Then is one valid format but not required.

**Multiple criteria:** add each as a separate item under the section, matching the existing style (bullets, numbered items, or bare blocks).

**Edit tool example** (the single worked example for all patterns — the others follow the same `old_string`/`new_string` mechanics):

```
old_string: "## Acceptance Criteria\n\n[No criteria defined yet.]"
new_string: "## Acceptance Criteria\n\n- When a user submits a form with a missing required field, an inline error message appears adjacent to the field describing what is missing."
```

---

### Pattern 2: Architecture / Decision — Prose with Rationale

**Use when:** The answer explains a design choice, technology selection, or structural decision.

**Template:**

```
[Decision or approach]. [Why this was chosen]. [What it trades off or sacrifices compared to the alternative].
```

For an Alternatives Considered section, give each rejected option a bold label, the reason it was rejected, and what it traded off.

---

### Pattern 3: UI State — Trigger / Visual / Behavior / Exit

**Use when:** The answer describes a UI state (loading, empty, error, success, disabled, etc.) that needs a structured spec.

**Template:**

```
**[State name]**
- Trigger: [what causes this state]
- Visual: [what the user sees]
- Behavior: [what the user can do, what is disabled]
- Exit: [what ends this state]
```

---

### Pattern 4: Edge Case — Bullet Point

**Use when:** The answer identifies a specific edge case scenario that needs handling.

**Template:**

```
- [Condition that triggers the edge case]: [expected system behavior]
```

Append to an existing list or populate an empty section, matching the section's bullet style.

---

### Pattern 5: Default — Verbatim in Existing Style

**Use when:** None of the above patterns apply, or the target section has a clear existing style to match.

**Rules:**
1. Read the existing content in the target section to understand its style (prose, bullets, numbered list, table).
2. Write the answer in that same style — don't introduce a new format.
3. Insert at the natural end of the section, before the next heading.
4. Preserve existing whitespace conventions (blank line before headings, single-line bullets, etc.).

---

## Survey Output Format

Each checklist item is evaluated as one of:
- **PASS** — the required content is present and complete
- **GAP** — the content is missing or incomplete (severity from the checklist applies)
- **N/A** — the checklist item does not apply to this artifact (e.g., DD-07 race conditions for a feature with no shared state)

Surveys must be complete — evaluate every checklist item and record a result. Do not skip items just because they appear obviously satisfied. Sample output:

```
DD-01  GAP    [Blocker] No business cost of the limitation stated — why does this matter?
DD-02  PASS   Goals: "Bulk export supports up to 100,000 records within 60 seconds"
DD-06  GAP    [Blocker] Requirement "handle large files gracefully" — "gracefully" is unacceptably vague
DD-07  N/A    Feature does not touch shared state (export is per-user, no concurrent writes)
DD-08  GAP    [Blocker] Requirements 2 and 3 have no corresponding acceptance criteria
```

Triage GAPs by severity, ask one gap question per Blocker, convert each answer to artifact content via the patterns above, then present the sign-off gate ("Approve" / "Run full challenge" / "Save and stop").
