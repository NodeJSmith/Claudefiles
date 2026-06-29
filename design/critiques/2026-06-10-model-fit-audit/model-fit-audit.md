# Model-Fit Audit: Claudefiles vs Opus 4.6 / Sonnet 4.6

**Date:** 2026-06-10 · **Status:** Applied same day (commits `350e407`..`2b4fe6e`, 64 files, +497/−2694). Deferred decisions are listed at the end of the session that produced this report. · **Method:** Fable 5 synthesis over a direct read of the always-loaded layer (rules, references, capabilities) plus 9 parallel Opus 4.8 batch audits covering all 58 skills, 34 support files, 20 agents, and 6 commands. Every instruction block was judged by its *delta versus what a 4.6-class model does unprompted*: counter-bias (keep), default-restating (cut), or fact/convention (keep but bare).

## Verdict

The corpus is healthier than most config repos. The backbone is genuine counter-bias material — anti-sycophancy, anti-over-engineering, evidence-before-claims, anti-AI-slop — and that content is exactly what 4.6 models need spelled out. The house style (diagnostic questions, named failure modes, "why before what") is well matched to how these models execute. "Too vague" is essentially a non-problem: only a handful of uncheckable vibe-instructions exist in the whole corpus.

The two real costs are:

1. **Default-restating concentrated in ~15 files** — textbook checklists, generic virtue lists, and worked examples that demonstrate things 4.6 does unprompted. Roughly 8–10k words recoverable across the skills/agents corpus with no behavior loss.
2. **Copy-paste duplication where a pointer would do** — the same block pasted into 2–7 files instead of referenced from one home. This is a maintenance/drift cost more than a token cost, and it has already produced one live contradiction (fonts, below).

Estimated always-loaded savings: ~1.5–2k words (~15%) per session. Estimated skills-corpus savings: ~15–20k words across the flagged files. Three correctness bugs and one behavioral contradiction were found along the way.

## Scoreboard

| Layer | Health | Main issue |
|---|---|---|
| rules/common (always loaded) | Good | invariants.md Consider tier is pure double-pay; coding-style examples demonstrate defaults |
| references/common (on demand) | Good | reliability/security carry textbook code samples |
| Agents (20) | Good | 4 files carry generic virtue filler (architect, planner, qa-specialist, sre) |
| mine.* skills | Good–Mixed | commit/PR/ship trio duplicates itself and git-workflow.md; define/gap-close carry dead weight |
| skills-impeccable | Mixed | Core (i-frontend-design + references) is excellent; 8 satellite skills are ~40–50% textbook enumeration |
| skills-cli | Good | SKILLs lean by design; cli-output/cli-affordances REFERENCEs are the default-restating ones |
| skills-memory | Good | Nothing significant |
| Commands (6) | Excellent | Tightest files in the repo |

## Bugs and Contradictions (fix regardless of the audit)

1. **Font contradiction (behavioral bug).** `i-frontend-design/SKILL.md` `<reflex_fonts_to_reject>` bans Outfit, DM Sans, Plus Jakarta, Space Grotesk. `i-frontend-design/reference/typography.md` recommends Outfit and DM Sans as the Inter replacements. The model gets opposite instructions depending on which file it reads last. Fix: remove the named-font table from typography.md; the SKILL.md selection *procedure* is the right mechanism.
2. **Hardcoded `~/.claude` paths** violate the repo's own `${CLAUDE_CONFIG_DIR:-~/.claude}` rule (CLAUDE.md): all 8 i-* skills with the MANDATORY PREPARATION block (i-audit, i-critique, i-shape, i-overdrive, i-polish, i-harden, i-optimize, i-adapt) and `mine.implementation-review/SKILL.md:76`.
3. **`agents/testing-reality-checker.md` missing `tools:` frontmatter** — every sibling declares one; this file lists its Playwright tools only in prose.
4. **`agents/engineering-sre.md` structural mislabel** — three positive communication tips ("Lead with data", "Frame reliability as investment") sit under the "Anti-Patterns — Never Do These" header.
5. **`mine.ship` Phase 2 steps are numbered 11–20** to continue mine.commit-push's 1–10 across file boundaries — fragile coupling, confusing in isolation.
6. **`rules/common/performance.md` model table staleness check** — researcher pinned to "Opus 4.6; do not upgrade without explicit approval" while Opus 4.8 is current; verify the pin is still intentional and the Haiku/Sonnet/Opus tier descriptions still reflect the lineup you run.

## Top 10 Changes, Ranked by Impact

