# Brief: Extract claude-memory into a Standalone Repo + Claude Code Plugin

**Date:** 2026-06-13
**Status:** explored

## Idea

`packages/claude-memory` was inherited wholesale (copied from an unremembered source,
never vetted). Now that it has semantic (vector) search layered on top of FTS, the
goal is to extract it into its **own repository and publish it as a Claude Code
plugin** — a real, supported product, because the author dogfoods it daily. The
modernization that triggered this exploration (cyclopts migration, package-wide
logging, `--json` everywhere) is real but has been correctly **demoted to polish that
comes after extraction and after the central format-coupling risk is settled**.

The session started from a small papercut — no way to see embedding-backfill progress
or a done/total count — and grew into the platform decision above. The small fix still
exists underneath and can be handled independently (see Scope).

## Key Decisions Made

- **Real goal = platform, not cleanup.** Extract to a standalone repo and ship as a
  Claude Code plugin. Semantic-search-on-FTS is what makes it worth publishing.
- **Sequence = extract first.** Spin out the standalone repo + plugin manifest +
  its own CI/tests/packaging BEFORE doing cyclopts/logging/`--json`, so that rewrite
  lands in its real home and isn't done twice. In-place-then-rehome was rejected.
- **Posture = real product, supported.** Author relies on it daily, so it gets
  support. This sets a high bar: graceful degradation, DB-migration safety, docs,
  versioning discipline. Cyclopts/logging are explicitly "the least of it."
- **Output contract = `--json` is primary, not secondary.** The package is almost
  entirely machine/Claude/hook-facing (see Codebase Context), so structured output +
  stdout/stderr discipline + stable exit codes matter more than human-UX polish
  (color, tables, progress bars are mostly misapplied here).
- **Observability is the real prize of the "logging" workstream.** Current logging is
  a single flat `claude-memory` logger gated behind `logging_enabled=False`
  (NullHandler), exercised by only 6/15 modules, and fully blind on the
  background-spawn path (stderr → DEVNULL). Background jobs must leave a trail.
- **Format-drift defense is unresolved and gated on prior-art research** (see Open
  Questions) — do not pick an architecture by guessing.

## Open Questions

