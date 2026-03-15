# RTK — CLI Proxy for Token Reduction

Source: https://github.com/rtk-ai/rtk

## What It Is

Single Rust binary, zero dependencies. CLI proxy that intercepts Bash commands and rewrites them to return compressed output. Reduces LLM token consumption by 60-90%.

## How It Works

1. Registers as a PreToolUse hook in `~/.claude/settings.json` via `rtk init -g`
2. Transparently rewrites commands (e.g., `git status` → `rtk git status`)
3. Applies 4 compression strategies:
   - **Smart Filtering** — removes noise (comments, whitespace, boilerplate)
   - **Grouping** — aggregates similar items (files by directory, errors by type)
   - **Truncation** — keeps relevant context, cuts redundancy
   - **Deduplication** — collapses repeated log lines with counts
4. Returns compressed output only; <10ms overhead

## Benchmarks (30-minute session)

| Operation | Freq | Standard | RTK | Reduction |
|-----------|------|----------|-----|-----------|
| ls/tree | 10x | 2,000 | 400 | -80% |
| cat/read | 20x | 40,000 | 12,000 | -70% |
| cargo test | 5x | 25,000 | 2,500 | -90% |
| git add/commit/push | 8x | 1,600 | 120 | -92% |
| **Total** | | **118,000** | **23,900** | **-80%** |

## Supported Commands

- **File ops:** ls, read, find, grep, diff
- **Git:** status, log, diff, add, commit, push, pull
- **GitHub CLI:** pr list, pr view, issue list, run list
- **Test runners:** cargo test, npm test, pytest, go test, vitest
- **Build/lint:** TypeScript, ESLint, Biome, Prettier, Cargo, Ruff
- **Containers:** Docker, Kubernetes
- **Package managers:** npm, pip, pnpm, Cargo

## Failure Recovery

When commands fail, full unfiltered output saved locally with reference path. LLM can troubleshoot without re-executing.

## Relevance to Setup

This complements the context reduction architecture. Rules/CLAUDE.md optimization reduces *instructional* context; RTK reduces *operational* context (tool output). Together they attack both sides of context bloat.

**Potential concern:** You already have `command-output.md` rules for `| tee` + `| tail` patterns. RTK automates this at a lower level. Could conflict with or replace your existing command-output preservation workflow.

**Worth evaluating:** Install, run a session, compare token usage. The 80% reduction on tool output is significant — may matter more than rules optimization if your sessions are tool-heavy.