1. **Trim the always-loaded `invariants.md` (~600–900 words).** Drop the **Consider** tier entirely — every entry restates a principle file that is itself always loaded in full, so it's pure double-pay (the Must/Should tiers earn their place as a checklist; Consider adds zero information). Tighten multi-line entries (test co-location exemption list, PySpark notes) to one line + pointer. This is the highest-value cut because it pays on every session of every project.
2. **De-duplicate the commit/PR/ship trio.** Make `mine.ship` Phase 2 delegate to `mine.create-pr` exactly as Phase 1 delegates to `mine.commit-push` (kills ~40 duplicated lines + the 11–20 numbering). Replace the triplicated task-archival block and the restated reviewer-loop/local-verification steps in commit-push and address-pr-issues with pointers to always-loaded `git-workflow.md`, keeping only the novel bits (test-presence check, atomic stage/commit/push batching, CHANGELOG ancestor-walk — keep the walk in one home).
3. **Extract shared `scope-detection.md` for mine.review + mine.clean-code.** ~600 words byte-identical except one line. `findings-protocol.md` already proves the shared-file pattern works. Same pass: point the 5 copies of the validity-assessment paragraph and the 4 copies of "How to Analyze Code / no AST parsers" at single homes (validity's canonical home already exists in findings-protocol.md).
4. **Compress the impeccable satellite checklists (~3–4k words):** i-polish (delete its verbatim 20-item duplicate checklist outright), i-harden, i-optimize, i-audit, i-critique (keep dimension #1 AI-slop detection full; collapse 2–10 to a list), i-delight, i-animate, i-clarify, i-colorize. Pattern everywhere: keep concrete tokens (OKLCH values, WCAG/CWV numbers, easing curves, routing tables) and AI-slop counter-bias; cut the design-textbook enumeration 4.6 reproduces unprompted. Then dedupe the three cross-file rules (no-bounce → i-animate owns; gray-on-color/tinted-grays → i-colorize owns; humor-only-for-non-blocking-errors → i-clarify owns).
5. **Gut the generic-virtue agents:** architect.md (~40% filler: Core Principles, Expectations, Purpose restatement, generic GFM rules, self-duplicating checklist — keep the materiality test / interface-first / failure-modes core), planner.md (delete Best Practices + Red Flags — both restate always-loaded invariants; keep explicit-dependencies + quality gates), qa-specialist.md (compress workflow ASCII + Test Quality Standards; keep severity table + anti-patterns), engineering-sre.md (textbook three-pillars/golden-signals out; fix the mislabel). Trim Identity/Personality/Experience narrative across engineering-* to one role line.
6. **mine.define diet (~800–1,000 words).** Section-presence rules are stated twice (template annotations + Phase 5 checklist items 13–21) — make one the source. Delete or extract the self-described-unreachable "On Challenge" section (~400 words; git preserves it). Trim code-example selection criteria to 2–3 lines.
7. **mine.gap-close/REFERENCE.md (~1,000+ words).** Cut the 900-word worked walkthrough to a 10-line survey-output sample; trim the five conversion patterns to one Edit example each. A 4.6 model executes five specified phases without a transcript.
8. **Orchestrate trail-logging boilerplate.** State once "any `log` call returning non-zero increments `log_failures`"; strip the suffix from ~12 call sites across SKILL.md and post-execution-pipeline.md. Zero behavior change.
9. **Compress textbook samples in the references layer:** reliability.md (retry-with-backoff implementation, transient-codes sample — keep the rules, idempotency three-questions, shared-state-elimination framing), security.md (injection examples), frontend.md (generic React sections; keep all Preact facts + the scope-before-coding workflow), coding-style.md (early-returns/variable-naming/boolean/logging examples — keep no-underscore, no-section-dividers, method-decomposition restraint), git-workflow.md ("choosing the right type" explainer → bare type list; 4.6 knows Conventional Commits cold).
10. **Single-source intra-skill repeats:** mine.brainstorm persona meta-headers (~300–400w), mine.research's three worked Motivation examples → one + "adapt to domain" (~250w), mine.prior-art's twice-defined brief schema, mockup SKILL.md's three internal forbidden-list passes → one canonical block, write-skill checklist → REFERENCE.md owns, SKILL.md names + points. Optional: collapse the verbatim Propose-Changes gate in 5 i-* files to a canonical referenced block (~120 lines), and consider merging the three small evolution rules (subtract-first, redesign-from-first-principles, outcome-oriented-execution) into one file — modest token win, fewer cross-reference hops, medium confidence.

## Always-Loaded Layer Detail (Phase 1, direct read)

**Keep as-is (counter-bias that earns every token):** verification.md, interaction.md (incl. the AskUserQuestion-blocks protocol — harness-specific and load-bearing), debugging-discipline.md, laziness-protocol.md, reader-load.md, receiving-code-review.md, autonomous-run-discipline.md, refactoring-discipline.md, encode-lessons-in-structure.md, decomposition-discipline.md, worktrees.md, command-output.md, bash-tools.md, eval-discipline.md, writing-quality.md, instruction-quality.md, dependency-injection.md, agents.md, testing.md (mostly facts + policy), typescript.md (light trim only), python.md.

**Notes:**
- `capabilities-*.md` routing tables: keep. The BLOCKING framing is real counter-bias (the model's default is to answer inline rather than dispatch). Don't thin the trigger phrases — they're the dispatch keys.
- `performance.md` agent-model list is a hand-maintained mirror of 20 files' frontmatter — exactly what encode-lessons-in-structure says to mechanize. An `agnix-check` rule (or a generator) that validates frontmatter against policy would let the prose list shrink to the policy exceptions ("pre-commit gates: do not downgrade").
- The SYNC-comment web (testing↔invariants↔implementation-review, receiving-code-review↔retry-prompt, agents PARALLEL markers — present on only 3 of the 7 files sharing the git-discovery cascade) works but is honor-system. Same encode-the-lesson opportunity: a lint that verifies SYNC-marked blocks actually match would convert instructions into structure. Low urgency.
- The evidence-first trio (verification / debugging-discipline / performance-discipline) looked like a merge candidate from the file names; on reading, each is short and domain-scoped. Keep all three separate.

## What NOT to Touch (the crown jewels)

Preserve verbatim — this is the content that most changes 4.6 behavior:

- `agents/researcher.md` Epistemics (confidence tiers, sycophancy trap, anti-rationalization)
- `agents/code-reviewer.md` LLM-Specific Smells + Lead-Judgment Self-Check
- `references/common/receiving-code-review.md` + `mine.orchestrate/retry-prompt.md` (SYNC pair)
- `mine.orchestrate/spec-reviewer-prompt.md` default-to-FAIL posture
- `mine.build` routing/execution Rationalization tables
- `mine.debug` Red Flags / Rationalizations table
- `i-frontend-design` font-selection procedure, absolute bans, theme worked examples; `reference/anti-patterns.md` in full
- `agents/secrets-auditor.md` and `cli-harden/REFERENCE.md` (the two model citizens: bare facts + one counter-bias section)
- The reviewer fleet's lane-boundary blocks ("this is X's job, not mine") — that's fleet coordination, not redundancy
- Per-subagent repetition of format contracts and test-discovery (subagents run in fresh contexts; the repetition is the delivery mechanism)
- Calibration exemplars to imitate when writing new skills: `mine.grill`, `mine.how`, `commands/mine.status`, `mine.challenge/caller-protocol.md`

## Niche Questions Answered

- **Research cluster (brainstorm/grill/research/prior-art):** all four earn distinct niches; the "How This Differs" tables actively prevent collision. No merges.
- **Single-focus i-* skills:** all earn their existence on counter-bias grounds (i-typeset, i-layout, i-colorize, i-bolder, i-quieter strongly; i-animate/i-delight/i-distill after trimming). Weakest: i-clarify — would survive as a ~400-word skill (empathy/humor rule + two examples + gate).
- **cli-* split (5 + audit aggregator):** well-designed; thin standalone SKILLs with content in on-demand REFERENCEs is the right shape.
- **mine.debug vs debugging-discipline.md:** justified overlap — the rule states the principle, the skill operationalizes it as gated phases; only the step-level "why" prose re-explaining reproduce-first is compressible.

## Suggested Execution Order

1. Bugs first (font contradiction, `${CLAUDE_CONFIG_DIR}` paths, tools: frontmatter, sre mislabel) — small, unambiguous, immediate.
2. Always-loaded trims (#1, #9-rules-parts) — pays every session.
3. Structural dedup (#2, #3, #8) — kills drift risk; behavior-neutral.
4. Bulk compressions (#4, #5, #6, #7, #10) — biggest word counts, most judgment; reviewable file-by-file.
5. Optional mechanization (agnix-check rules for model policy + SYNC verification).

A borderline-case caveat: document review can confidently identify restatement and duplication, but "does this rule still change behavior at 4.6?" is ultimately behavioral. The cuts above are high-confidence (textbook content, verbatim duplicates, dead sections). Anything marked medium/low confidence in the batch outputs — and the deliberate-redundancy keeps — would need an A/B eval (`/mine.mutation-test`-style, per eval-discipline.md) to relitigate.
