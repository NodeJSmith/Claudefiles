# Impeccable Skills Bundle

- **Source**: https://impeccable.style/api/download/bundle/universal-prefixed
- **Imported**: 2026-03-19
- **Skills**: 21 (i-adapt, i-animate, i-arrange, i-audit, i-bolder, i-clarify, i-colorize, i-critique, i-delight, i-distill, i-extract, i-frontend-design, i-harden, i-normalize, i-onboard, i-optimize, i-overdrive, i-polish, i-quieter, i-teach-impeccable, i-typeset)
- **Local modifications to i-* skills**:
  - Normalized `user-invokable` → `user-invocable` in all frontmatter
  - Added `user-invocable: false` to `i-frontend-design` (library skill, not directly invoked)
  - Added `design/direction.md` fallback to `i-frontend-design` Context Gathering Protocol
  - Fixed sentence fragment in `i-teach-impeccable` line 69

## Bridging modifications to mine.* skills

The following `mine.*` skills were modified to integrate with the `i-*` bundle:
- `mine.look-and-feel` Phase 7: writes `.impeccable.md` alongside `direction.md`
- `mine.build` direction check: reads `.impeccable.md` as fallback when no `direction.md`
- `mine.mockup` direction check: reads `.impeccable.md` as fallback when no `direction.md`

These are not part of the upstream bundle — they must be preserved manually when upgrading.

## Upgrade Policy

The `i-*` bundle must be upgraded as a unit — never file-by-file. Internal cross-references (every skill's MANDATORY PREPARATION calls `i-frontend-design`) require atomic updates.

To upgrade:
1. Download the latest bundle from the source URL
2. Extract the `.claude/skills/i-*` directories
3. Diff against the current `skills/i-*` to identify upstream changes
4. Reapply local modifications listed above
5. Update this file with the new import date
