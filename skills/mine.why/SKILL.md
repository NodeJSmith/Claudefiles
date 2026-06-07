---
name: mine.why
description: "Use when the user says: \"why is this code like this\", \"why does this exist\", \"why was this built this way\", \"decision rationale\", \"what's the history behind\". Decision archaeology — reconstructs historical rationale from evidence, not speculation."
user-invocable: true
---

# Why

Decision archaeology for existing code. Reconstructs why code is shaped the way it is by querying multiple evidence sources in parallel. Operates under strict evidence-before-narrative epistemics — explicitly states when evidence is absent rather than speculating.

Critical for safe refactoring: if you don't know why a constraint exists, removing it can break things that aren't obvious from the diff.

## How This Differs From Other Skills

| Skill | What it answers |
|-------|-----------------|
| **`/mine.why`** | **"Why is this code shaped this way?"** — historical rationale |
| `/mine.how` | "How does this work?" — runtime flow and mental models |
| `/mine.research` | "What would it take to do X?" — forward-looking investigation |

## Arguments

$ARGUMENTS — the code or decision to investigate. Can be:
- A code pattern: `/mine.why "why does the dispatcher use a priority queue instead of FIFO?"`
- A file: `/mine.why src/services/auth.py`
- A constraint: `/mine.why "why is there a 30-second timeout on webhook retries?"`
- A structural choice: `/mine.why "why are apps and services in separate directories?"`
- Empty: ask the user what they want to understand

## Phase 1: Frame the Investigation

If $ARGUMENTS is empty:

```
AskUserQuestion:
  question: "What code or decision do you want to understand the rationale behind?"
  header: "Investigate"
  multiSelect: false
  options:
    - label: "I'll type my question"
      description: "Ask about any code shape, constraint, or structural decision"
    - label: "Something in the current diff"
      description: "I'll point to specific code I'm about to change"
```

Identify the **target**: the specific code, file, pattern, or decision to investigate. If the user named a file, read it. If they named a pattern or constraint, grep to locate the relevant code. Record the target's file path(s) and line range(s).

Run `get-skill-tmpdir mine-why` to establish `<dir>`.

## Phase 2: Gather Evidence

Dispatch 5 parallel evidence-gathering agents. Each searches one category and writes findings to its own temp file. Null results are first-class evidence — "no issues found referencing this code" is a finding, not a failure.

All agents use `subagent_type: "Explore"` (Haiku, read-only).

### Agent 1: Version Control History

```
Investigate the git history of this code to understand why it exists.

Target: <file path(s) and line range(s)>
Question: <the user's question>

Instructions:
1. Run git log on the target file(s): git log --follow --all -p -- <file>
2. Run git blame on the specific lines: git blame -L <start>,<end> <file>
3. For each significant commit, read the full commit message
4. Look for: the original commit that introduced this code, refactors that reshaped it, reverts that restored it, merge commits with context
5. Write findings to <dir>/evidence-git.md

Format:
- List each relevant commit: hash, date, author, full message, what changed
- Note if the code has been stable (unchanged for months) or volatile (frequently modified)
- Note if the introducing commit message explains the rationale
- If git history is shallow or the file was moved, say so — don't guess
```

### Agent 2: Issue Tracker and PRs

```
Search for issues and pull requests related to this code.

Target: <file path(s) and line range(s)>
Question: <the user's question>

Instructions:
1. Extract keywords from the target (function names, class names, feature terms)
2. Search issues: gh-issue list -R <repo> --state all --search "<keywords>" --limit 20
3. Search PRs: gh pr list -R <repo> --state all --search "<keywords>" --limit 20
4. For promising matches, read the body and first few comments
5. Write findings to <dir>/evidence-issues.md

Format:
- List each relevant issue/PR: number, title, key excerpt from body/comments
- Note if an issue explicitly explains the design decision
- If no issues or PRs reference this code, state that clearly
```

### Agent 3: Design Docs and Research

