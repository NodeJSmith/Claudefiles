# Research: Claude Code Skills & Context Engineering Improvements

## Context

You browsed ~26 Claude Code-related bookmarks (blog posts, GitHub repos, X posts, arxiv papers) covering skills, memory, context engineering, and best practices. This plan synthesizes what's worth adopting into your already-sophisticated Claudefiles setup.

---

## Bookmark Inventory

| # | Bookmark | What It Discusses | Relevance | Recommendation |
|---|----------|-------------------|-----------|----------------|
| 1 | [pilot-shell](https://github.com/maxritter/pilot-shell) | Production dev environment for Claude Code: enforced TDD, context preservation before compaction, smart model routing (Opus for planning, Sonnet for implementation), `/learn` command | **HIGH** | Adopt context preservation before compaction pattern; consider `/learn`-style auto-capture |
| 2 | [Skill Graphs > SKILL.md](https://x.com/arscontexta/status/2023957499183829467) (X post, Heinrich) | Proposes skill graphs as superior to flat SKILL.md files — skills as nodes with typed edges (depends_on, triggers, feeds_into) | **MEDIUM** | Interesting architecture direction but premature for your setup; revisit if skill count exceeds ~50 |
| 3 | [arscontexta](https://github.com/agenticnotetaking/arscontexta) | Claude Code plugin generating individualized knowledge systems from conversation; 6-Rs pipeline (Record/Reduce/Reflect/Reweave/Verify/Rethink); research-backed vault design | **MEDIUM** | The 6-Rs pipeline is a useful mental model; your shodh-memory + auto-memory already covers this functionally |
| 4 | [Agent-Skills-for-Context-Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering) | 13 skills across 5 categories teaching context optimization; attention mechanics > raw token capacity; BDI (Belief-Desire-Intention) modeling | **MEDIUM** | Core insight (attention mechanics as the real constraint) could inform how you structure agent prompts and long rules files |
| 5 | [Context Engineering Skills 10x'd](https://x.com/koylanai/status/2005827257458131321) (X post, Muratcan Koylan) | Promotional post for #4 above; "Personal OS" folder-based architecture for managing personal brand, content, voice | **LOW** | Marketing fluff for the repo above; skip |
| 6 | [memU](https://github.com/NevaMind-AI/memU) | Memory system for 24/7 proactive agents; event-driven memory with decay and consolidation | **LOW** | Less sophisticated than your shodh-memory; the decay/consolidation concept is already in your auto-memory type system |
| 7 | [TDD Skill for Claude Code](https://www.aihero.dev/skill-test-driven-development-claude-code) | One-test-at-a-time vertical slicing; RED phase enforcement prevents bulk test-writing that verifies imagined behavior | **HIGH** | Your orchestrate skill uses TDD but doesn't enforce one-test-at-a-time; adopt this constraint in tdd.md |
| 8 | [Ralph Loop setup](https://x.com/d4m1n/status/2026032801322356903) (X post, Dan) | Multi-agent loop orchestration pattern for long-running agents | **LOW** | Already covered by your orchestrate + agents system |
| 9 | [Garry Tan's mega-plan](https://gist.github.com/garrytan/120bdbbd17e1b3abd5332391d77963e7) | Plan-review framework with 3 modes (EXPANSION/HOLD SCOPE/REDUCTION); 10 mandatory review sections; "zero silent failures" discipline; ASCII diagrams required | **HIGH** | Enhance plan-review with scope mode selection and broader checklist; "zero silent failures" principle for code-reviewer |
| 10 | [Garry's plan-exit-review](https://gist.github.com/garrytan/001f9074cab1a8f545ebecbc73a813df) | Structured review: scope challenge step, interactive halting with AskUserQuestion, DRY enforcement, failure mode enumeration, "NOT in scope" tracking | **HIGH** | Add scope-challenge step to implementation-review; adopt "NOT in scope" tracking in design docs |
| 11 | [Everything is Context](https://arxiv.org/abs/2512.05470) (arxiv paper) | Unix "everything is a file" abstraction applied to context; 3-stage pipeline (Constructor/Loader/Evaluator); human-as-curator emphasis | **LOW** | Academic validation of your approach; no actionable changes |
| 12 | [Codified Context Infrastructure](https://arxiv.org/abs/2602.20478) (arxiv paper) | Hot-memory constitution + cold-memory knowledge base + specialized agents; tested on 108K-line system across 283 sessions | **LOW** | Validates your constitution.md + shodh-memory + agents architecture; confirms you're on the right track |
| 13 | [Seeing like an Agent](https://x.com/trq212/status/2027463795355095314) (X post, Thariq from Anthropic) | Claude Code team philosophy on agent design; lessons from building Claude Code itself | **LOW** | FYI reading only; no specific actionable techniques |
| 14 | [ralph for idiots](https://x.com/agrimsingh/status/2010412150918189210) (X post, agrim singh) | Beginner-friendly explanation of the Ralph loop pattern for long-running agents | **LOW** | You already have this pattern; skip |
| 15 | [Skills-4-SE](https://github.com/ArabelaTso/Skills-4-SE) | Curated list of 180+ Claude skills across 8 packs (bug fixing, code quality, testing, requirements, code understanding, DevOps, formal verification, security) | **MEDIUM** | Browse for specific gaps; metamorphic testing and formal verification packs may have novel ideas |
| 16 | [visual-explainer](https://github.com/nicobailon/visual-explainer) | Agent skill for HTML diagrams, diff reviews, plan audits, slide decks | **DONE** | Already adopted in commit 6632e10; could enhance with more template patterns from this reference |
| 17 | [How To Be A World-Class Agentic Engineer](https://x.com/systematicls/status/2028814227004395561) (X post, sysls) | General career/mindset advice for working with AI agents | **LOW** | Motivational, not technical; skip |
| 18 | [claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice) | Meta-guidance: when to use commands vs subagents vs skills vs hooks; CLAUDE.md under 200 lines; commit hourly; multi-machine coordination via tmux + worktrees | **MEDIUM** | Useful validation; your CLAUDE.md is 114 lines (good); multi-machine coordination patterns worth noting |
| 19 | [Google Workspace CLI](https://github.com/googleworkspace/cli) | Official Google Workspace CLI with AI agent skills; alternative to gog | **MEDIUM** | You already use `gog`; evaluate if this offers better API coverage or agent integration |
| 20 | [Jack Culpan workflow prompt](https://x.com/JackCulpan/status/2029478582352003150) (X post) | Workflow orchestration rules: plan mode for 3+ step tasks; stop and re-plan on failure; verification steps in plan mode | **LOW** | You already enforce plan mode; nothing new here |
| 21 | [Beads](https://github.com/steveyegge/beads) | Git-native graph issue tracker with hash-based IDs, hierarchical tasks (epic/task/subtask), memory decay for closed tasks, JSON output for agents | **MEDIUM** | Interesting alternative to WP system but would be a major architectural change; dependency graph concept could enhance orchestrate |
| 22 | [SkillKit](https://www.agenstskills.com/docs) | Universal skill format translator (44 agents); security scanning (46+ rules); lineage tracking | **LOW** | Only useful if deploying skills across multiple AI platforms; security scanning rules could inspire skill validation |
| 23 | [context-hub](https://github.com/andrewyng/context-hub) (Andrew Ng) | CLI for curated, versioned API docs with agent learning loop (annotations, ratings); incremental fetching | **LOW** | You have Context7 MCP for library docs; this adds a learning loop but low ROI for your setup |
| 24 | [Arvid Kahl tips](https://x.com/arvidkahl/status/2031457304328229184) (X post) | "shift-tab into planning mode", "mention deep research on best practices using web search", read the plan carefully | **LOW** | You already do this; basic advice for beginners |
| 25 | [FMHY](https://fmhy.net/) | Collection of free stuff on the internet | **NONE** | Not Claude-related; tag or archive |
| 26 | [PySpark linting](https://clusteryield.app/blog/1/blog-post-1.html) | Static analysis of 5,046 PySpark projects | **NONE** | Not Claude-related; tag or archive |

---

## Non-Claude Bookmarks (also untagged, need triage)

These were in the untagged list but aren't Claude Code related:

| Bookmark | Category |
|----------|----------|
| Reddit MovieSuggestions (ftqxwwyscu8m5xj6aovcovt5) | Entertainment |
| Facebook haircut reel (jtskhc430jsslanvonq0wgjh) | Hair Inspiration (AI-tagged) |
| Reddit DataHoarder (knjue4ibzqgsecbqxtzjvmga) | Tech/Hoarding |
| soundgasm (mffmt5lo91lh9ryutdefyopx) | Adult Audio (AI-tagged) |
| rehumanize.io (tofzl5geu0tj2hvnu3nw3f8y) | AI Tools |
| Reddit Wichita (tz8ax9ilnony48oatc39z93f) | Local |
| Reddit redneckengineering (hhsp5u3e8fgz8apc6z1zu4fr) | DIY (AI-tagged) |
| Bandcamp - Blue Paintings (y2mdxemzzrxox98hlc6wnhj4) | Music (AI-tagged) |
| Reddit MovieSuggestions - character actors (gcxr121b6gpdnbcjqv1zices) | Entertainment (AI-tagged) |
| Dark Tower bookmark (l7hhprrl9yen4xddaiwzfkgy) | Fantasy (AI-tagged) |
| Reddit Baking cruffins (gxl5e62pvtze7xazi3nd2vgf) | Baking (AI-tagged) |
| Reddit AskWomenOver30 (w65hymmhein2w8rae9x2gecl) | Relationships (AI-tagged) |

---

## Prioritized Recommendations

### Priority 1: Context Preservation Before Compaction (from pilot-shell)

**Problem**: When context compaction happens, active plans, task state, and session context can be lost. Your `mine.pre-compact` command generates a `/compact` prompt but relies on the user remembering to run it.

**Recommendation**: Enhance `mine.pre-compact` to:
- Auto-save active plan state to shodh-memory before generating the compact prompt
- Include file paths of in-progress work, current WP lane states, and error file contents
- Consider a Stop hook that triggers pre-compact behavior automatically when context gets high

**Effort**: Medium | **Impact**: High

---

### Priority 2: One-Test-At-A-Time TDD Enforcement (from TDD skill blog post)

**Problem**: Your orchestrate skill's TDD enforcement reads a `tdd.md` file but doesn't prevent bulk test-writing. Agents can write 5 tests, then implement all at once — this allows "dishonest" tests that verify imagined behavior.

**Recommendation**: Update `tdd.md` (or create it if missing) to enforce:
- Write exactly ONE test
- Run it — must FAIL (RED)
- Write minimal implementation to pass ONLY that test (GREEN)
- Run all tests — must PASS
- Refactor if needed
- Repeat for next behavior

Add explicit guardrails in the executor prompt: "If you write more than one test before implementing, the spec reviewer will FAIL the WP."

**Effort**: Low | **Impact**: Medium-High

---

### Priority 3: Enhanced Plan Review (from Garry Tan's mega-plan)

**Problem**: Your plan-review has a 6-point checklist. Garry Tan's framework adds scope mode selection and a 10-section review that catches more issues.

**Recommendation**: Enhance `reviewer-prompt.md` in mine.plan-review to add:
- **Scope mode**: EXPANSION / HOLD SCOPE / REDUCTION — reviewer adjusts expectations based on mode
- **Additional review sections**: Exception handling coverage, observability/logging strategy, deployment considerations, trajectory assessment (is this design heading somewhere good?)
- **"Zero silent failures"**: Every new error path must name its exception class and handling strategy

**Effort**: Low-Medium | **Impact**: High

---

### Priority 4: Scope Challenge Step (from Garry Tan's plan-exit-review)

**Problem**: Your implementation-review checks what was built against the design, but doesn't challenge whether the scope was right in the first place.

**Recommendation**: Add a "Phase 0: Scope Challenge" to implementation-review:
- Before reviewing code quality, ask: "Does existing code already solve this? What's the minimum viable change?"
- Track "NOT in scope" items explicitly in design docs
- Require deferred work to be captured as issues or backlog items

**Effort**: Low | **Impact**: Medium

---

### Priority 5: Attention-Aware Context (from Context Engineering Skills repo)

**Problem**: Rules files total ~1,700 lines loaded into every conversation. Not all are relevant to every task. Attention degrades with context length even within the window.

**Recommendation**: Audit rules files for:
- Content that could be moved to on-demand skills (e.g., `frontend-workflow.md` only matters for UI work)
- Redundancy between rules and CLAUDE.md
- Opportunities to compress verbose examples into tighter guidance
- Consider splitting rules into "always-loaded" (core) and "loaded-on-demand" (specialized)

**Effort**: Medium | **Impact**: Medium (cumulative — every conversation benefits)

---

### Priority 6: Google Workspace CLI Evaluation (from bookmark #19)

**Problem**: You use `gog` for Google Workspace. The official `googleworkspace/cli` repo now exists with AI agent skills built in.

**Recommendation**: Run `/mine.eval-repo` on `googleworkspace/cli` to compare with `gog`. If it offers better coverage or native agent integration, consider migrating.

**Effort**: Low (evaluation only) | **Impact**: TBD

---

### Not Recommended (and why)

| Idea | Why Skip |
|------|----------|
| Beads (git-native task graph) | Major architectural change to replace WP system; low ROI vs. current spec-helper approach |
| SkillKit (cross-platform skills) | You're Claude-Code-only; adds complexity for no benefit |
| arscontexta 6-Rs pipeline | Conceptually interesting but shodh-memory + auto-memory already covers the functional need |
| Skill Graphs | Premature optimization at 32 skills; revisit at 50+ |
| memU memory system | Less capable than what you have |
| context-hub | Context7 MCP already solves this |

---

## Suggested Karakeep Triage

After this research, tag the bookmarks:

- **"Claude Code"** tag for all 24 relevant bookmarks (#1-#24)
- **"Adopted"** tag for visual-explainer (#16) — already implemented
- **"Worth Implementing"** tag for #1 (pilot-shell), #7 (TDD skill), #9 (Garry mega-plan), #10 (Garry plan-exit-review)
- **"Reference"** tag for #4, #11, #12, #15, #18 — useful to revisit but no immediate action
- Leave non-Claude bookmarks for separate triage

---

## Execution Order

If you want to implement the recommendations:

1. **Priority 2** first (TDD enforcement) — lowest effort, immediate quality improvement
2. **Priority 3** next (enhanced plan review) — low-medium effort, high impact on design quality
3. **Priority 4** (scope challenge) — quick addition to implementation-review
4. **Priority 1** (context preservation) — medium effort but highest long-term value
5. **Priority 5** (attention-aware context) — audit and compress rules files
6. **Priority 6** (Google CLI eval) — opportunistic, do when relevant