1. **[#1 — RESOLVED via prior-art, 2026-06-13] How do existing Claude Code
   memory/transcript plugins survive Anthropic changing the transcript/slug/hook
   format?** Full survey at
   `design/research/2026-06-13-claude-code-transcript-format-drift/research.md`.
   Findings (these are now design inputs, not open questions):
   - **No official conversation-history API exists.** The dependency is unavoidable;
     only the hook payload's `transcript_path` is a documented/sanctioned door, and it
     hands you the file path but documents no schema for the contents.
   - **Consensus architecture = ONE schema/parser boundary** (ccusage/valibot,
     claude-code-log/Pydantic). Our parsing is only moderately centralized today — the
     bar is one Pydantic `models.py`+parser that all ~10 call sites route through.
     Closest template: claude-code-log.
   - **Highest-value de-risk we're not using:** take the transcript path from the hook
     payload instead of hand-rolling the cwd→slug decode. The `/`→`-` scheme is
     acknowledged-buggy (collisions, issue #7009) and slated to change; our
     `token_parser._decode_project_cwd` inherits the bug now and breaks on the fix.
     Move live ingest to `transcript_path`; keep slug-decode only for historical crawl,
     isolated behind the boundary and labeled fragile.
   - **Deliberate divergence from prior art (our differentiator):** every surveyed tool
     silently skips unrecognized lines — fine for analytics, data-loss for *memory*.
     Count + surface unrecognized lines with a drift warning at a threshold, and refuse
     to mark a branch "fully ingested" when the unrecognized ratio spikes. Capture the
     per-line `version` field for the signal without branching on it.
   - **Drift is real and lands at patch granularity** (dir move; 2.0.77 TaskOutput
     regression #17591/#20531; #60090) — budget reactive schema patches as ongoing
     maintenance, made cheap by the single boundary.
   - **Naming:** "claude-memory" as the public product name is the riskier path
     (CLAUDE is registered, #7645254). Validated pattern (ccusage) = non-"claude"
     product name + "for Claude Code" descriptor + "not affiliated" disclaimer.
2. **Repo boundary / what moves.** Extraction is package **+** skill bundle
   (`cm-recall-conversations`, `cm-get-token-insights`, the recall agent,
   `capabilities-memory.md`) **+** hook declarations (today hand-wired in
   `~/Claudefiles/settings.json`, must move into a plugin manifest). Confirm the full
   inventory of what leaves Claudefiles.
3. **Don't break the author's daily memory during the transition.** It's a live
   dependency every session (recall, context injection, handoffs) over a 797 MB DB
   with 1900+ branches. Need a transition plan where Claudefiles consumes the
   extracted plugin instead of the vendored package, with no data-loss window.
4. **DB schema becomes a public contract.** Once strangers have DBs, schema changes
   need forward migrations that can't lose data. A prior `pre-v4` migration already
   happened (backup file exists), so migrations are real — formalize the story.
5. **Naming / trademark.** Prior-art confirms the validated pattern: non-"claude"
   product name + "for Claude Code" descriptor + "not affiliated" disclaimer (ccusage).
   **Proposed name: `ccm` (claude code memory)** — short binary, and the literal string
   avoids "claude," which sidesteps the trademark concern (CLAUDE reg. #7645254). Pairs
   naturally with the single-entry-point decision below (`ccm sync`, `ccm search`,
   `ccm backfill embeddings`, `ccm status`). Confirm `ccm` isn't already taken on PyPI /
   a common binary-name collision before committing.
6. **Consolidation before publish.** Three overlapping conversation-read entrypoints
   (`cm-recent-chats` / `cm-search-conversations` / `cm-session-tail`) and the orphan
   `cm-backfill-embeddings`. Trim/merge the public surface BEFORE it becomes a
   supported contract, not after.

## Scope Boundaries

**In (the platform play):**
- Extract to standalone repo with own CI/tests/packaging.
- Plugin manifest + hook declarations + bundled skills/agent.
- Format-coupling architecture (pending prior-art).
- Then: cyclopts migration, logging/observability overhaul, `--json`-primary output.
- DB-as-public-contract migration discipline.

**Out / deferred:**
- Human-UX polish (rich tables, color, narrow-terminal handling) — misaligned with a
  machine-facing surface; do only where a genuinely human-invoked path exists
  (`cm-recent-chats`).
- Building the full adapter before prior-art says what shape it should be.

**Independent / can ship now if desired:** the ORIGINAL embeddings papercut — a
status/progress reader (done vs eligible vs total, reusing `build_selection()` so the
predicate has one source of truth), a `--progress-every N` cadence flag + up-front
total + elapsed/ETA, and surfacing the orphan in a hook (like `onboarding.py` already
prints "run `cm-write-config`") so Claude can offer to kick it off. Cheap to re-home
later; resolves the immediate itch without waiting on the extraction.

## Feature Ideas (backlog — captured 2026-06-14)

Each tagged with verification against current code so `/mine.define` doesn't re-spec
things that already exist.

1. **Disable auto import/sync (config flag).** Let a user turn off the SessionStart
   import crawl and the Stop-hook sync so they can drive ingest from their own cron job
   / systemd timer instead. **New.** Fits the existing `config.json` pattern (alongside
   `logging_enabled`). Cheap; just gate the `_spawn_background` calls in `memory_setup`
   and the Stop-hook sync on a config key.

2. **Skill-invocation tracking (new table).** Record which skills/commands fire per
   session. **New domain** — sits alongside the existing `token_snapshots` telemetry but
   is distinct. Needs a data source: skill invocations would have to be parsed from the
   transcript JSONL (so it rides on, and is exposed to, the same format-drift boundary
   from Open Q #1) or captured via a dedicated hook. Decide the source during define.

3. **Missing-session alerting/tracking.** *Partially implemented already.* The
   SessionStart `cm-import-conversations` crawl globs every `*.jsonl` and hash-dedups via
   `import_log`, so a session whose Stop hook never fired (fatal crash) is **silently
   backfilled on the next session.** What's genuinely **new = surfacing it**: flag when a
   session was recovered-late via crawl rather than synced-live via Stop, since that gap
   is itself the signal of a fatal failure. Reframe from "detect missing sessions" to
   "alert on late-recovered sessions."

4. **Alternative backend (Postgres).** Explicitly **v2/v3, deferred.** Hard gate:
   feature parity for the two things sqlite gives us today — vector search (sqlite-vec →
   would need `pgvector`) and FTS (FTS5 → `tsvector`/GIN). Only worth it if a real
   multi-machine/shared-DB use case appears; for a single-user local plugin, sqlite is
   the right default. Keep the one schema boundary clean enough that the backend is
   swappable, but don't build for it now.

5. **Mid-conversation DB updates.** *Largely already implemented.* The Stop hook fires
   `cm-memory-sync` after **every assistant turn**, not once at session end — so the DB
   is already updated incrementally throughout the conversation. The only uncovered case
   is an in-flight turn that dies before Stop fires, which is exactly idea #3's
   territory. **Recommendation: drop as a standalone feature**; the residual benefit is
   already covered by late-recovery surfacing. Re-open only if there's a concrete benefit
   to sub-turn (streaming) sync, which is not evident.

6. **Single entry point with subcommands.** **This is the shape of the cyclopts phase,
   not a separate feature.** Collapse the 14 binaries into `ccm <command>` (root `App` +
   sub-`App`s, per the hassette reference). Consequence to design: the hook entrypoints
   become subcommands too (`ccm hook session-start`, `ccm hook stop`, …) and the plugin
   manifest declares those — which tidies the "hooks move from settings.json to the
   manifest" extraction step. Cross-references the cyclopts work in Scope/In.

7. **Cap embedding `--threads` to a conservative ceiling (v2).** `cm-backfill-embeddings
   --threads` currently accepts any int and sets onnxruntime intra+inter-op threads to
   it. On the 8-core VPS, `--threads 16` ran the int8 bge-m3 backfill ~15× slower than
   `--threads 1–2` (measured: oversubscription thrashes a memory-bandwidth-bound model;
   2 threads is already faster than 16). Embed time is dominated by summary length
   anyway (superlinear: ~0.5s at 450 chars, ~8s at 4.7k, ~37s at 13k+), so high thread
   counts buy little and can hurt. v2: clamp `--threads` to something like
   `min(requested, cpu_count // 2)` (or just lower the ceiling/default) so a careless
   high value can't tank a nightly run. Pure usability hardening on the already-shipped
   status/progress/exit-code work — not blocking the extraction.

## Risks and Concerns

- **Foundation built on sand (central risk — now contained, not eliminated).** Core
  depends on undocumented Claude Code internals Anthropic can change without notice.
  Prior-art (Open Q #1) confirms it's unavoidable but containable: one schema boundary,
  hook-fed `transcript_path` over hand-rolled slug decode, and a memory-specific drift
  guard. Residual standing cost = reactive schema patches at patch-version cadence.
- **Double-work trap (mitigated).** Addressed by extract-first sequencing.
- **Breaking your own daily memory mid-extraction** (Open Q #3) — data at stake.
- **Support burden you're signing up for.** "Real product + daily reliance" = real
  obligation; format drift, others' DB migrations, issue triage.
- **Scope gravity.** The thing that started this (a status line) is now the smallest
  item in a multi-phase program. Keep the independent embeddings fix from being held
  hostage by the big extraction if you want near-term relief.

## Codebase Context

- **14 entrypoints, ~28 modules.** Invocation map (this session): nearly all are
  harness-hook-invoked, spawned-as-subprocess, or Claude-invoked via SKILL.md. The
  only meaningful human-typed use is `cm-recent-chats` (16× in shell history).
  `cm-backfill-embeddings` is the lone orphan — manual-only, no hook/spawn/skill
  caller. Nothing is fully dead.
- **Tests: 22 files for 28 modules.** Strong enough to serve as a refactor pin
  (refactoring-discipline) — the cyclopts migration is well-pinned, not blind.
- **Coupling is to Claude Code conventions, not to the author.** Zero `/home/jessica`
  paths, no `WHICH_COMP`/Dotfiles refs; the only `machines.md` mentions are comments.
  Uses `Path.home()/.claude` and `~/.claude-memory` — identical on every Claude Code
  user's machine. For a plugin this is the *correct* coupling, and good news for
  portability.
- **The real coupling (10+ modules):** `~/.claude/projects/<slug>/*.jsonl` transcript
  layout, slug-encoding (incl. `.claude/worktrees` handling — see `formatting.py`,
  `token_parser.py`, `session_tail.py`), and the hook-event protocol. This is the
  domain, not a liability — but it's reverse-engineered and version-unstable.
- **Packaging today:** uv tool + editable install pointing at
  `packages/claude-memory/src`, symlinks via `install.py`, hooks hand-wired in
  `settings.json`. No plugin manifest exists — the packaging-as-plugin migration is
  the largest unstarted piece and is separate from cyclopts.
- **Hook stdout protocol is sacred:** `cm-memory-setup/sync/context` print
  `{"continue": true}` / `{}` to stdout for the harness. Any output-layer migration
  must not break these.
- **Reference for the rewrite (deferred phase):** the hassette CLI
  (`~/source/hassette/src/hassette/cli/`) — root `App` + sub-`App`s + `commands/`
  modules + `@app.meta.default` launcher injecting a frozen `CLIContext(json_mode)` +
  an `output.py` render layer (`render_table`/`render_detail`/`render_raw`, each
  `json_mode`-aware, clean stdout/stderr split). It is also the best `--json`/output
  reference available, not only the cyclopts one.

## Meta: cli-audit skill gap (separate follow-up)

The `/cli-audit` run that started this surfaced logging and `--json` but scoped them
narrowly (it audits the file(s) you point it at against human-UX dimensions). It has
**no dimension for parser/implementation ergonomics** (so cyclopts could never
surface) and **no tool-family/package mode** (so cross-entrypoint consistency and
shared infrastructure — one logger, one `--json` contract, one output layer — are
invisible to it). Worth filing as a skill improvement.
