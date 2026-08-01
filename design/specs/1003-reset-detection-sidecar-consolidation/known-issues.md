# Known Issues

Durable issues discovered during orchestration that were intentionally not fixed in this run.

## KI-001: Stale CLAUDE.md references to moved sidecar scripts

Status: open
Source: T03 (integration-review, iteration 3)
Reason not fixed now: out-of-scope
Observed in: T03, commits 67f5da4 / c9d38f9 (Dotfiles repo)
Affected files:
- /home/jessica/Dotfiles/CLAUDE.md:139
- /home/jessica/Dotfiles/CLAUDE.md:204
- /home/jessica/Dotfiles/CLAUDE.md:205
- /home/jessica/Dotfiles/CLAUDE.md:294

Issue:
CLAUDE.md still describes `tools/context-tier.sh`, `tools/claude-context-writer`, and
`tools/claude-status-writer` as living in the Dotfiles repo — including a `statusLine.command`
pointer to `tools/claude-context-writer` — but commit 67f5da4 (this same task, T03) deleted
those files and emptied the `statusLine` block. The files now live in Claudefiles at
`scripts/hooks/`.

Why deferred:
T03's design.md "Changed Files" section for the Dotfiles repo lists only the three tool
deletions and the `settings.json` edit — CLAUDE.md is not among the target files for this
task, and editing it would expand beyond the approved task/design scope. T03 is the last
task in this feature, so no later task in this run owns these files either.

Recommended follow-up:
Update the four passages in Dotfiles CLAUDE.md to point readers at the new Claudefiles
location (`scripts/hooks/claude-context-writer`, `claude-status-writer`, `context-tier.sh`)
instead of the deleted `tools/` paths, so a future reader isn't sent chasing files that no
longer exist via grep.

Acceptance criteria:
- CLAUDE.md:139, 204, 205, 294 (or their renumbered equivalents) describe the sidecar
  pipeline's current Claudefiles location, not the deleted Dotfiles `tools/` paths.
