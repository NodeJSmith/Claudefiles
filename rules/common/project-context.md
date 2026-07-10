---
tool: claude, codex, antigravity
---

# Project Context

Projects can declare structured metadata in their CLAUDE.md frontmatter that calibrates how skills, reviewers, and critics assess the work. Without this, agents default to enterprise-grade advice — suggesting RBAC for a personal CLI tool, rate limiting for a self-hosted single-user app, horizontal scaling for a hobby project.

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
- `personal` — the developer's own data. Input validation is good practice, not a compliance requirement.
- `internal` — business data within an org. Reasonable security, but no regulatory burden.
- `regulated` — PII, financial, health, or other data subject to compliance requirements. Security and audit trails are non-negotiable.

## How to Use It

When reviewing, challenging, or designing for a project:

1. Check the project's CLAUDE.md for frontmatter. If present, calibrate advice to match.
2. A `personal tool` with `solo` developer does not need: RBAC, rate limiting, horizontal scaling, comprehensive audit logging, multi-tenant isolation, or enterprise error handling patterns. It does need: correctness, clear code, and reasonable error messages.
3. A `B2B SaaS` with `large team` and `regulated` data needs all of those things.
4. When a finding would be valid for an enterprise project but not for the declared context, skip it — do not surface it with a caveat.

## When It's Missing

Do not assume enterprise defaults when project context is absent. Look for signals in the codebase (single-user config, no auth layer, personal dotfiles patterns) before defaulting to high-rigor advice. When genuinely uncertain, ask rather than over-prescribing.

Skills that run structured discovery (like mine-define) should suggest adding project context when it's missing.
