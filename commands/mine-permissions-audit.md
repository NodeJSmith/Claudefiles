---
description: "Use when the user says: \"audit permissions\", \"reduce permission prompts\". Analyze frequent permission prompts and recommend allow-list entries to reduce friction."
---

# Permissions Audit

Find the permission prompts that recur for routine, safe operations and offer to auto-allow them, so there are fewer prompts without opening up anything risky. Nothing changes until the user picks entries.

## Arguments

$ARGUMENTS — unused; ignore if provided.

## Sources

Gather these in parallel:

- **Current settings:** `~/Claudefiles/settings.json` (may not exist yet). This is the baseline; don't recommend what is already allowed.
- **Debug logs:** the prompts Claude Code actually raised are the ground truth. This yields ranked `(count, ruleContent)` pairs, the exact strings Claude Code suggested allowing:

  ```bash
  ls -t ${CLAUDE_CONFIG_DIR:-$HOME/.claude}/debug/*.txt 2>/dev/null | head -20 | xargs grep -h "ruleContent" 2>/dev/null | grep -oP '"ruleContent": "\K[^"]+' | sort | uniq -c | sort -rn | head -40
  ```

- **Local settings drift:** `settings.local.json` files under `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects` hold per-session approvals the user already granted. Entries in their `permissions.allow` that are missing from the merged `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json` are candidates for promotion to the portable list.

## Judging what to recommend

A good recommendation is a reusable pattern for something routine and low-risk, seen often or across projects. Repeated counts and presence in several projects are strong signal; a single appearance is weak.

Skip what shouldn't be auto-allowed or can't generalize:
- `AskUserQuestion`, `EnterPlanMode`, `ExitPlanMode`: user interaction and mode switches must always prompt.
- One-off invocations with serialized arguments (over about 200 characters or multi-line, such as an `ExitPlanMode` carrying a whole plan), `TaskCreate`/`TaskUpdate` with specific subjects or IDs, and single-character or obviously one-off commands.
- Shell-in-shell (`bash:*`, `bash -c:*`) and for-loop fragments (`for sid in ...`, `do echo ...`, `done`). The loop fragments mean a multi-line loop caused extra prompts; the fix is sequential Bash calls, not allowing `for:*`.

Assess safety by what the pattern can do. Build, test, lint, and read-only tools (`git:*`, `ls:*`, `pytest:*`, `ruff:*`) are safe; broad interpreters and installers (`python3:*`, `pip:*`, `npm:*`) can run arbitrary code, so recommend them with that note; destructive ones (`rm:*`, `sudo:*`) get mentioned as risky, not recommended. File-access patterns that share a project root should be generalized to per-tool patterns (`Read(/path/to/project/*)`). Task-dispatch entries such as `Task(standard-worker)` are generally safe. Use the `//path/**` form from the debug logs as-is; that is what Claude Code matches.

## Report

Present a compact report with the count and pattern per entry, sorted by count: high-confidence recommendations (keep it scannable), moderate-confidence ones with a note on the risk, local settings drift with the project each came from, and a short skipped summary so the user can see what was deliberately left out. Summarize long patterns instead of printing them raw, and when a section is long, show the top entries and summarize the tail in a line rather than dropping it silently.

## Applying

Ask which entries to add. The user can add any entry the report shows (entries in a summarized tail are reachable through "add everything in a section" or by naming them), grouped by section (high-confidence, moderate, drift); start with the high-confidence section when it has entries, and make the others reachable in the same run. When all are empty, say so and stop. Offer to add everything in a section (put the entry count in the description), let the user pick entries (`multiSelect: true`, four per question, as many questions as needed), or make no changes.

To apply: create `~/Claudefiles/settings.json` as `{"permissions": {"allow": []}}` if it doesn't exist, add the selected patterns to `permissions.allow` without duplicating existing ones, run `claude-merge-settings` to propagate to `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json`, and confirm what was added.
