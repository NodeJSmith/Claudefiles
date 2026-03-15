# ralph for idiots — agrim singh (@agrimsingh)

Source: https://x.com/agrimsingh/status/2010412150918189210

## Core Insight

"Ralph treats AI like a volatile process, not a reliable collaborator. Progress persists. Failures evaporate."

Context pollution is inevitable — failures accumulate, can't be deleted. Ralph throws away context and starts fresh each iteration.

## State Hygiene (the actual technique)

The loop is not the technique. **State hygiene is the technique.**

```
context (bad for state)        files + git (good for state)
- dies with the convo          - only what you choose to write
- polluted by dead ends        - can be patched / rolled back
- "memory" can drift           - git doesn't hallucinate
```

## Anchor File Pattern

Single source-of-truth that survives rotations:

```markdown
---
task: build a rest api
test_command: "npm test"
---

# task: rest api

## success criteria
1. [ ] get /health returns 200
2. [ ] post /users creates a user
3. [ ] all tests pass
```

## State Directory (.ralph/)

```
.ralph/
├── guardrails.md   # learned constraints ("signs") — append-only
├── progress.md     # what's done / what's next
├── errors.log      # what blew up
└── activity.log    # tool usage + token tracking
```

## Guardrails: Same Mistake Never Happens Twice

```markdown
### sign: check imports before adding
- trigger: adding a new import statement
- instruction: check if import already exists
- added after: iteration 3 (duplicate import broke build)
```

Guardrails are append-only. Mistakes evaporate. Lessons accumulate.

## Signal Detection (Cursor version)

```
stream-parser.sh emits signals:
├── warn     (near context limits)
├── rotate   (hard rotate now)
├── gutter   (same failure repeatedly)
└── complete (all checkboxes done)
```

"Gutter detection" = same command fails repeatedly, file thrashing. Turns "it's losing it" into mechanics.

## Critique of Claude Code Plugin Approach

"The Claude Code plugin approach keeps pounding the model in a single session until context rots. Ralph assumes pollution is coming and rotates deliberately before it happens."

## When to Use / Not Use

**Use:** Specs are crisp, success is machine-verifiable (tests/types/lint), bulk execution (CRUD, migrations, refactors, porting)
**Don't use:** Still deciding what to build, taste/judgment > correctness, can't define "done"

"If you can't write checkboxes, you're not ready to loop. You're ready to think."

## Key Takeaway for Existing Setup

The guardrails.md pattern (append-only learned constraints) and gutter detection (detecting repeated failures) are the most transferable ideas. The critique of single-session context rot validates the pre-compact / context preservation work.
