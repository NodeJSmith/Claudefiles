# Tmux Session Naming

## Convention

At conversation start, rename the session to reflect the current work:

```bash
claude-tmux rename "<name>"
```

The script handles the `$TMUX` check internally — exits silently when not in tmux.

## Name Format

`<project>-<context>`, kebab-case, max ~30 chars.

- **project**: derived from the working directory name (e.g., `dotfiles`, `hassette`, `claudefiles`)
- **context**: branch name, issue number, task description — whatever best identifies the work

Examples:
- `dotfiles-main` — general work on main branch
- `hassette-238-url-fix` — issue worktree
- `claudefiles-pr3` — PR review
- `dotfiles-tmux-naming` — feature work

Rules:
- Truncate intelligently (don't cut mid-word)
- No spaces or special characters beyond hyphens
- Prefer branch name if it's already descriptive

## Drift Detection

When the conversation topic shifts significantly (e.g., pivoting from one feature to another), update the session name to match the new focus.
