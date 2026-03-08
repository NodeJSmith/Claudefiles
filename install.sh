#!/usr/bin/env bash
# Symlink Claudefiles into ~/.claude/
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="${CLAUDE_HOME:-$HOME/.claude}"
BIN_DIR="$HOME/.local/bin"

interactive=false
[ -t 0 ] && [ -t 1 ] && interactive=true

declare -A shadowed   # shadowed[$target]=$source

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
      shadowed["$target"]="$item"
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
      shadowed["$dest"]="$lang_dir"
      continue
    fi
    mkdir -p "$dest"
    for item in "$lang_dir"*; do
      [ -e "$item" ] || continue
      target="$dest/$(basename "$item")"
      if [ -L "$target" ]; then
        rm "$target"
      elif [ -e "$target" ]; then
        shadowed["$target"]="$item"
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
  skip_learned=false
  if [ -L "$dest" ]; then
    rm "$dest"   # upgrade: remove old whole-directory symlink
  elif [ -e "$dest" ] && [ ! -d "$dest" ]; then
    shadowed["$dest"]="$REPO_DIR/learned"
    skip_learned=true
  fi
  if [ "$skip_learned" = false ]; then
    mkdir -p "$dest"
    for item in "$REPO_DIR/learned"/*; do
      [ -e "$item" ] || continue
      target="$dest/$(basename "$item")"
      if [ -L "$target" ]; then
        rm "$target"
      elif [ -e "$target" ]; then
        shadowed["$target"]="$item"
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
      shadowed["$target"]="$item"
      continue
    fi
    ln -s "$item" "$target"
  done
fi

# Check for stale symlinks (point to targets that no longer exist)
stale_links=()

# Top-level dirs: agents, skills, commands, hooks, bin
for dir in "$CLAUDE_DIR"/agents "$CLAUDE_DIR"/skills "$CLAUDE_DIR"/commands \
           "$CLAUDE_DIR"/scripts/hooks "$BIN_DIR"; do
  [ -d "$dir" ] || continue
  for link in "$dir"/*; do
    [ -L "$link" ] || continue   # also skips literal "$dir/*" when dir is empty
    [ ! -e "$link" ] && stale_links+=("$link")
  done
done

# Rules: check file-level symlinks within each language subdirectory
if [ -d "$CLAUDE_DIR/rules" ]; then
  for lang_dir in "$CLAUDE_DIR/rules"/*/; do
    [ -d "$lang_dir" ] || continue
    [ ! -L "${lang_dir%/}" ] || continue
    for link in "$lang_dir"*; do
      [ -L "$link" ] || continue   # also skips literal "$lang_dir*" when dir is empty
      [ ! -e "$link" ] && stale_links+=("$link")
    done
  done
fi

# Learned: check file-level symlinks (skip if it's itself a whole-dir symlink)
if [ -d "$CLAUDE_DIR/learned" ] && [ ! -L "$CLAUDE_DIR/learned" ]; then
  for link in "$CLAUDE_DIR/learned"/*; do
    [ -L "$link" ] || continue   # also skips literal "$CLAUDE_DIR/learned/*" when dir is empty
    [ ! -e "$link" ] && stale_links+=("$link")
  done
fi

# Report problems
if [ ${#shadowed[@]} -gt 0 ]; then
  echo "" >&2
  echo "warning: ${#shadowed[@]} file(s) not symlinked — a non-symlink already exists:" >&2
  for tgt in "${!shadowed[@]}"; do
    src="${shadowed[$tgt]}"
    if [ -d "$src" ]; then
      echo "  $tgt (shadows dir $src — re-run install.sh to restore links)" >&2
    else
      echo "  $tgt (shadows $src)" >&2
    fi
  done

  if [ "$interactive" = true ]; then
    echo "  (these are real files, not symlinks — remove only if you don't need them)" >&2
    printf "  Remove and re-link? [y/N] " >/dev/tty
    read -r answer </dev/tty
    if [[ "$answer" =~ ^[Yy] ]]; then
      for tgt in "${!shadowed[@]}"; do
        src="${shadowed[$tgt]}"
        rm -rf "$tgt"
        if [ -d "$src" ]; then
          echo "  removed: $tgt (was shadowing $src — re-run install.sh to restore links)" >&2
        else
          ln -s "$src" "$tgt"
          echo "  linked: $tgt" >&2
        fi
      done
    fi
  else
    echo "  Remove the above file(s) and re-run install.sh:" >&2
    for tgt in "${!shadowed[@]}"; do
      echo "    rm \"$tgt\"" >&2
    done
  fi
fi

if [ ${#stale_links[@]} -gt 0 ]; then
  echo "" >&2
  echo "warning: ${#stale_links[@]} stale symlink(s) found (target no longer exists):" >&2
  for link in "${stale_links[@]}"; do
    echo "  $link -> $(readlink "$link")" >&2
  done

  if [ "$interactive" = true ]; then
    printf "  Remove stale symlink(s)? [y/N] " >/dev/tty
    read -r answer </dev/tty
    if [[ "$answer" =~ ^[Yy] ]]; then
      for link in "${stale_links[@]}"; do
        rm "$link"
        echo "  removed: $link" >&2
      done
    fi
  else
    echo "  Remove stale symlink(s) manually:" >&2
    for link in "${stale_links[@]}"; do
      echo "    rm \"$link\"" >&2
    done
  fi
fi

echo "Claudefiles installed to $CLAUDE_DIR"
