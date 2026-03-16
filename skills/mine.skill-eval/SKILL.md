---
name: mine.skill-eval
description: "Use when the user says: \"evaluate skill\", \"compare skill variants\", or \"skill A/B test\". Evaluates and compares skill variants with setup, execution, grading, and reporting."
user-invokable: true
---

# Skill Evaluation

Evaluate skill quality and compare variants using structured grading, blind comparison, and statistical analysis.

## Arguments

$ARGUMENTS — the skill to evaluate (e.g., `mine.audit`, `mine.research`). Can also specify variant paths or A/B config.

## Phase 1: Setup

1. Read `$ARGUMENTS` to identify the skill to evaluate
2. Verify the skill exists using Glob to check for `skills/<skill-name>/SKILL.md`

3. Ask for evaluation parameters:

```
AskUserQuestion:
  question: "How should I evaluate this skill?"
  header: "Eval mode"
  multiSelect: false
  options:
    - label: "Single variant"
      description: "Grade the current version against assertions"
    - label: "A/B comparison"
      description: "Compare two variants of the skill"
    - label: "Iteration test"
      description: "Run the same variant multiple times to check consistency"
```

4. Ask for iteration count:

```
AskUserQuestion:
  question: "How many iterations per variant?"
  header: "Iterations"
  multiSelect: false
  options:
    - label: "3 (recommended)"
      description: "Good balance of signal and speed"
    - label: "5"
      description: "More data, takes longer"
    - label: "1 (quick check)"
      description: "Single pass — useful for debugging"
```

5. Ask for test prompts — what inputs to give the skill:

```
AskUserQuestion:
  question: "What test prompts should I use? (Describe the scenario the skill should handle)"
  header: "Test input"
  multiSelect: false
  options:
    - label: "Use current project"
      description: "Run the skill against this codebase with a representative prompt"
    - label: "I'll provide prompts"
      description: "You'll specify exact prompts to use"
```

6. Write the eval config to a temp YAML file for `skill-eval-run` to consume

## Phase 2: Execute

Run `skill-eval-run` with the config file:

```bash
skill-eval-run /tmp/skill-eval-config.yaml
```

This invokes `claude -p` for each variant x iteration combination and saves outputs to `eval-results/<timestamp>/`.

Monitor progress — each run may take a while depending on the skill's complexity.

## Phase 3: Grade

For each run output, launch a parallel **Agent** subagent. Before dispatching, read the grader agent definition at `skills/mine.skill-eval/agents/grader.md` and include its full instructions in the agent's prompt.

The grader:
- Evaluates each assertion against the skill output with cited evidence
- Meta-evaluates assertion quality (are the assertions themselves good?)
- Returns structured pass/fail results

Launch grader agents in **parallel** — one per run output.

Read each grader's results and collect them for the next phase.

## Phase 4: Compare

If running an A/B test, launch a **comparator** Agent subagent. Read the comparator definition at `skills/mine.skill-eval/agents/comparator.md` and include its full instructions in the agent's prompt.

The comparator:
- Receives two outputs labeled "Output 1" and "Output 2" (blind — no knowledge of which is A vs B)
- Scores each on Content (1-5) and Structure (1-5)
- Justifies scores with specific quotes
- Declares winner or tie

Run one comparator per iteration pair (A run 1 vs B run 1, etc.).

## Phase 5: Analyze & Report

1. Launch an **analyzer** Agent subagent (read the definition at `skills/mine.skill-eval/agents/analyzer.md` and include its full instructions in the prompt) with all graded results:
   - Identifies systematic differences (not random noise)
   - Explains root causes
   - Suggests improvements

2. Run `skill-eval-aggregate` for statistical summary:

```bash
skill-eval-aggregate eval-results/<timestamp>/
```

3. Present results:

```
## Evaluation Results: <skill name>

### Pass Rates
| Assertion | Variant A | Variant B | Delta |
|-----------|-----------|-----------|-------|
| ...       | ...       | ...       | ...   |

### Scores (mean +/- std dev)
| Metric    | Variant A     | Variant B     |
|-----------|---------------|---------------|
| Content   | 3.8 +/- 0.4   | 4.2 +/- 0.3   |
| Structure | 4.0 +/- 0.5   | 3.9 +/- 0.2   |

### High-Variance Assertions
(assertions that passed inconsistently — unreliable tests)

### Analysis
<analyzer findings — why variants differ, root causes, improvement suggestions>

### Recommendation
<which variant to use, or what to change>
```

4. Ask what to do with the results:

```
AskUserQuestion:
  question: "What would you like to do with these results?"
  header: "Next step"
  multiSelect: false
  options:
    - label: "Apply improvements"
      description: "Edit the skill based on the analysis"
    - label: "Save report"
      description: "Write the evaluation report to a file"
    - label: "Run again"
      description: "Re-run with different parameters or prompts"
    - label: "Done"
      description: "Results noted, no further action"
```

## What This Skill Does NOT Do

- **Edit skills automatically** — it evaluates and recommends, but the user decides what to change
- **Test non-skill prompts** — this is specifically for SKILL.md evaluation, not general prompt testing
- **Guarantee statistical significance** — with 3-5 iterations, results are directional, not rigorous. Use more iterations for higher confidence.
