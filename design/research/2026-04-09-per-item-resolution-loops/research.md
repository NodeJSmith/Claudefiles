---
topic: "Per-item interactive resolution loops without batch collapse"
date: 2026-04-09
status: Draft
---

# Prior Art: Per-Item Interactive Resolution Loops Without Batch Collapse

## The Problem

When a workflow produces N independent decisions (findings from adversarial review, lint errors, failed audit items, rebase commits, etc.) and each needs per-item judgment, the interface wants to collapse into an "accept all?" binary. Humans do it because clicking 15 prompts is tedious. LLMs do it harder, because they have an efficiency prior and a documented tendency to resolve multi-turn state into single turns.

We have a challenge/findings skill where the rule says "present each judgment call, collect the user's choice, then move to the next question." In practice the LLM routinely bundles 7-11 unrelated findings into a single `Accept all?` binary prompt. The abstract "each" language in the rule is not winning against the model's efficiency prior.

## How We Do It Today

`rules/common/findings.md` prescribes a two-phase handoff: (1) Proceed Gate ("Proceed to fix all findings?" Yes/No), then (2) "present each judgment call, collect the user's choice, move to the next." The rule is prescriptive but abstract — it doesn't specify *how* the per-finding prompt should be structured, doesn't enumerate the bundling anti-pattern, and doesn't cap how many findings can share one AskUserQuestion call. `mine.challenge` Phase 4 simply delegates to this rule. The per-finding data in `findings.md` has `options` and `recommendation` fields that *could* populate a per-finding prompt, but there's no structural push to do so — the skill reads findings.md and renders one big block. The closest enforcement language in the repo is `rules/common/interaction.md`'s "AskUserQuestion Blocks in Skills (CRITICAL)" section, which works — it names failure modes verbatim ("Do not render options as bullet points," "Respect the option count"). findings.md has no equivalent prescriptive force.

## Patterns Found

### Pattern 1: Position Counter + Single Verb Per Item

**Used by**: `git add -p`, `git rebase -i`, lazygit, Magit, gh-triage

**How it works**: Fixed prompt format `(N/M) <what> [verbs]?` — `N/M` grounds the user in "which of how many." Each verb is a single keystroke. The user sees one item at a time, decides, advances. An "apply to all remaining" verb exists but is an explicit escape hatch (`a` in `git add -p`), not the default.

The prompt itself is the state machine — there's no "decide all" button visible, only position-ticking progress.

**Strengths**: Very low friction per decision; position counter creates momentum; bulk escape is explicit opt-in, not default.
**Weaknesses**: Fatigue past ~30 items; needs escape valves for nuance beyond the fixed verb set.
**Example**: https://www.man7.org/linux//man-pages/man1/git-add.1.html

### Pattern 2: Editable Decision Manifest

**Used by**: `git rebase -i` (via `GIT_SEQUENCE_EDITOR`), lazygit (layered on top), npm RFC #18 `audit-resolve.json`, Claude Code Plan Mode

**How it works**: Instead of a real-time per-item loop, write every item to a file with a default verb next to each line. The user opens the file in their editor, changes verbs per line as needed, saves, and the tool executes the manifest. Decisions are durable, resumable, and auditable.

The key insight: per-item discipline doesn't have to be enforced in a prompt loop — it can be enforced by the format of a document the user must review. If the format is "one line per item," the user physically sees every item.

**Strengths**: Scales to 100+ items; resumable; no interactive UI; user sets their own pace.
**Weaknesses**: Requires editor context switch; "save to approve all defaults" is possible if defaults are permissive.
**Example**: https://git-scm.com/docs/git-rebase

### Pattern 3: Tool-Enforced Chunking (Structural Cap)

**Used by**: Anthropic Claude Code `AskUserQuestion` (1-4 questions, 2-4 options each)

**How it works**: Instead of instructing the LLM to be disciplined, the tool contract caps how many items can be bundled into a single call. If the model wants to ask about 15 findings, it *must* emit 4+ tool calls. The cap is small enough that bundling unrelated items into one call is obviously incorrect.

This flips the problem: rather than telling the model "present each finding separately" (which the model rationalizes around), the tool shape makes bundling impossible. The discipline lives in the API, not the prompt.

**Strengths**: Cannot be rationalized around; enforced without the model needing to "want" to comply; explicit in the schema.
**Weaknesses**: Requires control over the tool surface; cap must be chosen carefully; only helps if the tool is actually used (the model can still inline questions as text).
**Example**: https://github.com/Piebald-AI/claude-code-system-prompts/blob/main/system-prompts/tool-description-askuserquestion.md

### Pattern 4: Group By Kind, Decide Per Group

**Used by**: mizdra/eslint-interactive, VS Code issue triage, Kubernetes triage SOPs

