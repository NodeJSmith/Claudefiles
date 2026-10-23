<!-- findings-format-version: 4 -->

# Findings Protocol

Defines the findings file format used by challenge and other tools that
produce, consume, or reference findings.

## Findings File Format

The per-finding format below (sections, fields, status values) is the shared
contract. The file path, title, and header fields are producer-specific — e.g.,
challenge writes `<tmpdir>/challenge-results.md` with `# Challenge Findings`,
while mine-audit writes `<tmpdir>/audit-results.md` with `# Audit Findings`.

The canonical challenge header block:

```markdown
# Challenge Findings

**Format-version:** 4
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
**Likelihood:** routine | plausible | rare
**Classification:** Auto-apply | User-directed
**Raised-by:** <critic-name>
**visibility:** presented | likely-invalid  <!-- lowercase: runtime-written by synthesis, never changes -->
**disposition:** pending | applied | accepted | skipped | filed  <!-- lowercase: runtime-written by synthesis/resolution; omit this line entirely for likely-invalid findings, which are NULL -->

**Why-it-matters:** <consequence if left unfixed>

**When-it-bites:** <the concrete trigger and how often it happens for this project>

**Evidence:** <file:line, section reference, quoted text, or URL>

**Design-challenge:** <what this reveals about the design's assumptions>

<!-- For Auto-apply findings: -->
**Better-approach:** <specific change to apply>

<!-- For User-directed findings: -->
**Deciding-factor:** <what the recommendation optimizes>

**Criteria:**
| | A | B |
|---|---|---|
| <criterion> | <how A fares> | <how B fares> |

**Options:**
- **A** *(recommended)*: <first option>
- **B**: <second option>

**Recommendation:** <which option and why>
**Pick-instead-if:** B: <condition under which B is the right call>

<!-- For TENSION findings: -->
**Side-a:** <argument for side A>
**Side-b:** <argument for side B>
**Deciding-factor:** <question or data point that resolves the tension>

**Criteria:**
| | Side A | Side B |
|---|---|---|
| <criterion> | <how side A fares> | <how side B fares> |

**Pick-instead-if:** Side A: <condition>. Side B: <condition>.
**Chosen:** side-a | side-b   <!-- set during inline resolution; absent until resolved -->
```

Finding IDs are sequential starting from 1. `## Finding N:` headings must
match 1:1 with findings — no gaps.

`**Likelihood:**` and `**When-it-bites:**` come from challenge synthesis
(`synthesis-procedure.md` step 3). Other producers may omit them; a finding
without `**Likelihood:**` is resolved as if it were not `rare`.

`**Deciding-factor:**`, `**Criteria:**`, and `**Pick-instead-if:**` follow
`${CLAUDE_CONFIG_DIR:-~/.claude}/references/common/presenting-decisions.md`.
They are presentation fields, like `**Evidence:**`: synthesis fills them in
before choosing the recommendation, and they are not written to the review log.

## Convergence Findings

When one change to a mechanism would make several findings' local fixes
unnecessary, synthesis adds a convergence finding (`synthesis-procedure.md`
step 8 has the full test). It uses the standard
format with `**Raised-by:** Synthesis`, `**Type:** Structural`,
`**Design-level:** Yes`, `**Classification:** User-directed`, and one extra
field after `**Raised-by:**`:

```markdown
**Converges:** Findings 3, 5, 7
```

Convergence findings come first in the main list. They ask whether the
mechanism should be re-evaluated; they do not prescribe a replacement.

## Severity Taxonomy

| Severity | Meaning |
|---|---|
| `CRITICAL` | Breaks a core requirement or contract; must be user-directed |
| `HIGH` | Significant gap or fragility |
| `MEDIUM` | Meaningful but not blocking |
| `TENSION` | Legitimate competing concerns; resolved via user choice |

## Type Taxonomy

`Structural` · `Approach-now` · `Approach-later` · `Fragility` · `Gap`

## Design-level Field

`Yes` — the finding targets the artifact itself (a missing requirement, an untestable AC, a structural inconsistency). Resolution should be applied to the target document.

`No` — the finding targets implementation concerns that should be addressed during build, not in the design artifact. Flag for implementers rather than editing the document.

When critics disagree, `Yes` wins — design-level issues are harder to fix later.

## Visibility and Disposition Fields

The synthesis subagent writes `visibility` once, before challenge returns; it
never changes after that. `disposition` starts NULL or `pending` at synthesis
and is updated by the inline resolution phase as findings are resolved.

**`visibility`** values — set once at synthesis, never changes:

| Value | Meaning |
|---|---|
| `presented` | In scope for resolution |
| `likely-invalid` | Flagged by synthesis as likely invalid |

