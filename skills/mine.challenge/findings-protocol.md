<!-- findings-format-version: 3 -->

# Findings Protocol

Defines the findings file format produced by challenge and consumed by callers
(mine.define, mine.gap-close).

## Findings File Format

The findings file is a markdown file at `<tmpdir>/challenge-results.md`. Each
finding is a top-level section:

```markdown
## Finding N: <title>

**Severity:** CRITICAL | HIGH | MEDIUM | TENSION
**Type:** <type>
**Design-level:** Yes | No
**Resolution:** Auto-apply | User-directed
**Raised-by:** <critic-name>
**status:** pending | applied | overflow | skipped
**overflow:** true | false

**Why-it-matters:** <consequence if left unfixed>

**Evidence:** <file:line, section reference, or quoted text>

**References:** <optional supporting references>

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
| `MEDIUM` | Meaningful but not blocking; subject to cap budgeting |
| `TENSION` | Legitimate competing concerns; deferred unless user resolves |

## Type Taxonomy

`Gap` · `Fragility` · `Scope` · `Structural` · `Assumption`

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

- **CRITICAL and HIGH**: Always shown, no cap
- **MEDIUM**: At most `max(3, CRITICAL_count + HIGH_count)` MEDIUM findings
  are shown; the rest are marked `overflow: true, status: overflow`
- **TENSION**: Shown only when no CRITICAL/HIGH findings exist; otherwise
  overflow

Overflow findings are written to the findings file with `status: overflow` so
callers can inspect them. They are not presented during inline resolution.

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
```

Apply chosen option via Edit tool (or no edit for Skip). Set `status: applied`
or `status: skipped`. Continue to next finding.

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
```

Apply chosen side via Edit tool. Set `status: applied` and append
`**Chosen:** side-a` or `**Chosen:** side-b` to the finding. For Skip, set
`status: skipped`.

## Zero-Findings Case

If synthesis produces no findings, emit: "No findings — the target looks
clean." Do not run a resolution flow.