**How it works**: When raw item count is unworkable (500 lint errors), group by rule/kind/category first, then make one decision per group that applies to every item in the group. The user sees ~10 groups instead of 500 items but still makes N>1 decisions — the batch is scoped to a *semantically meaningful slice*, not "everything."

**Strengths**: Scales; groups carry intent; avoids fatigue.
**Weaknesses**: Only works when items naturally cluster; can still hide individual items that should be treated differently; grouping itself is a judgment call.
**Example**: https://github.com/mizdra/eslint-interactive

### Pattern 5: Plan / Execute Phase Split

**Used by**: Aider architect mode, Claude Code Plan Mode, Cline plan-then-act

**How it works**: Two explicit phases. Phase 1 (plan) is read-only — the model produces a structured proposal, the user reviews once. Phase 2 (execute) runs the plan with per-action permission checks. Per-item discipline shifts from "approve each finding as we resolve it" to "review the full plan once, then approve each resolution as it happens."

Two granularities of gate: holistic plan review (coarse, where judgment lives) followed by per-action execution gates (fine, safety rails).

**Strengths**: Concentrates judgment at one well-lit moment; reduces fatigue; plan is a durable artifact.
**Weaknesses**: If the plan is wrong, caught late; "approve all" pressure shifts to the plan review step.
**Example**: https://aider.chat/docs/usage/modes.html

### Pattern 6: Named Anti-Pattern Catalog in Prompt

**Used by**: Claude Code BashTool (~6,500 tokens of anti-patterns), Anthropic production agents, `rules/common/interaction.md` in this repo

**How it works**: Rather than abstract rules like "present each item separately," the prompt enumerates specific failure modes by name with concrete examples of the wrong behavior. Each anti-pattern has a label, a "looks like this" example, and a "do this instead" example.

The theory, backed by practitioners: LLMs rationalize around abstract rules ("this is efficient, surely the user meant...") but have a harder time rationalizing around a named failure mode they just read. "Batch collapse" as a named concept is stickier than "present each separately."

**Strengths**: Concrete; hard to rationalize around; accumulates institutional knowledge; extensible.
**Weaknesses**: Grows monotonically — prompts balloon, and IFScale shows instruction-following drops as instruction count grows.
**Example**: https://github.com/Piebald-AI/claude-code-system-prompts

## Anti-Patterns

- **"Accept all" as default with per-item as opt-in** — `npm audit fix` and early LLM coding tools. Dan Abramov's critique ([overreacted.io/npm-audit-broken-by-design](https://overreacted.io/npm-audit-broken-by-design/)) nails it: when bulk is default and per-item is extra effort, judgment evaporates. This is *structurally indistinguishable* from what the challenge skill is doing today.
- **Abstract "each" language without structural enforcement** — IFScale and related research show instruction-following degrades with prompt density. Abstract "each" can be rationalized as "I presented them in a list." Without a structural cap or a concrete anti-pattern, the model collapses to the easier path.

## Research Findings (highly relevant)

Three papers change how we should think about this:

1. **"How Many Instructions Can LLMs Follow at Once?" (IFScale, arXiv 2507.11538)** — Instruction-following degrades predictably as density grows. Frontier models hit 68% at max density. **Implication**: stuffing more discipline into a single prompt has sharply diminishing returns. The fix is structural.

2. **"When Instructions Multiply" (arXiv 2509.21051)** — Performance "consistently and drastically degrades as instruction count increases" across 10 SOTA models. Robust pattern across vendors.

3. **"LLMs Get Lost in Multi-Turn Conversation" (arXiv 2505.06120)** — 39% performance drop in multi-turn settings. Root cause: premature assumptions, attempting full solutions before all info arrives. **Implication**: the "efficiency prior" causing batch collapse is partly a *coping strategy* for a real weakness — models are bad at holding state across turns, so they resolve everything in one turn.

The research collectively argues: **you cannot fix this with more prose rules**. Adding anti-pattern tables helps at the margin, but the high-leverage fix is structural — tool-enforced chunking, per-finding durable state, or breaking each decision into its own turn via prompt chaining.

## Relevance to Us

Mapping patterns to our constraints:

| Pattern | Fit for challenge skill? |
|---|---|
| **1. Position Counter** | Very high. Maps directly to "Finding N/M" in each AskUserQuestion call. Low implementation cost — just requires the LLM to loop and include `(3/7)` in the header. |
| **2. Editable Decision Manifest** | High. `findings.md` could ship with a **resolution block** per finding the user edits (or a sibling `resolutions.md`). This shifts per-item discipline from prompt loop to document format. Scales to 30+ findings without fatigue. Matches how mine.challenge already writes findings.md as a durable artifact. |
| **3. Tool-Enforced Chunking** | Partial. AskUserQuestion already caps at 4 questions per call — we're under-using this. We can emit one AskUserQuestion per finding (current behavior is 1 question with 7 bundled in the text). No schema change needed, just discipline. |
| **4. Group By Kind** | Situational. Could group findings by severity or by `type` tag. But grouping here is exactly what the LLM is already doing wrong — we'd need to be careful it doesn't become permission for "all HIGHs in one prompt." |
| **5. Plan/Execute Split** | Already half-implemented. Challenge produces findings (the plan), resolution is execution. The gap: we're trying to do per-finding judgment *during* execution instead of during plan review. |
| **6. Named Anti-Pattern Catalog** | Must-have companion. findings.md needs an anti-pattern block like interaction.md's "AskUserQuestion Blocks (CRITICAL)" with verbatim examples of bundling and a forbid-list. Not sufficient on its own (per IFScale) but necessary. |

