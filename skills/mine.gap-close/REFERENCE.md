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

Items complement mine.define's 12-item quality validation — the quality validation checks that sections exist and are non-empty; these items check that the content within each section is complete.

### Problem / Goals

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-01 | Blocker | Is the problem stated in terms of user or business impact — not just a technical observation? ("Users cannot X" not "The system lacks Y") | Problem |
| DD-02 | Blocker | Is the business or user cost of not solving this problem quantified or at least characterized? | Problem |
| DD-03 | Blocker | Does each goal have a measurable success metric (number, percentage, threshold, or binary outcome)? | Goals |
| DD-04 | Should-address | Are non-goals listed when there is a plausible adjacent feature that is being intentionally excluded? | Goals |
| DD-05 | Should-address | Is the scope boundary stated — what this feature does AND does not change? | Goals |

### User Scenarios

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-06 | Blocker | Does each scenario name a specific actor (not "the user" generically) and describe a concrete task flow with steps? | User Scenarios |
| DD-07 | Should-address | Are there scenarios for the primary happy path AND at least one error/failure path? | User Scenarios |
| DD-08 | Should-address | Do the scenarios cover the entry point (how the user reaches this feature) as well as the core action? | User Scenarios |
| DD-09 | Nice-to-have | Is there a scenario for a new user encountering this feature for the first time? | User Scenarios |