```
Search for design documents and research briefs related to this code.

Target: <file path(s) and line range(s)>
Question: <the user's question>

Instructions:
1. Glob for design docs: design/specs/*/design.md, design/research/*/research.md
2. Grep each for keywords related to the target
3. Also check: CLAUDE.md, README.md, ARCHITECTURE.md, docs/ directory
4. Read matching sections in full
5. Write findings to <dir>/evidence-design.md

Format:
- List each relevant doc: path, section heading, key excerpt
- Note if a design doc explicitly chose this approach over alternatives
- If no design docs reference this code, state that clearly
```

### Agent 4: Rules, Comments, and Inline Rationale

```
Search for rules, comments, and inline explanations related to this code.

Target: <file path(s) and line range(s)>
Question: <the user's question>

Instructions:
1. Read the target code and all comments in/around it
2. Grep rules/ directory for keywords related to the target
3. Search for TODO, HACK, WORKAROUND, NOTE comments near the target
4. Check if any rules (rules/common/*.md) reference the pattern or constraint
5. Write findings to <dir>/evidence-rules.md

Format:
- List each relevant comment or rule: location, content
- Note if a comment explains WHY (rationale) vs just WHAT (description)
- If no comments or rules reference this code, state that clearly
```

### Agent 5: Test Assertions as Constraints

```
Search for tests that encode constraints related to this code.

Target: <file path(s) and line range(s)>
Question: <the user's question>

Instructions:
1. Find test files that import or reference the target code
2. Read the test assertions — they often encode constraints that explain why code is shaped a certain way
3. Look for: parameterized tests with specific edge cases, regression tests with descriptive names, test comments explaining what they guard against
4. Write findings to <dir>/evidence-tests.md

Format:
- List each relevant test: file, test name, what it asserts, what constraint it implies
- Note if a test name or comment references a bug number, incident, or specific scenario
- If no tests reference this code, state that clearly
```

## Phase 3: Synthesize

After all evidence agents complete, dispatch a synthesis agent:

```
Agent(subagent_type: "general-purpose", model: "sonnet")
```

Synthesis prompt:

```
Synthesize evidence from five sources into a confidence-calibrated explanation
of why code is shaped the way it is.

Question: <the user's question>
Target: <file path(s) and line range(s)>

Evidence files (read each in full):
- <dir>/evidence-git.md
- <dir>/evidence-issues.md
- <dir>/evidence-design.md
- <dir>/evidence-rules.md
- <dir>/evidence-tests.md

Instructions:
1. Read all five evidence files
2. For each claim about rationale, assign a confidence level:
   - HIGH — multiple independent sources agree (e.g., commit message + design doc + test comment)
   - MEDIUM — one source provides direct evidence (e.g., only a commit message, but it's clear)
   - LOW — evidence is indirect (e.g., a test implies a constraint but doesn't state it)
   - UNKNOWN — no evidence found; state this explicitly rather than speculating
3. Write the explanation to <dir>/synthesis.md

Format:
Start with a one-paragraph summary of the most likely rationale, stating the
overall confidence level.

Then for each aspect of the rationale:

**[Aspect — e.g., "The priority queue was chosen over FIFO"]**
Confidence: HIGH | MEDIUM | LOW | UNKNOWN
Evidence: [cite specific sources — commit hash, issue number, doc path, test name]
Explanation: [what the evidence says]

End with:

**Evidence gaps:** [what you looked for but didn't find — these are important
for the reader to know. "No design doc covers this decision" is actionable
information for someone considering a refactor.]

Rules:
- Never fill an UNKNOWN gap with speculation. "No evidence found" is the answer.
- Treat null results as findings. "No issues reference this code" tells the reader
  that the decision predates the issue tracker or was never controversial.
- If evidence conflicts (e.g., a commit message says one thing, a design doc says
  another), present both and flag the conflict rather than picking a winner.
- Reference every claim with its source — commit hash, file:line, issue number.
```

## Phase 4: Present

Read `<dir>/synthesis.md` and present it conversationally in the main context. Do not write files or produce artifacts.

If all aspects are UNKNOWN, say so directly: "I searched git history, issues, PRs, design docs, rules, comments, and tests — none of them explain this decision. The rationale appears to be undocumented."
