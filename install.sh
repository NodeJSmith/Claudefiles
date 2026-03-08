#!/usr/bin/env bash
# Symlink Claudefiles into ~/.claude/
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="${CLAUDE_HOME:-$HOME/.claude}"
BIN_DIR="$HOME/.local/bin"

shadowed=()

for dir in agents skills commands scripts/hooks; do
  src="$REPO_DIR/$dir"
  [ -d "$src" ] || continue
  dest="$CLAUDE_DIR/$dir"
  mkdir -p "$dest"
  for item in "$src"/*; do
    [ -e "$item" ] || continue
    target="$dest/$(basename "$item")"
    if [ -L "$target" ]; then
      rm "$target"  # replace existing symlink
    elif [ -e "$target" ]; then
      shadowed+=("$target (shadows $item)")
      continue
    fi
    ln -s "$item" "$target"
  done
done

# Rules: symlink individual files within each language subdirectory (common/, python/, etc.)
# File-level symlinks allow multiple sources (Claudefiles, Dotfiles) to contribute
# files into the same ~/.claude/rules/<lang>/ directory without conflict.
if [ -d "$REPO_DIR/rules" ]; then
  mkdir -p "$CLAUDE_DIR/rules"
  for lang_dir in "$REPO_DIR/rules"/*/; do
    [ -d "$lang_dir" ] || continue
    lang="$(basename "$lang_dir")"
    dest="$CLAUDE_DIR/rules/$lang"
    if [ -L "$dest" ]; then
      rm "$dest"   # upgrade: remove old whole-directory symlink
    elif [ -e "$dest" ] && [ ! -d "$dest" ]; then
      shadowed+=("$dest (shadows directory $lang_dir)")
      continue
    fi
    mkdir -p "$dest"
    for item in "$lang_dir"*; do
      [ -e "$item" ] || continue
      target="$dest/$(basename "$item")"
      if [ -L "$target" ]; then
        rm "$target"
      elif [ -e "$target" ]; then
        shadowed+=("$target (shadows $item)")
        continue
      fi
      ln -s "$item" "$target"
    done
  done
fi

# Learned: symlink individual files into ~/.claude/learned/
# File-level symlinks allow Dotfiles (and future sources) to also contribute files
# without conflict. Skipped silently if Claudefiles has no learned/ directory.
if [ -d "$REPO_DIR/learned" ]; then
  dest="$CLAUDE_DIR/learned"
  if [ -L "$dest" ]; then
    rm "$dest"   # upgrade: remove old whole-directory symlink
  elif [ -e "$dest" ] && [ ! -d "$dest" ]; then
    shadowed+=("$dest (shadows directory $REPO_DIR/learned)")
    dest=""
  fi
  if [ -n "$dest" ]; then
    mkdir -p "$dest"
    for item in "$REPO_DIR/learned"/*; do
      [ -e "$item" ] || continue
      target="$dest/$(basename "$item")"
      if [ -L "$target" ]; then
        rm "$target"
      elif [ -e "$target" ]; then
        shadowed+=("$target (shadows $item)")
        continue
      fi
      ln -s "$item" "$target"
    done
  fi
fi

# Bin: symlink scripts into ~/.local/bin (should be in PATH)
if [ -d "$REPO_DIR/bin" ]; then
  mkdir -p "$BIN_DIR"
  for item in "$REPO_DIR/bin"/*; do
    [ -e "$item" ] || continue
    target="$BIN_DIR/$(basename "$item")"
    if [ -L "$target" ]; then
      rm "$target"
    elif [ -e "$target" ]; then
      shadowed+=("$target (shadows $item)")
      continue
    fi
    ln -s "$item" "$target"
  done
fi

# Check for stale symlinks (point to targets that no longer exist)
stale=()

# Top-level dirs: agents, skills, commands, hooks, bin
for dir in "$CLAUDE_DIR"/agents "$CLAUDE_DIR"/skills "$CLAUDE_DIR"/commands \
           "$CLAUDE_DIR"/scripts/hooks "$BIN_DIR"; do
  [ -d "$dir" ] || continue
  for link in "$dir"/*; do
    [ -L "$link" ] || continue
    [ ! -e "$link" ] && stale+=("$link -> $(readlink "$link")")
  done
done

# Rules: check file-level symlinks within each language subdirectory
if [ -d "$CLAUDE_DIR/rules" ]; then
  for lang_dir in "$CLAUDE_DIR/rules"/*/; do
    [ -d "$lang_dir" ] || continue
    [ ! -L "${lang_dir%/}" ] || continue
    for link in "$lang_dir"*; do
      [ -L "$link" ] || continue
      [ ! -e "$link" ] && stale+=("$link -> $(readlink "$link")")
    done
  done
fi

# Learned: check file-level symlinks (skip if it's itself a whole-dir symlink)
if [ -d "$CLAUDE_DIR/learned" ] && [ ! -L "$CLAUDE_DIR/learned" ]; then
  for link in "$CLAUDE_DIR/learned"/*; do
    [ -L "$link" ] || continue
    [ ! -e "$link" ] && stale+=("$link -> $(readlink "$link")")
  done
fi

# Report problems
if [ ${#shadowed[@]} -gt 0 ]; then
  echo "" >&2
  echo "warning: ${#shadowed[@]} file(s) not symlinked — a non-symlink already exists at the destination:" >&2
  for entry in "${shadowed[@]}"; do
    # entry format: "target (shadows source)" — extract target for the rm command
    target_path="${entry%% (shadows *}"
    echo "  $entry" >&2
    echo "    rm \"$target_path\"" >&2
  done
  echo "  Remove the above file(s) and re-run install.sh" >&2
fi

if [ ${#stale[@]} -gt 0 ]; then
  echo "" >&2
  echo "warning: ${#stale[@]} stale symlink(s) found (target no longer exists):" >&2
  for entry in "${stale[@]}"; do
    # entry format: "link -> target" — extract link path for the rm command
    link_path="${entry%% -> *}"
    echo "  $entry" >&2
    echo "    rm \"$link_path\"" >&2
  done
fi

echo "Claudefiles installed to $CLAUDE_DIR"

# Prerequisite checks
if ! command -v pyright &>/dev/null; then
  echo "" >&2
  echo "note: pyright not found — LSP features (go-to-definition, find-references, hover)" >&2
  echo "      will not work until you install it:" >&2
  echo "        npm install -g pyright" >&2
fi
