<!-- findings-format-version: 3 -->

# Findings Protocol

Defines the findings file format used by challenge and other tools that
produce, consume, or reference findings, including structured callers such as
mine.define and mine.audit.

## Findings File Format

The per-finding format below (sections, fields, status values) is the shared
contract. The file path, title, and header fields are producer-specific — e.g.,
challenge writes `<tmpdir>/challenge-results.md` with `# Challenge Findings`,
while mine.audit writes `<tmpdir>/audit-results.md` with `# Audit Findings`.

The canonical challenge header block:

```markdown
# Challenge Findings

**Format-version:** 3
**Target:** <file path or description>
**Critics:** <comma-separated critic names>
**Likely-invalid:** <count>
```

Each finding is a top-level section:

```markdown
## Finding N: <title>

**Severity:** CRITICAL | HIGH | MEDIUM | TENSION
**Type:** <type>
**Design-level:** Yes | No
**Resolution:** Auto-apply | User-directed
**Raised-by:** <critic-name>
**status:** pending | applied | overflow | skipped  <!-- lowercase: runtime-written by synthesis/resolution, not by critics -->
**overflow:** true | false  <!-- lowercase: runtime-written -->

**Why-it-matters:** <consequence if left unfixed>

**Evidence:** <file:line, section reference, quoted text, or URL>

**Design-challenge:** <what this reveals about the design's assumptions>

<!-- For Auto-apply findings: -->
**Better-approach:** <specific change to apply>

<!-- For User-directed findings: -->
**Options:**
- **A** *(recommended)*: <first option>
- **B**: <second option>

**Recommendation:** <which option and why>

<!-- For TENSION findings: -->
**Side-a:** <argument for side A>
**Side-b:** <argument for side B>
**Deciding-factor:** <question or data point that resolves the tension>
**Chosen:** side-a | side-b   <!-- set during inline resolution; absent until resolved -->
```

Finding IDs are sequential starting from 1. `## Finding N:` headings must
match 1:1 with findings — no gaps.

## Severity Taxonomy

| Severity | Meaning |
|---|---|
| `CRITICAL` | Breaks a core requirement or contract; must be user-directed |
| `HIGH` | Significant gap or fragility; shown to user |
| `MEDIUM` | Meaningful but not blocking; always shown |
| `TENSION` | Legitimate competing concerns; deferred unless user resolves |

## Type Taxonomy

`Structural` · `Approach-now` · `Approach-later` · `Fragility` · `Gap`

## Status and Overflow Fields

The synthesis subagent writes these fields before challenge returns; the inline
resolution phase updates `status` as findings are resolved.

**`status`** values:

| Value | Meaning |
|---|---|
| `pending` | In scope; awaits resolution |
| `applied` | Resolution executed (auto-apply ran, or user chose an option) |
| `overflow` | Exceeded the cap; in file but not presented |
| `skipped` | User explicitly skipped during resolution |

**`overflow`** values: `false` = within cap (presented normally); `true` = exceeded cap (recorded for reference only).

## Resolution Classification

The synthesis subagent classifies each finding as `Auto-apply` or
`User-directed` using these criteria:

**Auto-apply** when ALL of the following hold:
- Fix is localized (one section, one field, one line)
- Critics agree on the fix (no meaningful dissent)
- Severity is not CRITICAL
- Fix introduces no behavior change to the design's intent

**User-directed** when ANY of the following hold:
- Fix requires a judgment call between competing approaches
- Severity is CRITICAL
- Fix touches multiple sections or has design-level implications
- Critics disagreed on the resolution

TENSION findings always classify as User-directed.

## Finding Cap

Findings are capped before presentation to prevent overwhelming the user:

- If `cap=0`: all findings are auto-applied or overflow — pure automation mode
- **CRITICAL, HIGH, and MEDIUM**: Always shown, no cap (except `cap=0`)
- **TENSION**: Shown only when no CRITICAL/HIGH findings exist; otherwise
  overflow

Overflow findings are written to the findings file with `status: overflow` so
callers can inspect them. They are not presented during inline resolution.

## Validity Assessment

After synthesizing findings, assess whether each finding holds up. Findings
are valid by default. To flag a finding as likely invalid, the synthesizer
must provide concrete evidence: what the finding claims, what the code
actually does, and why they conflict. If the evidence trail cannot be
articulated, the finding remains in the main findings list.

Likely-invalid findings are removed from the main `## Finding N:` sequence
and placed in a `## Likely Invalid` section at the end of the findings file.
They do not consume finding numbers — the main sequence renumbers to stay
contiguous.

### Likely Invalid section format

Each likely-invalid entry uses a `LI-N` identifier (sequential, separate from
the main finding numbers):

    ## Likely Invalid

    ### LI-1: <original finding title>
    **Original-severity:** <severity from the critic>
    **Raised-by:** <critic or reviewer name>
    **Claimed:** <what the finding asserts>
    **Actually:** <what the code actually does, with file:line references>
    **Why-invalid:** <the specific conflict — trace the code path, show the contradiction>

The three evidence fields (`Claimed`, `Actually`, `Why-invalid`) are
mandatory — if any are missing, the synthesizer has not met the evidence bar
and the finding must stay in the main list.

## Inline Resolution Flow

After synthesis completes and the findings file is written, challenge resolves
findings in cap order.

**Auto-apply** (`Resolution: Auto-apply`, `status: pending`): Apply
`better-approach` via Edit tool silently. Set `status: applied`. No prompt.

**User-directed** (`Resolution: User-directed`, `status: pending`): Emit one
AskUserQuestion per finding — do not batch:

```
AskUserQuestion:
  question: "Finding N/{total}: <title> (<severity>)"
  header: "<raised-by>"
  options:
    - label: "<Option A text> (Recommended)"
      description: "<why-it-matters>"
    - label: "<Option B text>"
      description: ""
    - label: "Skip — defer to later"
      description: "Record this finding without acting on it"
    - label: "File as issue"
      description: "Create a GitHub issue for this finding"
```

Apply chosen option via Edit tool. Set `status: applied` for options,
`status: skipped` for Skip, or `status: skipped` + create issue via
`gh-issue create` for File as issue. Continue to next finding.

**TENSION findings** (`Resolution: User-directed`, `Severity: TENSION`):

```
AskUserQuestion:
  question: "Finding N/{total}: <title> (TENSION) — <deciding-factor>"
  header: "<raised-by>"
  options:
    - label: "Side A: <side-a summary>"
      description: "<side-a detail>"
    - label: "Side B: <side-b summary>"
      description: "<side-b detail>"
    - label: "Skip — defer to later"
      description: "Record this finding without acting on it"
    - label: "File as issue"
      description: "Create a GitHub issue for this finding"
```

Apply chosen side via Edit tool. Set `status: applied` and append
`**Chosen:** side-a` or `**Chosen:** side-b` to the finding. For Skip, set
`status: skipped`.

**After all main findings are resolved**, if the findings file contains a
`## Likely Invalid` section with entries, present them:

> **Likely Invalid (N flagged)** — these findings were flagged as likely
> invalid based on code evidence. Review below; re-run with the finding
> restored if any were wrongly excluded.

List each LI entry with its title, original severity, and a one-line summary
of the `Why-invalid` field. Do not prompt for action — this is informational.

## Zero-Findings Case

If synthesis produces no findings, emit: "No findings — the target looks
clean." Do not run a resolution flow.
