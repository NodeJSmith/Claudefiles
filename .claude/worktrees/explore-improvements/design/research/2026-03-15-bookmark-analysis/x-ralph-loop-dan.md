# Ralph Loop Setup — Dan (@d4m1n)

Source: https://x.com/d4m1n/status/2026032801322356903

## Core Concept

Each iteration starts with fresh context. Agent reads task list, picks next task, implements, verifies, commits, exits. Next iteration starts clean. State lives in text files and git commits, not in context window.

## Architecture

```
.agent/
├── PROMPT.md          # Main iteration instructions
├── SUMMARY.md         # Project summary for context
├── STEERING.md        # Steer the agent mid-run (edited while loop runs)
├── tasks.json         # Task lookup table
├── tasks/             # Individual task specifications
├── prd/               # Product requirements documents
├── logs/              # Progress tracking
├── history/           # Iteration outputs
└── skills/            # Reusable agent capabilities
```

## Key Patterns

1. **Fresh context per iteration** — avoids "dumb zone" when context fills up
2. **STEERING.md for mid-run redirection** — agent reads at start of each iteration; write critical bugs here for immediate handling
3. **PRD → tasks pipeline** — prd-creator skill expands brain dump into structured PRD, asks clarifying questions, breaks into tasks
4. **Docker sandbox** — full permissions inside container, can't touch host
5. **Git as state** — every completed task is a commit; `git revert` for bad commits, task tests fail, Ralph re-attempts

## Scaling Pattern

```bash
./ralph.sh -n 2    # start small, watch and verify
./ralph.sh -n 10   # scale up after confidence
./ralph.sh -n 30   # overnight runs
```

## Where It Works / Doesn't

**Works:** Prototyping/MVPs, automated testing, migrations, bulk refactoring
**Struggles:** Pixel-perfect design, novel architecture, security-critical code

## Key Insight

"State lives in text files and git commits. Not in the context window. This is how you scale AI coding from 'help me write a function' to 'build me an app.'"

The STEERING.md pattern (live mid-run redirection) and fresh-context-per-iteration are the most transferable ideas.
