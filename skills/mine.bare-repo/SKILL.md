---
name: mine.bare-repo
description: One-time setup of a bare git repo with worktree-based directory structure. Use when the user wants to set up a new project for worktree-based development.
user-invokable: true
---

## Your task

Set up a bare repository with a worktree-based directory structure. There are two modes:

### Detect mode

- If the user provides a **repository URL** → use **Clone mode** (fresh setup from remote)
- If the user says "convert" or refers to an **existing local repo** → **ask nested vs external** (AskUserQuestion), then proceed with chosen mode
- If ambiguous, ask which mode they want

When asking nested vs external, offer:
- **Nested** — worktree lives inside the repo dir at `<repo>/main/` (standard layout)
- **External** — bare db moves to a separate location, worktree stays at original path (use when path is load-bearing)

---

### Clone mode (fresh from remote)

Ask the user for any missing info:
- **Repository URL** (required)
- **Target directory name** (default: derive from repo URL)

#### Steps

1. Create the target directory
2. Clone bare into `.bare/` subdirectory:
   ```bash
   git clone --bare <url> <target>/.bare
   ```
3. Create the `.git` pointer file:
   ```bash
   echo "gitdir: ./.bare" > <target>/.git
   ```
4. Fix fetch refspec (bare clones don't set this up for remote tracking):
   ```bash
   cd <target> && git config remote.origin.fetch "+refs/heads/*:refs/remotes/origin/*"
   ```
5. Fetch all remote refs:
   ```bash
   cd <target> && git fetch origin
   ```
6. Detect the default branch:
   ```bash
   cd <target> && git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@'
   ```
   If that fails (some hosts don't set origin/HEAD), fall back:
   ```bash
   cd <target> && git branch -r | grep -oP 'origin/\K\S+' | grep -vxF 'HEAD' | head -1
   ```
7. Create the initial worktree for the default branch:
   ```bash
   cd <target> && git worktree add <default-branch> <default-branch>
   ```

Note: All git commands run via `cd <target> &&` since the `.git` pointer file in the target directory routes git to the `.bare/` store.

#### Result

Tell the user the structure is ready and show them how to start:
```
cd <target>/<default-branch>
```

---

### Convert mode (existing local repo)

Converts an existing (non-bare) git repo into the bare+worktree structure, preserving all files including untracked and gitignored items like `.vscode/`, `.claude/`, `.env`, etc.

Ask the user for any missing info:
- **Repo path** (default: current directory)

#### Steps

1. **Dry run first** — always preview before converting:
   ```bash
   git-convert-to-bare --dry-run <path>
   ```
2. Show the user the dry-run output and ask for confirmation to proceed.
3. **Run the conversion**:
   ```bash
   git-convert-to-bare <path>
   ```

#### What the script handles

- Validates: no submodules, no extra worktrees, no uncommitted changes, not already converted
- Moves `.git/` → `.bare/`, creates `.git` pointer file
- Fixes fetch refspec for remote tracking
- Creates worktree for the current branch
- Moves all untracked/gitignored files (`.vscode/`, `.claude/`, `.env`, etc.) into the worktree
- On failure: preserves staged files and prints recovery instructions

#### Result

Tell the user the conversion is complete and show them how to continue:
```
cd <path>/<branch>
```

---

### Convert-External mode (existing local repo → external bare + same-path worktree)

Use when the repo path is load-bearing — referenced by symlinks, installed tools, or
editor/IDE settings — and must not change after conversion.

Ask the user for any missing info:
- **Repo path** (default: current directory)
- **External bare location** (e.g., `~/source/<reponame>`)

#### Steps

1. **Dry run first** — always preview before converting:
   ```bash
   git-convert-to-bare-external --dry-run <repo-path> --bare <bare-path>
   ```
2. Show the user the dry-run output and ask for confirmation to proceed.
3. **Run the conversion**:
   ```bash
   git-convert-to-bare-external <repo-path> --bare <bare-path>
   ```
4. If the repo has an install script that creates symlinks (e.g., `install.sh`), re-run it
   from the worktree after conversion to refresh any symlinks.

#### What the script handles

- All validations from Convert mode (clean tree, no submodules, etc.)
- Moves `.git/` to the external bare location
- Configures bare repo and fixes fetch refspec
- Registers the original directory as the main worktree (path unchanged)
- Preserves all untracked/gitignored files in place

#### Result

```
<bare-path>/          ← bare repo (git database only)
<repo-path>/          ← worktree at original path (files unchanged)
    .git              ← pointer to <bare-path>/
    (all files)

Feature worktrees:
  cd <bare-path>
  git worktree add worktrees/<name> -b feat/<name>
```

Tell the user the conversion is complete and show them how to add feature worktrees:
```
cd <bare-path>
git worktree add worktrees/<name> -b feat/<name>
```
