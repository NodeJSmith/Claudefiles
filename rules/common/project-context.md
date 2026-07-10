---
tool: claude, codex, antigravity
---

# Project Context

Projects can declare structured metadata in their CLAUDE.md frontmatter that calibrates how agents assess the work. Currently wired into `mine-challenge` critic dispatch; other skills and reviewers inherit the values via CLAUDE.md context. Without this metadata, agents default to enterprise-grade advice — suggesting RBAC for a personal CLI tool, rate limiting for a self-hosted single-user app, horizontal scaling for a hobby project.

## Format

Three fields in CLAUDE.md YAML frontmatter:

```yaml
---
audience: self-hosted personal tool
developers: solo
data-sensitivity: personal
---
```

### Axes

<!-- Option labels here are duplicated in scripts/hooks/project-meta-prompt.sh — update both when changing -->

**audience** — who uses this software. The single biggest calibration signal.
- `personal tool` / `self-hosted personal tool` — built for the developer. Enterprise patterns are overkill.
- `internal tool` — used within a team or org. Conventions matter more than polish.
- `open-source library` — external consumers exist. API stability, docs, and semver matter.
- `B2B SaaS` / `consumer app` — production service with real users. Reliability, security, and scale matter.

**developers** — who works on this codebase.
- `solo` — one person. No code ownership boundaries, no team conventions to enforce, simpler review standards.
- `small team` — 2-5 people. Conventions and code clarity matter for shared understanding.
- `large team` — 6+ people. Strict conventions, documentation, and explicit interfaces between modules.

**data-sensitivity** — what kind of data flows through the system.
- `personal` — the developer's own data. No compliance burden; skip PII handling, audit trails, and regulatory patterns.
- `internal` — business data within an org. Reasonable security, but no regulatory burden.
- `regulated` — PII, financial, health, or other data subject to compliance requirements. Security and audit trails are non-negotiable.

## How to Use It

When reviewing, challenging, or designing for a project:

1. Check the project's CLAUDE.md for frontmatter. If present, calibrate advice to match.
2. A `personal tool` with `solo` developer does not need: RBAC, rate limiting, horizontal scaling, comprehensive audit logging, multi-tenant isolation, or enterprise error handling patterns. It does need: correctness, clear code, and reasonable error messages.
3. A `B2B SaaS` with `large team` and `regulated` data needs all of those things.
4. Must-tier invariants (see `invariants.md`) always surface regardless of project context — calibration adjusts framing and priority, never suppression of Must-tier items. For Should/Consider-tier findings, skip those that would only matter for a different audience or scale.

## When It's Missing

Do not assume enterprise defaults when project context is absent. Look for signals in the codebase (single-user config, no auth layer, personal dotfiles patterns) before defaulting to high-rigor advice. When genuinely uncertain, ask rather than over-prescribing.
