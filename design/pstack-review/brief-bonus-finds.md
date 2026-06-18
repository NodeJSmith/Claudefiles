# Brief: Bonus Finds from Other Watched Repos

Source: Claude Code Digests May 25 – Jun 1, 2026  
Branch: pstack-review  
Status: Ready for pickup — lower priority than pstack items

---

## Security Hooks (haberlah/dotfiles-claude) — High Priority

Two fully novel items that plug a real gap: no local credential scanning.

**`secrets-auditor-agent`** — Haiku-powered read-only agent that scans staged diff and working tree for secrets/credentials/tokens. Groups findings by severity (Blocker/Review/Clear) with truncated snippets. Invocable on demand or pre-push.

**`pre-commit-secrets-check-hook`** — Git pre-commit shell hook blocking commits containing 30+ secret patterns (Anthropic, GitHub, Stripe, AWS, OpenAI, Slack, JWT, service-account JSON, dangerous filenames like `.env` and `id_rsa`). Scans staged diffs with grep. Truncates matched lines to avoid echoing full secrets.

**The gap:** `security.md` rule teaches defensive coding but provides no active scanning. A hook fires automatically; the agent doesn't. Both complement each other — hook is the hard gate, agent is the on-demand auditor.

**What to do:** Steal both. Hook goes in `scripts/hooks/` as a pre-commit hook; agent goes in `agents/secrets-auditor.md`. The shell-scripts-rule from the same repo (`**/*.sh` path-gated rule for safe scripting conventions) is also worth grabbing as a `rules/common/shell-scripts.md` since several local hooks are shell scripts.

---

## `anti-sycophancy-baseline` (ooloth/dotfiles) — Medium Priority

**What it does:** A CLAUDE.md-level instruction setting the system-wide behavioral baseline to challenge assumptions, offer skeptical viewpoints, correct plainly when arguments are weak, and prioritize accuracy over agreement — applied to all interactions, not just when a skill is explicitly invoked.

**The gap:** `mine.challenge` and `mine.grill` critique ideas when explicitly invoked. Day-to-day conversational responses are unconstrained. A system-level directive raises the baseline quality of all replies without requiring a skill call, particularly for quick questions and code discussions.

**Nuance:** This is a CLAUDE.md addition, not a skill. The digest notes it's "similar to mine.challenge" but they're not the same — challenge is structured multi-angle critique; this is a conversational default.

**What to do:** Add a short `anti-sycophancy` section to `rules/common/interaction.md` (or a new `rules/common/honesty.md`). "Challenge assumptions, correct plainly when arguments are weak, prioritize accuracy over agreement." Keep it short — this should be a posture, not a procedure.

---

## `discuss-strategy-skill` (ooloth/dotfiles) — Medium Priority

**What it does:** Read-only strategy validation before design or implementation. Explicitly constrained to no side effects (no edits, commits, ticket creation). Frames tradeoffs as "optimize for X vs Y". Flags reversibility (two-way vs one-way doors). Ends with a structured strategy artifact and explicit approval before recommending `/design`.

**The gap:** Local setup jumps from `mine.grill` (adversarial critique) or `mine.define` (full design doc) with nothing in between for collaborative approach validation. When you want to think out loud before committing to a design, there's no skill for that. Wasted effort from premature `/define` runs when the approach wasn't settled yet.

**What to do:** New skill at `skills/mine.discuss/SKILL.md`. Hard constraints: read-only, no side effects. Output: structured strategy artifact (approach, tradeoffs, reversibility, recommended next step). Trigger: "discuss this approach", "think through this with me", "is this the right strategy".

---

## `agent-issue-filing-budget` (ooloth/dotfiles) — Low-Medium Priority

**What it does:** Before an agent files issues from an opportunity scan, count existing open agent-authored issues (`gh issue list --label author:agent`) and apply a sliding budget: if ≥20 open, file only the single most important finding; if <20, file at most min(5, 20 − count).

**The gap:** `mine.issues-triage` and autonomous scan routines can surface many findings per run. With repeated scans, agent-authored issues can pile up faster than they're triaged. The budget gate keeps volume manageable.

**What to do:** Add budget logic to `mine.create-issue` (or a pre-flight check in any autonomous issue-filing workflow). The label `author:agent` should be applied by default when Claude creates issues autonomously so the budget check works.

---

## `write-ticket-description` (ooloth/dotfiles) — Low Priority

**What it does:** Structured skill for creating GitHub/Linear/Jira tickets from scratch. Runs a duplicate-detection pass before writing. Applies a template (Why, Current state, Expected state, Starting points, QA plan, Done when). Enforces outcome-focused, verb-first titles.

**The gap:** `mine.create-issue` creates issues but doesn't enforce template quality or check for duplicates first. `issue-refiner` enriches existing issues. This covers the creation side with quality gates.

**What to do:** Enhance `mine.create-issue` with: (1) duplicate-detection pass using keyword search + semantic read of candidate bodies, (2) structured template when the issue is being created from scratch (vs. quick-file from a finding). This is an enhancement, not a new skill.

---

## Skips

- **`scan-invariants-routine`** and **`implement-ready-issues-routine`** (ooloth) — Both require cloud infrastructure for unattended scheduling. Not immediately applicable without that setup, but worth bookmarking if the VPS routine infrastructure expands.
- **`folder-structure-skill`** (citypaul) — Screaming architecture / feature-based organization. Not a current pain point; skip for now.
- **TypeScript rule** (pstack) — Already covered well by `rules/common/typescript.md`. Skip.
