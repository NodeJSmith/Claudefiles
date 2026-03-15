# How To Be A World-Class Agentic Engineer — sysls (@systematicls)

Source: https://x.com/systematicls/status/2028814227004395561

## Core Thesis

Less is more. Strip dependencies, use basic CLI, master a few principles. Frontier companies will incorporate anything truly useful into their products.

## Key Principles

### 1. Context Is Everything (Context Bloat is the Enemy)

"You want to give your agents only the exact amount of information they need to do their tasks and nothing more."

Memory systems, plugins, poorly-named skills = injecting irrelevant context. Hurts more than helps.

### 2. Separate Research from Implementation

**Bad:** "Go build an auth system" (agent researches all options, pollutes context)
**Good:** "Implement JWT authentication with bcrypt-12 password hashing, refresh token rotation with 7-day expiry..."

If you don't know the implementation details: research task → decision → fresh agent for implementation.

### 3. CLAUDE.md as Logical Directory

"Treat your CLAUDE.md as a logical, nested directory of where to find context given a scenario and an outcome. It should be as barebones as possible, and only contain the IF-ELSE of where to go to seek the context."

```
If coding → read coding-rules.md
  If writing tests → read coding-test-rules.md
    If tests failing → read coding-test-failing-rules.md
```

### 4. Neutral Prompts (Exploit Sycophancy)

**Bad:** "Find me a bug in the database" (agent WILL find one, even if it has to engineer it)
**Good:** "Search through the database, follow along with the logic, report all findings"

### 5. Adversarial Multi-Agent Pattern (Novel)

Three-agent bug-finding pattern exploiting sycophancy:

1. **Bug-finder agent:** Scored +1/+5/+10 by severity. Goes hyper-enthusiastic, reports superset of all possible bugs (including false positives)
2. **Adversarial agent:** Gets bug-score for each disproved bug, but -2x penalty for wrong disproval. Aggressively disproves bugs (including some real ones)
3. **Referee agent:** Told "I have ground truth, +1 correct / -1 wrong." Scores both agents. Result is "frighteningly high fidelity."

### 6. Task Completion Contracts

Agents know how to start tasks, not end them. Solution:

```markdown
# {TASK}_CONTRACT.md
- [ ] All tests pass (agent cannot edit tests)
- [ ] Screenshot verification of design/behavior
- [ ] Specific verification criteria met
```

Stop hook prevents session termination until contract is fulfilled.

### 7. New Session Per Contract (Not Long-Running)

"I've not found long-running, 24 hour sessions to be optimal. By construction, this forces context bloat by introducing context from unrelated contracts."

Better: orchestration layer creates contracts → new session per contract.

### 8. Iterate and Clean Up

Add rules and skills over time → agent develops personality/memory. But eventually they contradict each other or cause context bloat.

"Tell your agents to go for a spa day and consolidate rules and skills and remove contradictions."

## Rules vs Skills

- **Rules** = preferences (don't do X, always do Y)
- **Skills** = recipes (when you encounter X, here's the exact approach)

Both referenced from CLAUDE.md via conditional logic.

## Key Insight on Harnesses/Plugins

"If something truly is ground-breaking and extends agentic use-cases, it will be incorporated into the base products. Skills, memory, subagents, planning — all started as external solutions that got incorporated."

"Do me a favor. Just update your CLI tool of choice every once in awhile and read what new features have been added. That's MORE than sufficient."

## Actionable for Existing Setup

1. **Audit CLAUDE.md as routing table** — is it lean enough? Or does it contain content that should be in rules/skills?
2. **Adversarial multi-agent pattern** — could enhance code-reviewer with bug-finder + adversary + referee
3. **Task contracts with stop hooks** — formalize task completion criteria
4. **Periodic rules/skills consolidation** — detect contradictions, remove bloat
5. **Context bloat check** — are all loaded rules actually needed for every conversation?