### Functional Requirements

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-10 | Blocker | Is every requirement independently testable — can a QA engineer determine pass/fail without additional clarification? | Functional Requirements |
| DD-11 | Blocker | Are requirements free of ambiguous qualifiers like "appropriate", "reasonable", "as needed", "user-friendly"? | Functional Requirements |
| DD-12 | Should-address | Does each requirement state what the system does (behavior) not what the system is (property)? | Functional Requirements |
| DD-13 | Should-address | Are all requirements traceable to a stated goal? (No orphan requirements that don't serve a stated goal) | Functional Requirements |

### Edge Cases

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-14 | Blocker | Are boundary conditions covered for all numeric inputs, list sizes, or time-based behaviors? | Edge Cases |
| DD-15 | Should-address | Are concurrent or race-condition scenarios identified where the feature touches shared state? | Edge Cases |
| DD-16 | Should-address | Is the behavior defined for the empty/null case (empty list, no results, missing optional field)? | Edge Cases |
| DD-17 | Nice-to-have | Are permission-boundary edge cases covered (user with insufficient access, partial access)? | Edge Cases |

### Acceptance Criteria

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-18 | Blocker | Is each acceptance criterion specific and testable — with a clear precondition, action, and observable outcome? | Acceptance Criteria |
| DD-19 | Blocker | Does every Functional Requirement have at least one corresponding acceptance criterion? | Acceptance Criteria |

### Architecture / Alternatives

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-20 | Should-address | Does the architecture section explain WHY the chosen approach was selected, not just WHAT was chosen? | Architecture |
| DD-21 | Should-address | Is at least one alternative approach documented with the reason it was not chosen? | Alternatives |
| DD-22 | Nice-to-have | Are the trade-offs of the chosen architecture stated (what it optimizes for, what it sacrifices)? | Architecture |

### Failure Modes / Security

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-23 | Should-address | Are at least two operational failure modes identified (e.g., dependency unavailable, data corruption, timeout)? | Edge Cases (preferred) or a dedicated Failure Modes section if one exists |
| DD-24 | Should-address | Is the expected system behavior on failure defined (graceful degradation, error message, fallback)? | Same section as DD-23 |
| DD-25 | Blocker | If the feature touches authentication, authorization, or user data: are access control rules explicitly stated? | Security/Access |

### Dependencies / Test Strategy / Open Questions

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| DD-26 | Blocker | Are all external dependencies identified (services, APIs, data sources this feature consumes or modifies)? | Dependencies |
| DD-27 | Should-address | Is the test strategy concrete — naming what will be unit-tested, integration-tested, and E2E-tested? | Test Strategy |
| DD-28 | Blocker | Is the Open Questions section empty OR does each entry have an owner and a target-resolution date? | Open Questions |

---

## Checklist: Brief

Briefs follow the mine.grill output format: Idea, Key Decisions Made, Open Questions, Scope Boundaries, Risks and Concerns, Codebase Context.

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| BR-01 | Blocker | Is the core idea stated in one or two sentences that someone unfamiliar with the project can understand? | Idea |
| BR-02 | Blocker | Is the problem or pain point explicitly named (not implied)? | Idea |
| BR-03 | Blocker | Are at least three key decisions recorded — things that were ambiguous and are now pinned down? | Key Decisions Made |
| BR-04 | Should-address | Does each key decision include the reason it was made (not just the decision itself)? | Key Decisions Made |
| BR-05 | Blocker | Are scope boundaries stated in both directions: what is IN and what is OUT or DEFERRED? | Scope Boundaries |
| BR-06 | Should-address | Is the scope boundary specific enough to prevent scope creep? (Not "we won't gold-plate" but "we won't add X") | Scope Boundaries |
| BR-07 | Should-address | Are open questions distinguished from risks? (Open questions = unknown; risks = known uncertainty with potential downside) | Open Questions / Risks |
| BR-08 | Should-address | Does each open question have enough context for someone to research or resolve it independently? | Open Questions |
| BR-09 | Blocker | Are technical risks that could block implementation identified? | Risks and Concerns |
| BR-10 | Should-address | Are the risks accompanied by any mitigation ideas or contingency thinking? | Risks and Concerns |
| BR-11 | Should-address | Is there codebase context — existing patterns, integration points, or constraints — that shapes the approach? | Codebase Context |
| BR-12 | Nice-to-have | Does the codebase context section cite specific files, modules, or patterns found during exploration? | Codebase Context |

---

## Checklist: Work Package

Work packages define a bounded unit of implementation work within a caliper plan.

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| WP-01 | Blocker | Is the WP's deliverable stated as a concrete artifact or observable behavior — not a process? ("Implement X" → "X exists and does Y", not "Work on X") | Objectives & Success Criteria |
| WP-02 | Blocker | Does the success criterion specify what done looks like — observable, not aspirational? | Objectives & Success Criteria |
| WP-03 | Blocker | Are subtasks specific enough that a developer could pick one up without reading anything else? | Subtasks |
| WP-04 | Should-address | Are all subtasks mutually exclusive — no two subtasks duplicate effort or produce conflicting artifacts? | Subtasks |
| WP-05 | Should-address | If this WP has dependencies on other WPs, are they listed and accurate? | depends_on |
| WP-06 | Blocker | Is the scope bounded — is there a clear statement of what this WP does NOT include? | Objectives or Subtasks |
| WP-07 | Should-address | Is the test strategy concrete: what will be tested, at what level (unit/integration/E2E), and what the test command is? | Test Strategy |
| WP-08 | Should-address | Does the WP avoid implementation detail that belongs in a later or sibling WP? (No cross-WP scope bleed) | Subtasks |
| WP-09 | Blocker | Is the WP small enough to be completed in one session? (If subtasks exceed ~8 items, split into two WPs) | Subtasks |
| WP-10 | Nice-to-have | Are implementation notes or design hints included to reduce ramp-up time? | Implementer instructions or subtasks |

---

## Checklist: General-Purpose

Applies to any document that doesn't match the above types — research docs, ADRs, specs, playbooks, etc.

| ID | Severity | Gap question | Target section |
|----|----------|-------------|----------------|
| GP-01 | Blocker | Does the document have a clearly stated purpose — what question does it answer or what decision does it inform? | Any introduction or header section |
| GP-02 | Blocker | Are there any `TBD`, `TODO`, `FIXME`, or `[placeholder]` markers that indicate incomplete content? | Entire document |
| GP-03 | Blocker | Do all sections contain content — no heading-only sections with no body? | All sections |
| GP-04 | Should-address | Is the scope bounded — what topics are in and out of scope for this document? | Introduction or Scope section |
| GP-05 | Should-address | Are claims and recommendations verifiable — either cited to evidence or stated as assumptions? | Any claims sections |
| GP-06 | Should-address | Is ambiguous language ("should", "may", "some", "often", "generally") replaced with specific language where precision matters? | All sections |
| GP-07 | Should-address | Does the document state who it is written for — the intended reader? | Introduction or header |
| GP-08 | Nice-to-have | Are key terms defined on first use, or is there a glossary section for jargon-heavy content? | Introduction or Glossary |

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
- **N/A** — the checklist item does not apply to this artifact (e.g., DD-25 security items for a feature that doesn't touch auth)

Surveys must be complete — evaluate every checklist item and record a result as **PASS**, **GAP**, or **N/A**. Do not skip items just because they appear obviously satisfied. For readability, the walkthrough below shows only a condensed subset of the full survey output.

### Step 1: Survey (scanning the artifact)

The skill reads the design doc and evaluates the DD-* checklist item by item. The excerpt below shows representative results from the full survey:

```
DD-01  PASS   Problem states "Users cannot export more than 100 records at a time"
DD-02  GAP    No business cost of the limitation stated — why does this matter?
DD-03  PASS   Goals: "Bulk export supports up to 100,000 records within 60 seconds"
DD-04  PASS   Non-goals listed: "We will not support scheduled exports in this version"
DD-06  GAP    User scenario actor is "the user" — no specific persona named; task flow has no numbered steps
DD-10  GAP    Requirement "Export should handle large files gracefully" — "gracefully" is unacceptably vague
DD-18  GAP    Acceptance criterion "Export works for all valid inputs" is vague — no precondition, action, or observable outcome
DD-19  GAP    Requirements 2 and 3 have no corresponding acceptance criteria
DD-21  PASS   One alternative documented: "Streaming vs. batch" with rationale
DD-25  N/A    Feature does not touch auth (export of user's own data only, confirmed by Goals)
DD-28  GAP    Open Questions item 2 has no owner or target-resolution date
```

### Step 2: Triage

From the survey, blockers are:
- DD-06 (no concrete actor or task flow)
- DD-10 (vague requirement)
- DD-18 (acceptance criterion is vague and untestable)
- DD-19 (two requirements have no acceptance criteria)
- DD-28 (open question item 2 missing resolution date)

Should-address gaps:
- DD-02 (missing business cost)

### Step 3: Gap Questions

**Question 1** (targets DD-06):

> "The User Scenarios section uses 'the user' generically. Who specifically uses bulk export? Walk me through what they are doing just before they reach this feature, and list the steps they take."

**Answer:** "A data analyst in an enterprise account is preparing a quarterly report. They filter the record list by date range and account type, then click 'Export All'. They wait for a download link, then open the file in Excel."

**Converted to artifact** (Pattern 5 — matching existing scenario style):

```
old_string: "## User Scenarios\n\n**Bulk export**: The user exports a large set of records."
new_string: "## User Scenarios\n\n**Bulk export (data analyst, quarterly reporting)**\n1. Data analyst filters the record list by date range and account type\n2. Analyst clicks \"Export All\" — a progress indicator appears\n3. When processing completes, a download link appears in a notification\n4. Analyst clicks the link and receives a CSV file, which they open in Excel"
```

**Question 2** (targets DD-10):

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

**Question 3** (targets DD-28):

> "Open question item 2 reads 'Should we support XLSX as well as CSV?' but has no owner or target date. Who should resolve this, and when?"

**Answer:** "Product owner (Sam) will decide by end of month."

**Converted to artifact** (Pattern 5 — matching open question style):

```
old_string: "2. Should we support XLSX as well as CSV?"
new_string: "2. Should we support XLSX as well as CSV? (Owner: Sam/Product; target: end of month)"
```

### Step 4: Sign-off

After filling all Blocker gaps, the skill confirms: "All Blocker gaps resolved. 1 Should-address item remaining: DD-02 (business cost)."

Presents sign-off gate:
- "Approve" — update status field
- "Run full challenge" — invoke /mine.challenge for deeper critique
- "Save and stop" — leave as-is
