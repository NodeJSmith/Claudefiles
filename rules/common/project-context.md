# Project Context

Projects can declare structured metadata in their CLAUDE.md frontmatter that calibrates how agents assess the work. Currently wired into `mine-challenge` critic dispatch; other skills and reviewers inherit the values via CLAUDE.md context. Without this metadata, agents default to enterprise-grade advice — suggesting RBAC for a personal CLI tool, rate limiting for a self-hosted single-user app, horizontal scaling for a hobby project.

## Format

Three fields in CLAUDE.md YAML frontmatter, plus two optional ones (`peers` and `accepted-risks`, below):

```yaml
---
audience: self-hosted personal tool
developers: solo
data-sensitivity: personal
---
```

### Axes

**audience** — who uses this software. The single biggest calibration signal.
- `personal tool` — built for the developer. Enterprise patterns are overkill.
- `internal tool` — used within a team or org. Conventions matter more than polish.
- `open-source library` — external consumers exist. API stability, docs, and semver matter.
- `B2B SaaS` — production service with real users. Reliability, security, and scale matter.

**developers** — who works on this codebase.
- `solo` — one person. No code ownership boundaries, no team conventions to enforce, simpler review standards.
- `small team` — 2-5 people. Conventions and code clarity matter for shared understanding.
- `large team` — 6+ people. Strict conventions, documentation, and explicit interfaces between modules.

**data-sensitivity** — what kind of data flows through the system.
- `personal` — the developer's own data. No compliance burden; skip PII handling, audit trails, and regulatory patterns.
- `internal` — business data within an org. Reasonable security, but no regulatory burden.
- `regulated` — PII, financial, health, or other data subject to compliance requirements. Security and audit trails are non-negotiable.

### Optional: peers

```yaml
peers: AppDaemon, pyscript, Home Assistant core
```

**peers** names comparable projects: ones solving the same problem for a similar audience. Prior-art research (`mine-prior-art`, and the convergence gates in `mine-challenge` and `mine-address-pr-issues`) searches these first, so "how do others handle this?" is answered by real peers instead of generic best-practice writing, which skews toward enterprise scale. `project-meta-prompt.sh` asks for it only in public GitHub repos; private and work repos rarely have public peers to compare against. When it's absent, prior-art research picks comparable projects itself.

### Optional: accepted-risks

```yaml
accepted-risks:
  - a crash mid-run leaves partial output; rerunning fixes it
  - an expired API token fails the run; the next scheduled run retries
```

**accepted-risks** lists specific risks the project has decided to live with. Each entry names one failure, not a category. When one comes up, mention it in a sentence and don't guard against it; reviewers' findings about it are noted but aren't blocking, unless they're security findings or bugs the change introduced (item 4 below). Specific statements move agent behavior more than a general stance like `audience: personal tool`. Only the user adds entries: when you've dismissed the same risk twice, suggest one.

## How to Use It

When reviewing, challenging, or designing for a project:

1. Check the project's CLAUDE.md for frontmatter. If present, calibrate advice to match.
2. A `personal tool` with `solo` developer does not need: RBAC, rate limiting, horizontal scaling, comprehensive audit logging, multi-tenant isolation, or enterprise error handling patterns. It does need: correctness, clear code, and reasonable error messages.
3. A `B2B SaaS` with `large team` and `regulated` data needs all of those things.
4. Security findings and bugs the change itself introduces always surface regardless of project context or `accepted-risks`. For other findings that would only matter for a different audience or scale, lower their priority and name the audience assumption instead of omitting them — dropping them is a decision for whoever filters the findings downstream, not for the reviewer producing them.

## When It's Missing

Do not assume enterprise defaults when project context is absent. Look for signals in the codebase (single-user config, no auth layer, personal dotfiles patterns) before defaulting to high-rigor advice. When genuinely uncertain, ask rather than over-prescribing.
