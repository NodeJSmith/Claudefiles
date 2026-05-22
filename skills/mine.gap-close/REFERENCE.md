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
| DD-03 | Should-address | Are non-goals listed when there is a plausible adjacent feature that is being intentionally excluded? | Goals |
| DD-04 | Should-address | Is the scope boundary stated — what this feature does AND does not change? | Goals |

### User Scenarios

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-05 | Should-address | Are there scenarios for the primary happy path AND at least one error/failure path? | User Scenarios |
| DD-06 | Should-address | Do the scenarios cover the entry point (how the user reaches this feature) as well as the core action? | User Scenarios |

### Functional Requirements

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-07 | Blocker | Are requirements free of ambiguous qualifiers like "appropriate", "reasonable", "as needed", "user-friendly"? | Functional Requirements |

### Edge Cases

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-08 | Should-address | Are concurrent or race-condition scenarios identified where the feature touches shared state? | Edge Cases |

### Acceptance Criteria

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-09 | Blocker | Does every Functional Requirement have at least one corresponding acceptance criterion? | Acceptance Criteria |

### Architecture / Alternatives

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-10 | Nice-to-have | Are the trade-offs of the chosen architecture stated (what it optimizes for, what it sacrifices)? | Architecture |

### Failure Modes

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-11 | Should-address | Are at least two operational failure modes identified (e.g., dependency unavailable, data corruption, timeout)? | Edge Cases (preferred) or a dedicated Failure Modes section if one exists |
| DD-12 | Should-address | Is the expected system behavior on failure defined (graceful degradation, error message, fallback)? | Same section as DD-11 |

### Replacement Targets / Migration

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-13 | Blocker | If the feature replaces existing code, does the Replacement Targets section list each pattern being superseded and what replaces it? | Replacement Targets |
| DD-14 | Should-address | If a Migration section is present, does it address what happens to existing data and whether the migration is reversible? | Migration |