**`disposition`** values — tracks resolution outcome; `pending` for findings
that enter the resolution flow, then transitions to one of the terminal
values below. NULL for `likely-invalid` findings, which never
enter the resolution flow:

| Value | Meaning |
|---|---|
| `pending` | In scope; awaits resolution |
| `applied` | Resolution executed (auto-apply ran, or user chose an option) |
| `accepted` | User accepted a `rare` finding as a known limitation and it was recorded (see Rare Findings below). Distinct from `skipped`: the limitation is written down, not left unaddressed. |
| `skipped` | User explicitly skipped during resolution |
| `filed` | User chose to create a tracked issue rather than fix in-place. The issue is the durable record; the finding needs no further in-session attention. Distinct from `skipped` — `skipped` means the user declined to act, `filed` means the user acted by creating an issue. |

## Finding Classification

The synthesis subagent classifies each finding as `Auto-apply` or
`User-directed` using these criteria. `synthesis-procedure.md` step 3 mirrors
them — change both together.

**Auto-apply** when ALL of the following hold:
- Fix is localized (one section, one field, one line)
- Critics agree on the fix (no meaningful dissent)
- Severity is not CRITICAL
- Fix introduces no behavior change to the design's intent
- Likelihood is not `rare`
- Fix adds no state, setting, validator, or new mechanism and no guard, reset, or heuristic by which one component guesses at another's state

**User-directed** when ANY of the following hold:
- Fix requires a judgment call between competing approaches
- Severity is CRITICAL
- Likelihood is `rare` (this includes every `Audience assumption:` finding), so the user can accept it as a limitation instead of carrying a fix
- Fix touches multiple sections or has design-level implications
- Fix adds state, a setting, a validator, or a new mechanism, or a guard, reset, or heuristic that guesses at another component's state
- Critics disagreed on the resolution

TENSION findings always classify as User-directed.

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
findings in order.

