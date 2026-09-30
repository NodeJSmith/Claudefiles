# Design Doc Format

The shared contract for how a `design.md` written by `mine-define` or `mine-sketch` encodes
requirements — cited by the templates that produce it, the tools that parse it, and the skills
that review it, instead of each restating the rules independently. Consult this file whenever
you write, parse, or review `FR#N`/`AC#N` content in a design doc, rather than re-deriving the
rules from a specific template or consumer.

## FR/AC Definition

An `FR#N` or `AC#N` is a **definition** only when its bolded ID is the first thing in a Markdown
list item, at any indentation, immediately followed by whitespace and then the requirement text.

**Definitions:**

```
- **FR#1** Users can create widgets
  - **AC#1** Widget list shows all widgets
```

**Not definitions:**

```
- This depends on **FR#1** being done first.
- **AC#2** Widget can be removed (also FR#2)
- ~~**FR#9**~~ **Removed** — dropped.
- **FR#3**: Users can archive widgets
- **FR#4**
```

- Line 1 cites `**FR#1**` mid-sentence — the bolded ID isn't the first thing in the list item.
- Line 2 defines `AC#2` (its own bolded ID starts the item, followed by whitespace and text) — the
  `(also FR#2)` suffix names a secondary FR the AC also verifies, not a new definition of `FR#2`.
- Line 3 is a struck-through removal of `FR#9`.
- Line 4's bolded ID is followed directly by punctuation (`:`), not whitespace.
- Line 5's bolded ID is followed by nothing.

`packages/cfl/src/cfl/snapshot.py`'s `_FR_PATTERN`/`_AC_PATTERN` enforce this rule. Any
other extraction of `FR#N`/`AC#N` content from a design doc — the `mine-plan` validator's
LLM-driven extraction included — must apply the same definition, not a looser or stricter one, or
the two extraction paths can disagree on the same document.

The two example blocks above are test input: `packages/cfl/tests/test_snapshot.py` reads each
block from under its `**Definitions:**` / `**Not definitions:**` label and runs it through that
parser. Keep each block directly under its label, and when you add or change an example, update
the IDs that test expects.

## Nested ACs and Numbering Rules

Each Functional Requirement carries its own Acceptance Criteria as nested bullets — there is no
top-level `## Acceptance Criteria` section:

- AC numbers are global and sequential across the document, never hierarchical (e.g., `AC#3.2`)
- An AC that verifies several FRs sits under its primary FR and names the others as `(also FR#N)`
  or `(also FR#N, FR#M)`, but only when it verifies each cited FR's behavior on its own; an FR that
  no AC fully verifies gets its own AC
- Checks that apply to the whole test suite ("all tests pass", "lint clean") are not ACs — task
  Verify and orchestrate already enforce them

## One Fact, One Home

Any enumeration (an inventory table, a file list, a coverage list) lives in exactly one section;
every other section cites it by ID or name instead of re-listing it. A count or one-line summary
of a fact is a copy of it, so it cites the home too. When several requirements depend on the same mapping,
write the mapping once — usually a table — and have the requirements cite it.

A reference that names the home and adds none of the fact's content — no count, no list items — is
a citation and is allowed. Restating the count or the inventory, even briefly, is a copy and is not.

## Where Tests Are Named

A design's testing intent is named in two places, and only these two:

- **Acceptance Criteria** — each AC that implies testable behavior names or implies the test that
  proves it, since an AC must be verifiable by a local command
- **Test Strategy** (`### Required Test Types`, `### Existing Tests to Adapt`, `### Tests to
  Remove`) — concerns that span requirements rather than belonging to one FR/AC

Anything that checks "did the design name a test that doesn't exist" — `mine-implementation-review`'s
missing-test check, `mine-orchestrate`'s TDD co-location check, or any future consumer — must look
in both places. A check that only reads Test Strategy misses tests named in ACs.