### Test Strategy

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-15 | Blocker | Does the Test Strategy identify specific existing test files that will break or need updating (with file paths), or explicitly state none are affected? | Test Strategy > Existing Tests to Adapt |
| DD-16 | Should-address | Does the New Test Coverage subsection map new behaviors to Functional Requirements (FR#N)? | Test Strategy > New Test Coverage |

### Impact

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-17 | Should-address | Does the Impact section identify behavioral invariants — existing behaviors that must not change? | Impact > Behavioral Invariants |

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

**Edit tool example:**

```
old_string: "## Acceptance Criteria\n\n[No criteria defined yet.]"
new_string: "## Acceptance Criteria\n\n- When a user submits a form with a missing required field, an inline error message appears adjacent to the field describing what is missing."
```

**Multiple criteria:** Add each as a separate item under the section, matching the existing style (bullets, numbered items, or bare blocks).

```
old_string: "## Acceptance Criteria\n\n- The system validates input on submission."
new_string: "## Acceptance Criteria\n\n- The system validates input on submission.\n- When a logged-in user with read-only permissions visits the admin dashboard, no delete button is shown and no deletion can occur."
```

---

### Pattern 2: Architecture / Decision — Prose with Rationale

**Use when:** The answer explains a design choice, technology selection, or structural decision.

**Template:**

```
[Decision or approach]. [Why this was chosen]. [What it trades off or sacrifices compared to the alternative].
```

**Edit tool example:**

```
old_string: "## Architecture\n\nThe service uses a queue-based approach."
new_string: "## Architecture\n\nThe service uses a queue-based approach. A queue decouples ingestion from processing, allowing the pipeline to absorb burst loads without dropping events. The trade-off is added operational complexity (a queue service must be provisioned and monitored) compared to direct synchronous processing, which was rejected because it blocks the ingestion path under load."
```

**Alternatives section example:**

```
old_string: "## Alternatives Considered\n\n_None documented._"
new_string: "## Alternatives Considered\n\n**Synchronous processing**: Rejected because it blocks the ingestion path under sustained load, causing upstream timeouts during peak traffic periods.\n\n**Batch file ingestion**: Considered for simplicity; rejected because it introduces 15-minute latency that violates the real-time SLA stated in Goals."
```

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

**Edit tool example:**

```
old_string: "## Edge Cases\n\n- Empty results state not defined."
new_string: "## Edge Cases\n\n**Empty results state**\n- Trigger: Search returns zero matching records\n- Visual: Illustration with caption \"No results found for '[query]'\" and a secondary line \"Try adjusting your search terms\"\n- Behavior: Search input remains active; filters remain visible; no table or list is rendered\n- Exit: User modifies the query and resubmits, or clears the search"
```

---

### Pattern 4: Edge Case — Bullet Point

**Use when:** The answer identifies a specific edge case scenario that needs handling.

**Template:**

```
- [Condition that triggers the edge case]: [expected system behavior]
```

**Edit tool example — appending to an existing list:**

```
old_string: "- Zero-length input: rejected with validation error"
new_string: "- Zero-length input: rejected with validation error\n- Input exceeding 10,000 characters: truncated to limit with a warning displayed; excess content is not silently discarded\n- Input containing only whitespace: treated as zero-length input after trimming"
```

**Edit tool example — populating an empty section:**

```
old_string: "## Edge Cases\n\n_None identified._"
new_string: "## Edge Cases\n\n- Concurrent edits by two users to the same record: last-write wins; a conflict warning is shown to the second writer naming the first writer and the timestamp of their change\n- Session expires mid-flow: form state is preserved in localStorage; user is prompted to re-authenticate, then returned to the same step"
```

---

### Pattern 5: Default — Verbatim in Existing Style

**Use when:** None of the above patterns apply, or the target section has a clear existing style to match.

**Rules:**
1. Read the existing content in the target section to understand its style (prose, bullets, numbered list, table).
2. Write the answer in that same style — don't introduce a new format.
3. Insert at the natural end of the section, before the next heading.
4. Preserve existing whitespace conventions (blank line before headings, single-line bullets, etc.).

**Edit tool example — appending to a prose section:**

```
old_string: "## Problem\n\nUsers frequently lose their place when navigating between sections of a long form.\n\n## Goals"
new_string: "## Problem\n\nUsers frequently lose their place when navigating between sections of a long form. Internally, support tickets for \"where did my data go\" account for 23% of form-related tickets last quarter, suggesting the problem is both common and frustrating enough to prompt contact.\n\n## Goals"
```

**Edit tool example — appending to a bullet list:**

```
old_string: "## Dependencies\n\n- Auth service: user identity and session tokens"
new_string: "## Dependencies\n\n- Auth service: user identity and session tokens\n- Notification service: sends confirmation emails on successful submission\n- Feature-flag service: gates the new form behind the `new-form-v2` flag during rollout"
```

---

## Example Walkthrough

### Scenario

A design doc has been written for a new "Bulk Export" feature. Mine.gap-close is invoked with the design.md path.

### Survey Result Codes

Each checklist item is evaluated as one of:
- **PASS** — the required content is present and complete
- **GAP** — the content is missing or incomplete (severity from the checklist applies)
- **N/A** — the checklist item does not apply to this artifact (e.g., DD-08 race conditions for a feature with no shared state)

Surveys must be complete — evaluate every checklist item and record a result as **PASS**, **GAP**, or **N/A**. Do not skip items just because they appear obviously satisfied. For readability, the walkthrough below shows only a condensed subset of the full survey output.

### Step 1: Survey (scanning the artifact)

The skill reads the design doc and evaluates the DD-* checklist item by item. The excerpt below shows representative results from the full survey:

```
DD-01  GAP    [Blocker] No business cost of the limitation stated — why does this matter?
DD-02  PASS   Goals: "Bulk export supports up to 100,000 records within 60 seconds"
DD-03  PASS   Non-goals listed: "We will not support scheduled exports in this version"
DD-04  PASS   Scope boundary clear
DD-05  GAP    [Should-address] No error/failure scenario — what happens when an export fails?
DD-06  PASS   Entry point covered: "clicks Export All from the filtered record list"
DD-07  GAP    [Blocker] Requirement "Export should handle large files gracefully" — "gracefully" is unacceptably vague
DD-08  N/A    Feature does not touch shared state (export is per-user, no concurrent writes)
DD-09  GAP    [Blocker] Requirements 2 and 3 have no corresponding acceptance criteria
DD-10  PASS   Trade-offs stated: "queue complexity vs synchronous simplicity"
DD-11  GAP    [Should-address] No operational failure modes identified
DD-12  GAP    [Should-address] No failure behavior defined
```

### Step 2: Triage

From the survey, blockers are:
- DD-01 (missing business cost)
- DD-07 (vague requirement)
- DD-09 (two requirements have no acceptance criteria)

Should-address gaps:
- DD-05 (no error/failure scenario)
- DD-11 (no failure modes)
- DD-12 (no failure behavior)

### Step 3: Gap Questions

**Question 1** (targets DD-01):

> "The Problem section describes the limitation but not its cost. What happens to users because of the 100-record export cap? How often does this come up?"

**Answer:** "Data analysts hit this weekly when preparing quarterly reports. They work around it by exporting in batches and stitching CSVs manually, which takes 30-45 minutes per report."

**Converted to artifact** (Pattern 5 — matching existing prose style):

```
old_string: "## Problem\n\nUsers cannot export more than 100 records at a time."
new_string: "## Problem\n\nUsers cannot export more than 100 records at a time. Data analysts hit this weekly when preparing quarterly reports, working around it by exporting in batches and stitching CSVs manually — 30-45 minutes per report."
```

**Question 2** (targets DD-07):

> "Requirement: 'Export should handle large files gracefully.' What does 'gracefully' mean in practice? What should happen when an export reaches the 100,000-record limit? What if it times out?"

**Answer:** "At the limit, the export is capped and the user sees a message saying 'Export limited to 100,000 records — your results have been truncated.' On timeout, the partial file is discarded and the user gets an error with a retry link."

**Converted to artifact** (Pattern 1 for acceptance criteria + Pattern 4 for edge cases):

Acceptance criteria (Pattern 1):
```
old_string: "- Export should handle large files gracefully"
new_string: "- Export is capped at 100,000 records per request\n- When a user requests an export exceeding 100,000 records, the delivered file contains exactly 100,000 records and a notice reads \"Export limited to 100,000 records — results were truncated\"\n- When a user requests an export and generation times out, no partial file is delivered; the user sees an error with a \"Retry export\" link"
```

Edge cases (Pattern 4):
```
old_string: "## Edge Cases\n\n- Zero-length export: return empty file with headers only"
new_string: "## Edge Cases\n\n- Zero-length export: return empty file with headers only\n- Export exceeding 100,000 records: capped at limit with truncation notice shown to user\n- Export timeout mid-generation: partial file discarded, user sees error with retry link"
```

**Question 3** (targets DD-09):

> "Requirements 2 and 3 have no acceptance criteria. What observable outcome would tell a tester that requirement 2 (format selection) passes? And requirement 3 (progress indication)?"

**Answer:** "For format selection: user picks CSV or JSON from a dropdown, downloaded file matches the chosen format. For progress: a progress bar appears within 2 seconds of clicking Export, updates at least every 5 seconds, and disappears on completion."

**Converted to artifact** (Pattern 1):

```
old_string: "- When a user requests an export, the system begins processing within 5 seconds."
new_string: "- When a user requests an export, the system begins processing within 5 seconds.\n- When a user selects CSV or JSON from the format dropdown and clicks Export, the downloaded file is in the selected format.\n- A progress bar appears within 2 seconds of clicking Export, updates at least every 5 seconds, and disappears when the export completes or fails."
```

### Step 4: Sign-off

After filling all Blocker gaps, the skill confirms: "All Blocker gaps resolved. 3 Should-address items remaining: DD-05 (error scenario), DD-11 (failure modes), DD-12 (failure behavior)."

Presents sign-off gate:
- "Approve" — update status field
- "Run full challenge" — invoke /mine.challenge for deeper critique
- "Save and stop" — leave as-is
