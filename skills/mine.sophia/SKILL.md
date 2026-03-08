---
name: mine.sophia
description: Sophia intent-tracking CLI — CR lifecycle, contracts, checkpoints, and validation for structured change management.
user-invokable: true
---

# Sophia Intent Tracking

Manage Change Requests (CRs) with sophia — structured contracts, task breakdowns, checkpoints, and validation for safe, reviewable changes.

## Arguments

$ARGUMENTS — the operation to perform. See the routing table in Phase 2.

## Phase 1: Detect & Init

### Check sophia installation

```bash
command -v sophia
```

If sophia is not found, ask whether to install it:

```
AskUserQuestion:
  question: "sophia is not on PATH. Install it?"
  header: "Install"
  multiSelect: false
  options:
    - label: "Yes, install sophia"
      description: "Run sophia-install to download and install the binary"
    - label: "No, skip"
      description: "Cancel — sophia is required for this skill"
```

If the user chooses to install:

```bash
sophia-install
```

If they skip, exit the skill.

### Check project config

```bash
test -f SOPHIA.yaml && echo "exists" || echo "missing"
```

If `SOPHIA.yaml` is missing, offer to initialize:

1. Copy `templates/SOPHIA.yaml.template` to `SOPHIA.yaml` in the project root — locate the template by resolving the installed skill's symlink target (e.g., `readlink ~/.claude/skills/mine.sophia` to find the repo root, then use `templates/SOPHIA.yaml.template` relative to it)
2. Ask which trust checks to enable:

```
AskUserQuestion:
  question: "Which trust checks should sophia run?"
  header: "Trust checks"
  multiSelect: false
  options:
    - label: "Both test and lint"
      description: "Run tests and linter as trust gates"
    - label: "Test only"
      description: "Run tests (e.g., pytest, npm test) as a trust gate"
    - label: "Lint only"
      description: "Run linter (e.g., ruff check ., eslint .) as a trust gate"
    - label: "Skip for now"
      description: "No trust checks — add later via SOPHIA.yaml"
```

3. For each selected check, ask for the specific command to use:

```
AskUserQuestion:
  question: "What test command should sophia use?"
  header: "Test cmd"
  multiSelect: false
  options:
    - label: "pytest"
      description: "Python pytest"
    - label: "uv run pytest"
      description: "pytest via uv"
    - label: "npm test"
      description: "Node.js test runner"
    - label: "Custom"
      description: "I'll type the command"
```

4. Uncomment and fill in the chosen definitions in `SOPHIA.yaml`

## Phase 2: CR Lifecycle

Route based on `$ARGUMENTS`:

| Argument pattern | Action |
|---|---|
| `create <description>` | Create a new CR |
| `contract` | Set the CR contract |
| `task add <name>` | Add a task to the current CR |
| `checkpoint` or `done` | Complete a task checkpoint |
| `validate` | Validate the current CR |
| `review` | Review the current CR |
| `status` | Show CR status |
| `merge` | Run the merge workflow |
| (empty) | Show status or ask what to do |

### create

```bash
sophia cr add --description "<description>"
```

### contract

Collect all 7 required contract fields by asking the user conversationally (not via AskUserQuestion — these are free-text fields). Ask for each field one at a time:

1. **why** — Why is this change needed?
2. **scope** — What files/modules will be touched?
3. **non_goals** — What is explicitly out of scope?
4. **invariants** — What must remain true after the change?
5. **blast_radius** — What could break?
6. **test_plan** — How will correctness be verified?
7. **rollback_plan** — How to undo if something goes wrong?

Once all 7 values are collected, set the contract in a single command:

```bash
sophia cr contract set --why "<why>" --scope "<scope>" --non-goals "<non_goals>" --invariants "<invariants>" --blast-radius "<blast_radius>" --test-plan "<test_plan>" --rollback-plan "<rollback_plan>"
```

If the command syntax differs, run `sophia cr contract set --help` first to discover the correct flags.

### task add

```bash
sophia cr task add --name "<name>"
```

Then prompt for the task contract fields (intent, acceptance_criteria, scope):

```bash
sophia cr task contract set --intent "<intent>" --acceptance-criteria "<criteria>" --scope "<scope>"
```

### checkpoint / done

Ask which scope to use for the checkpoint:

```
AskUserQuestion:
  question: "What scope should the checkpoint cover?"
  header: "Scope"
  multiSelect: false
  options:
    - label: "From contract"
      description: "Use the scope defined in the task contract"
    - label: "Specific paths"
      description: "I'll specify which files to include"
    - label: "All changed files"
      description: "Include everything that's changed"
```

Then ask for the commit type:

```
AskUserQuestion:
  question: "What type of change is this?"
  header: "Commit type"
  multiSelect: false
  options:
    - label: "feat"
      description: "New feature"
    - label: "fix"
      description: "Bug fix"
    - label: "refactor"
      description: "Code restructuring"
    - label: "chore"
      description: "Maintenance or tooling"
```

```bash
sophia cr task done --commit-type "<type>"
```

### validate

```bash
sophia cr validate
```

Present the output. If validation fails, show each failing check and suggest fixes.

### review

```bash
sophia cr review
```

Present the review output with any warnings or suggestions.

### status

```bash
sophia cr status --json
```

Parse the JSON output and present it in a readable format: CR description, contract completeness, task list with status, and any `next_steps` from the output.

### merge

First, check the merge mode from SOPHIA.yaml (Read the file). Then run the appropriate workflow:

- **pr_gate**: The merge happens via PR — hand off to `/mine.ship` or `/mine.create-pr`
- **local**: Run `sophia cr merge` directly

### (empty)

Run `sophia cr status --json` and present the current state. If no active CR exists, ask what to do:

```
AskUserQuestion:
  question: "No active CR found. What would you like to do?"
  header: "Next step"
  multiSelect: false
  options:
    - label: "Create a new CR"
      description: "Start a new Change Request"
    - label: "List existing CRs"
      description: "Show archived and completed CRs"
    - label: "Cancel"
      description: "Nothing for now"
```

## Phase 3: Recovery & Help

If any sophia command fails:

1. Read the help for the failing command:

```bash
sophia <command> --help
```

2. Present the error and help text to the user
3. If the `--json` output includes `next_steps`, present those as suggested actions

## What This Skill Does NOT Do

- **Replace git workflow** — sophia tracks intent and contracts, not commits and branches. Use git normally.
- **Implement code** — this skill manages the CR lifecycle. The actual coding happens in your editor or via other skills.
- **Create PRs** — use `/mine.ship` or `/mine.create-pr` for that. Sophia's `merge` mode may trigger PR creation, but the PR workflow is handled by those skills.
- **Run tests directly** — sophia's trust checks invoke test commands, but test writing and debugging belong to other skills.