**Design-doc targets.** When the target type is `design-doc` (see
`skills/mine-challenge/SKILL.md`'s target-type table), every edit below —
Auto-apply, User-directed, and TENSION alike — follows the Content Rules in
`${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-sketch/design-template.md`. In
particular, don't restate a fact that already lives elsewhere in the doc —
cite its existing home instead. In a sketch ledger, a finding that adds or
changes a decision edits that decision's `### D<n>` block. When the user chose
the option (a User-directed or TENSION answer), that choice is the ratification:
write the `**Ratified:**` sentence ("Chose X over Y, to achieve Q, accepting D.")
in the same edit, and add or update that option's column in the decision's criteria table, so the sketch doesn't ask again and the comb finds the table consistent. Only an edit the user never
chose between (an Auto-apply edit) sets `**Ratified:**` back to `pending`.

**Show the reasoning before every question.** Before each User-directed and
TENSION `AskUserQuestion` below, write the finding's `**Deciding-factor:**`,
`**Criteria:**` table, and `**Pick-instead-if:**` as message text before the
call, copied from the findings file as markdown (see `interaction.md`, item 5).
Synthesis wrote them before it chose the recommendation, so they are the
reasoning behind it, not a justification written afterwards.
When a finding lacks them (an older findings file, or a producer that doesn't
write them), show what it has. Don't build a table at this point: one written
after the recommendation exists only argues for it. The recommendation is
taken as-is more often than any other answer here, so the user needs the
trade-offs in view to push back on it.

**Auto-apply** (`Classification: Auto-apply`, `disposition: pending`): Apply
`better-approach` via Edit tool silently. Set `disposition: applied`. No prompt.

**User-directed** (`Classification: User-directed`, `disposition: pending`): Emit
one AskUserQuestion per finding — do not batch. MEDIUM `rare` findings wait for
the Rare Findings batch below; a HIGH `rare` finding is asked here like any other,
with its Accept option still recommended. This is a major gate (finding walkthrough,
see `interaction.md`) — run `context-pct` and prepend the result to the question:

```
AskUserQuestion:
  question: "[Context: N%] Finding N/{total}: <title> (<severity>)"
  header: "<raised-by>"
  options:
    - label: "A: <Option A text>"
      description: "<why-it-matters>"
    - label: "B: <Option B text>"
      description: ""
    - label: "Skip — defer to later"
      description: "Record this finding without acting on it"
    - label: "File as issue"
      description: "Create an issue for this finding"
```

When the finding's Options end in `Accept as a known limitation`, that option
takes Skip's place: accepting is the recorded form of not fixing, and the menu
stays at four.

Each option's `label` must be the letter and text exactly as they appear in the
finding's `**Options:**` list (`A: <first option>`, `B: <second option>`, ...) —
this is the same canonical string `challenge-gate.md` extracts into the
`recommended` field. Prepend `(Recommended) ` to the `description` of whichever
option (A, B, or C) carries the `*(recommended)*` marker in that source list — never
the label — so the label the user selects (passed to `--chosen` in step 6)
matches `recommended` exactly when the user follows the recommendation. Getting
this wrong (baking the cue into the label, or hardcoding it onto one option
regardless of which one the finding actually recommends) silently breaks the
"did the user follow the recommendation" comparison between `chosen` and
`recommended`.

Apply chosen option via Edit tool. Set `disposition: applied` for options
(`accepted` for an `Accept as a known limitation` option, recorded as in Rare
Findings below), `disposition: skipped` for Skip, or `disposition: filed` + create an issue in
the project's issue tracker for File as issue. Continue to next finding.

**Convergence findings** use the User-directed prompt above. If the user picks
**A** (re-evaluate the mechanism), first check prior art when it applies, per
`${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-prior-art/SKILL.md` (Invoking From
a Convergence Gate): invoke `/mine-prior-art` with the topic it describes, and
open the discussion with the brief's recommendation. Then work through the
re-evaluation with the user and apply what they settle on to the target.
Accepting the limitation and documenting it is a valid outcome. Then set `disposition: applied`
on the convergence finding and `disposition: skipped` on every finding in its
`**Converges:**` list without prompting — the re-evaluation supersedes their
individual fixes. This includes CRITICAL converging findings: the user decided
them through the convergence prompt. A converging finding already resolved as
part of an earlier convergence finding keeps that resolution. After the flow,
recommend a re-challenge (`--re-challenge`) of the reworked target as a line in
the final report, not a prompt. If the user picks
**B**, set `disposition: applied` and resolve the converging findings
individually as they come up. Skip and File as issue behave as for any other
finding, and the converging findings still come up individually.

**TENSION findings** (`Classification: User-directed`, `Severity: TENSION`). Same
major-gate rule applies — prepend the `context-pct` result:

```
AskUserQuestion:
  question: "[Context: N%] Finding N/{total}: <title> (TENSION) — <deciding-factor>"
  header: "<raised-by>"
  options:
    - label: "Side A: <side-a summary>"
      description: "<side-a detail>"
    - label: "Side B: <side-b summary>"
      description: "<side-b detail>"
    - label: "Skip — defer to later"
      description: "Record this finding without acting on it"
    - label: "File as issue"
      description: "Create an issue for this finding"
```

Apply chosen side via Edit tool. Set `disposition: applied` and append
`**Chosen:** side-a` or `**Chosen:** side-b` to the finding. For Skip, set
`disposition: skipped`. For File as issue, set `disposition: filed` and
create an issue in the project's issue tracker, same as the User-directed
case. TENSION findings are always resolved here, one at a time, whatever their
likelihood.

**Rare Findings** (User-directed, `Severity: MEDIUM`, likelihood `rare`,
`disposition: pending`). Resolve these after every other finding, as one
batch: a pile of individually reasonable guards for unlikely cases is how a
design bloats, and walking each one invites accepting each one. HIGH rare
findings stay out of the batch: their consequence is large enough that the user
should weigh the likelihood call themselves. If a
convergence already superseded one, it keeps that resolution. Write a short
message listing each remaining rare finding: its number, title, `When-it-bites`,
and its recommended option. Mark any whose recommendation is a fix rather than
Accept, so the code it would add doesn't pass unnoticed. Then ask once (a major gate, so prepend the
`context-pct` result):

```
AskUserQuestion:
  question: "[Context: N%] {count} rare-case findings: accept the recommendations?"
  header: "Rare cases"
  options:
    - label: "Accept recommendations"
      description: "(Recommended) Record each recommended limitation; apply the fixes that were recommended"
    - label: "Let me pick"
      description: "Walk the ones I name individually; accept the rest's recommendations"
```

For "Accept recommendations", carry out each finding's recommended option
without prompting. For "Let me pick", ask which numbers to walk (free text),
run the User-directed prompt for each of those, and carry out the recommended
option for the rest. Carrying out `Accept as a known limitation` records the
limitation where the target keeps its trade-offs: when the target is a sketch
ledger, in the `accepting …` clause of the affected decision's `**Ratified:**`
sentence (the user chose it, so it ratifies); when it is another design doc, in
its known-limitations or assumptions section if it has one. When the target is
code and a caller records limitations (`mine-sketch`'s ship gate writes them to
`known-issues.md`), leave it to the caller. Otherwise it goes in the final
report, listed under the accepted count. Set
`disposition: accepted` for it. Other options are `disposition: applied`, as
usual.

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
