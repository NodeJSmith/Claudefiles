---
name: mine.wp
description: "Use when the user says: \"move WP to doing\", \"WP status\", or \"kanban\". Manages work package lanes — move between lanes, view status, list WPs for the current feature."
user-invocable: true
---

# mine.wp

Thin user-facing wrapper around `spec-helper` for work package (WP) lane management. Use this to advance WPs through the pipeline, check status, or list all WPs.

## Arguments

$ARGUMENTS — subcommand and arguments:
- `move <wp-id> <lane>` — move a WP to a new lane
- `status [feature]` — show terminal kanban for all features, or just the specified feature
- `list` — list all WPs for the current feature with their lane

If $ARGUMENTS is empty, show usage.

---

## Usage

### move

Moves a work package to a new lane. Valid lanes: `planned`, `doing`, `for_review`, `done`.

Use `--auto` to resolve the most recently modified feature, or pass an explicit feature if the user specified one:

```bash
spec-helper wp-move --auto <wp-id> <lane>
spec-helper wp-move <feature> <wp-id> <lane>
```

Examples:
```bash
spec-helper wp-move --auto WP02 doing
spec-helper wp-move 001-user-auth WP02 for_review
```

Print the result. If the WP was already in the target lane, note that no change was made.

### status

Print the terminal kanban. If no feature is specified, show all features; if one is provided, scope to it:

```bash
spec-helper status
spec-helper status <feature>
```

### list

List all WPs for the current feature with their lane and title.

Run:
```bash
spec-helper wp-list --auto
```

Parse the JSON output and print a human-readable table:

```
WP01  planned  Set up database schema
WP02  doing    Implement API endpoints
WP03  planned  Write integration tests
```

---

## Error Handling

If `spec-helper` exits non-zero, print the error message and stop. Do not retry.

If no feature can be identified (e.g., running outside a repo with `design/specs/`), ask:

```
AskUserQuestion:
  question: "Which feature are you working on?"
  header: "Select feature"
  multiSelect: false
  options: []
```

Then use the user's answer as the feature identifier.

---

## Usage (when $ARGUMENTS is empty)

Print:

```
Usage:
  /mine.wp move <wp-id> <lane>    Move a WP to a new lane
  /mine.wp status                 Show terminal kanban
  /mine.wp list                   List WPs for the current feature

Valid lanes: planned, doing, for_review, done
```
