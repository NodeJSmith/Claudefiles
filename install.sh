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
      shadowed+=("$target (shadows ${lang_dir%/})")
      continue
    fi
    ln -s "${lang_dir%/}" "$target"
  done
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
for dir in "$CLAUDE_DIR"/agents "$CLAUDE_DIR"/skills "$CLAUDE_DIR"/commands "$CLAUDE_DIR"/scripts/hooks "$CLAUDE_DIR"/rules "$BIN_DIR"; do
  [ -d "$dir" ] || continue
  for link in "$dir"/*; do
    [ -L "$link" ] || continue
    if [ ! -e "$link" ]; then
      stale+=("$link -> $(readlink "$link")")
    fi
  done
done

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
