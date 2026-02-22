#!/usr/bin/env bash
# Symlink Claudefiles into ~/.claude/
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="${CLAUDE_HOME:-$HOME/.claude}"

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
      echo "skip: $target exists (not a symlink)" >&2
      continue
    fi
    ln -s "$item" "$target"
  done
done

# Rules: symlink per-language directories (common/, python/, etc.)
if [ -d "$REPO_DIR/rules" ]; then
  mkdir -p "$CLAUDE_DIR/rules"
  for lang_dir in "$REPO_DIR/rules"/*/; do
    [ -d "$lang_dir" ] || continue
    lang="$(basename "$lang_dir")"
    target="$CLAUDE_DIR/rules/$lang"
    if [ -L "$target" ]; then
      rm "$target"
    elif [ -e "$target" ]; then
      echo "skip: $target exists (not a symlink)" >&2
      continue
    fi
    ln -s "${lang_dir%/}" "$target"
  done
fi

# Bin: symlink scripts into ~/.local/bin (should be in PATH)
if [ -d "$REPO_DIR/bin" ]; then
  BIN_DIR="$HOME/.local/bin"
  mkdir -p "$BIN_DIR"
  for item in "$REPO_DIR/bin"/*; do
    [ -e "$item" ] || continue
    target="$BIN_DIR/$(basename "$item")"
    if [ -L "$target" ]; then
      rm "$target"
    elif [ -e "$target" ]; then
      echo "skip: $target exists (not a symlink)" >&2
      continue
    fi
    ln -s "$item" "$target"
  done
fi

echo "Claudefiles installed to $CLAUDE_DIR"