## Recommendation

**Use a layered fix — prose rules alone will not work** (the research is explicit). In priority order:

1. **Primary fix: Editable Decision Manifest (Pattern 2)** — the highest-leverage structural change. Before the resolve loop starts, challenge writes a `resolutions.md` file listing every user-directed finding with a default verb (`fix` / `file` / `defer`) and the recommended option pre-selected. The user edits it once (open in an editor, or via a structured Edit call), saves, and the skill executes the manifest. This scales to 30+ findings without fatigue, matches the git-rebase-todo pattern the user is already familiar with, and *structurally* prevents bundling because there's no prompt loop at all — the manifest is the review surface. This is where I'd put the most design effort.

2. **Secondary fix: Named Anti-Pattern Catalog (Pattern 6)** — `findings.md` gets an AskUserQuestion Blocks-style section. It enumerates the exact bundling failures we caught in the logs ("Do not bundle N findings into one `Accept all?` prompt", "Do not use multi-select to mean fix-vs-file") with verbatim good/bad examples. This is cheap to add and necessary as defense-in-depth even if we adopt the manifest.

3. **Fallback if manifest is too invasive: Position Counter (Pattern 1) + Tool-Enforced Chunking (Pattern 3)** — If we keep the prompt-loop model, mandate `(N/M)` in every AskUserQuestion header and emit exactly one question per AskUserQuestion call. Combined with the anti-pattern catalog, this is the minimum viable fix. It retains the fatigue problem for 20+ findings but solves the bundling problem.

**Explicitly reject**: Pattern 4 (Group By Kind) — the LLM is already doing this wrong (grouping findings into "MEDIUM batch 1/2/3"). Formalizing grouping legitimizes the failure. Pattern 5 as a standalone — we already have this structure and it's not helping.

## Sources

### Reference implementations
- https://www.man7.org/linux//man-pages/man1/git-add.1.html — `git add -p` hunk interface
- https://git-scm.com/docs/git-rebase — `git rebase -i` todo-list manifest
- https://github.com/jesseduffield/lazygit/wiki/Interactive-Rebasing — lazygit per-commit verbs
- https://github.com/mizdra/eslint-interactive — eslint-interactive group-by-rule
- https://github.com/cline/cline — Cline per-action permission
- https://github.com/k1LoW/gh-triage — gh-triage per-notification loop
- https://github.com/Piebald-AI/claude-code-system-prompts — Claude Code production prompts with anti-pattern catalogs

### Blog posts & writeups
- https://overreacted.io/npm-audit-broken-by-design/ — Dan Abramov's "accept all" critique
- https://dev.to/krnsk0/a-thorough-introduction-to-git-s-interactive-patch-mode-4bl6 — git patch mode intro
- https://nuclearsquid.com/writings/git-add/ — `git add --patch` UX breakdown
- https://www.prompthub.us/blog/why-llms-fail-in-multi-turn-conversations-and-how-to-fix-it — practitioner mitigation
- https://forum.cursor.com/t/can-we-turn-off-accept-reject-step/120192 — Cursor gate debate

### Documentation & standards
- https://docs.magit.vc/magit/Staging-and-Unstaging.html — Magit hunk staging
- https://github.com/npm/rfcs/pull/18 — npm audit-resolve.json RFC
- https://aider.chat/docs/usage/modes.html — Aider architect/editor split
- https://cursor.com/help/ai-features/tab — Cursor multi-granularity accept
- https://www.datacamp.com/tutorial/claude-code-plan-mode — Claude Code Plan Mode
- https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents — Anthropic prompt chaining guidance
- https://www.kubernetes.dev/docs/guide/issue-triage/ — k8s human triage SOP
- https://github.com/microsoft/vscode/wiki/Issues-Triaging — VS Code triage wiki

### Research papers
- https://arxiv.org/html/2507.11538v1 — IFScale (instruction density degradation)
- https://arxiv.org/html/2509.21051 — When Instructions Multiply
- https://arxiv.org/pdf/2505.06120 — LLMs Get Lost in Multi-Turn Conversation
- https://www.mdpi.com/2079-9292/14/21/4349 — Multi-task prompting degradation
