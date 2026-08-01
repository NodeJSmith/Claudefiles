---
topic: "Shell/transcript command pattern mining for automation"
date: 2026-07-31
status: Draft
---

# Prior Art: Mining Command History and Session Transcripts for Automation Candidates

## The Problem

Developers repeat themselves. The same `find` incantation, the same multi-step deploy dance, the same jq pipeline — run dozens of times before someone notices it should be a script. The question is how to systematically detect these patterns rather than relying on the developer to notice and act. This is especially acute in AI coding assistant workflows, where a tool-calling agent may repeat the same Bash commands across sessions without any human noticing the repetition.

## How We Do It Today

`mine-tool-gaps` is a skill that mines Claude Code session JSONL transcripts for recurring manual workarounds. It uses ad-hoc `grep`/`find` over raw JSONL files with a fixed list of "signal patterns" (3+ pipe stages, inline `python3 -c`, repeated `curl`, etc.) plus `ccrecall search` for semantic session discovery. No structured data collection layer exists — every invocation re-parses raw transcripts from scratch. No persistent tracking between runs, no de-duplication against previously-surfaced gaps, and signal detection is heuristic rather than statistical or semantic.

A complementary live heuristic in `bash-tools.md` tells the agent to flag repeated commands during active work (same tool 3+ times, 3+ pipe stages), with mine-tool-gaps as the retroactive counterpart.

## Patterns Found

### Pattern 1: Frequency-Ranked Alias Generation (statistical, offline)

**Used by**: topalias, huffshell, alias-gen, Terminal Tracker
**How it works**: Parse the shell's history file as a flat list of strings, count occurrences, rank by a scoring function that combines frequency with command length (since a short command run often saves less than a long command run occasionally), and emit alias definitions. The most interesting variant (huffshell) frames alias-length assignment as an information-theoretic optimization — allocate the shortest alias slots to the commands that save the most total keystrokes, analogous to Huffman coding.
**Strengths**: Zero dependencies, fully offline, deterministic, transparent — a human can read exactly why each alias was suggested (a number).
**Weaknesses**: Exact-string matching means `git log --oneline -20` and `git log --oneline -50` count as different commands. No sense of multi-command sequences — only single commands. Can suggest `alias gco='git checkout'` but never notices that `git fetch && git checkout main && git pull` happens together 40 times a week.
**Example**: https://github.com/meteoritt/topalias, https://github.com/gingerlime/huffshell

### Pattern 2: Sequence/Macro Mining Across Multi-Step Traces

**Used by**: Repro (shell-level, manual trigger); CHI 2024 "Automatic Macro Mining from Interaction Traces at Scale" (mobile UI, LLM-powered); "Recommending More Efficient Workflows" (Eclipse IDE telemetry)
**How it works**: Treats a session or trace — an ordered sequence of actions — as the unit of analysis rather than individual commands. The CHI 2024 paper is the most developed: convert each step to a natural-language task description via an LLM, embed those descriptions (Sentence-T5) and cluster by cosine similarity to find recurring semantic tasks even when literal steps differ, ground each recurring task back to concrete executable actions, then merge/optimize action sequences across many traces via graph search (BFS for shortest paths, ~44-55% macro-length reduction). Repro is the manual version: user notices they just did a multi-step dance and asks the tool to package the preceding history segment into a script.
**Strengths**: Captures the actual unit of automation value — most repetitive toil is a sequence, not a single command. Embedding/clustering generalizes across superficial variation.
**Weaknesses**: Requires either an LLM in the loop (cost, latency, hallucination in grounding) or manual triggering (Repro). Nobody has shipped a fully automatic, non-LLM sequence miner for shell history. Merging multiple trace variants into one canonical macro is a hard design problem.
**Example**: https://ar5iv.labs.arxiv.org/html/2310.07023, https://github.com/asidiali/repro

### Pattern 3: Structured History Store + Ad Hoc Query (infrastructure-first)

**Used by**: Atuin
**How it works**: Replace the shell's history mechanism with a structured database (SQLite) that records rich metadata per command — cwd, exit code, duration, host, session id, timestamp — at capture time. Pattern-mining becomes "write a SQL query" rather than "write a text-parsing script." Built-in stats subcommands cover common cases; arbitrary SQL queries handle the rest.
**Strengths**: Makes all downstream mining dramatically easier and richer — filter by exit code (only successful commands), by directory (project-specific patterns), or by duration (find slow, worth-scripting operations). None of this is possible from raw `.bash_history` or raw JSONL transcript parsing.
**Weaknesses**: Doesn't itself do clustering or alias suggestion — it's a substrate, not a complete pipeline. Requires migrating away from whatever history mechanism exists today.
**Example**: https://github.com/atuinsh/atuin

### Pattern 4: LLM-Mediated Retrieval and Suggestion (real-time or on-demand)

**Used by**: historai, Autocomplete.sh
**How it works**: Send history plus a natural-language query to an LLM at the moment of need — "what was that command I used to..." or "suggest a command to do X" — letting the model's world knowledge plus history context produce a suggestion, including commands never actually run before.
**Strengths**: Solves the "tip-of-the-tongue" recall problem. Handles novel requests, not just past repetition.
**Weaknesses**: Reactive assistance, not periodic audit. Not really "mining for automation candidates" — it's a per-query tool. Requires network/API access and per-query cost.
**Example**: https://github.com/sanspareilsmyn/historai

### Pattern 5: AI-Coding-Session Log Mining → Auto-Generated Skills

**Used by**: crune, generating-skills-from-logs, Claudeception
**How it works**: Purpose-built for Claude Code's JSONL session logs. crune's pipeline: parse JSONL sessions → extract conversation turns/metadata/subagent branches → summarize into representative prompts + work-type classification → build feature vectors from TF-IDF + tool-usage patterns + structural session features → reduce dimensionality with truncated SVD → agglomerative clustering → Louvain community detection for topic grouping → rank by reusability score (frequency, tool-sequence consistency, outcome quality) → pass top clusters to Claude to synthesize SKILL.md files. Claudeception is a lighter, always-on variant that runs continuously during sessions rather than as a batch job.
**Strengths**: Operates on the exact log format Claude Code produces. Combining structural (tool-call sequence) features with textual (TF-IDF) features detects repetition in what tools were called in what order, not just what the user typed.
**Weaknesses**: Heavy pipeline (embeddings, SVD, two clustering algorithms). Requires enough session volume for clustering to be meaningful. Output quality bounded by the LLM synthesis step.
**Example**: https://github.com/chigichan24/crune, https://dev.to/chigichan24/mining-hidden-skills-from-claude-code-session-logs-with-semantic-knowledge-graphs-2em8

## Anti-Patterns

- **Exact-string frequency counting without normalization**: `docker ps -a`, `docker ps --all`, and `docker ps -a | grep foo` all treated as unrelated commands — undercounting real repetition.
- **Single-command tunnel vision**: Nearly all pure-statistics tools only consider one history line at a time, never sequences — so they suggest `alias gco='git checkout'` but miss that `git fetch && git checkout main && git pull` is a single repeated workflow.
- **Auto-applying suggestions**: huffshell explicitly notes it makes no automatic changes — auto-writing to `.bashrc`/`.zshrc` without review risks shadowing system commands or breaking existing aliases.

## Emerging Trends

- **LLM-in-the-loop clustering by semantic intent** rather than string similarity — the CHI 2024 paper and crune both embed natural-language descriptions and cluster by meaning, generalizing across superficial variation.
- **Purpose-built miners for coding-agent transcripts** specifically — crune, Claudeception, and generating-skills-from-logs all target Claude Code's JSONL format, treating tool-call sequences as a first-class feature alongside text content.
- **Structured/queryable history as a substrate** — Atuin's shift from flat-text to SQLite suggests future mining tools will assume rich, queryable history is available rather than reimplementing parsing from scratch.

## Relevance to Us

The biggest gap in our current approach is the data collection layer. `mine-tool-gaps` re-parses raw JSONL transcripts on every run with ad-hoc grep patterns — no persistent store, no structured metadata, no cross-run deduplication. The user's idea of a PostToolUse hook capturing Bash commands into a structured store (SQLite or JSONL) maps directly to Pattern 3 (Atuin) and would be the foundation everything else builds on.

crune's pipeline (Pattern 5) is the closest external prior art to mine-tool-gaps, but uses a dramatically more sophisticated analysis layer. The gap isn't necessarily that we need all of crune's machinery — it's that we lack the structured collection layer that would make even simple frequency analysis reliable.

The live heuristic in `bash-tools.md` (flag repeated commands during active work) is complementary and maps to Claudeception's "continuous" approach vs. mine-tool-gaps' "batch" approach. Both cadences have value.

Academic work (CHI 2024 macro mining, Davison & Hirsh Markov chains, CommunityCommands) confirms that the state of the art has moved well past single-command frequency counting toward sequence-level, semantically-aware pattern detection.

## Recommendation

**Start with the collection layer** (Pattern 3). A PostToolUse hook on Bash commands capturing to SQLite — command text, working directory, timestamp, session ID, exit code, project path — is the right first move. It's cheap, reversible, and makes every downstream analysis (from simple frequency counting to crune-style clustering) dramatically easier. This is the Atuin insight applied to Claude Code's Bash tool calls.

**Then upgrade mine-tool-gaps to query the structured store** instead of re-parsing raw JSONL. Even without changing the heuristic signal detection, querying a database with metadata (cwd, exit code, project) will surface patterns the current grep-over-JSONL approach misses.

**crune is worth evaluating** (`/mine-eval-repo`) as a reference implementation for the heavier clustering pipeline, but its full machinery (SVD, Louvain community detection) is likely overkill for a solo developer's volume of sessions. The simpler frequency + normalization approach from Pattern 1, applied over the structured store from Pattern 3, may be the right middle ground.

**Don't bother with**: Pattern 4 (LLM-mediated retrieval) — it solves a different problem (recall, not audit). Pattern 1 in its pure form (exact-string alias generation) — too shallow, and we already have the bash-tools.md live heuristic covering the simplest cases.

## Sources

### Reference implementations
- https://github.com/chigichan24/crune — Claude Code session log miner → SKILL.md generator
- https://github.com/atuinsh/atuin — SQLite-backed shell history with rich metadata
- https://github.com/meteoritt/topalias — Frequency-ranked alias generation from shell history
- https://github.com/gingerlime/huffshell — Huffman-inspired optimal alias allocation
- https://pypi.org/project/alias-gen/0.6.4/ — Global-optimization alias generation
- https://pypi.org/project/terminal-tracker/1.0.0 — Length × frequency alias scoring
- https://github.com/asidiali/repro — Package recent shell history into a reusable script
- https://github.com/sanspareilsmyn/historai — LLM-powered shell history search
- https://github.com/dvorka-oss/hstr — Interactive fuzzy shell history search (TUI)
- https://github.com/blader/Claudeception — Continuous in-session skill extraction
- https://lobehub.com/skills/shutootaki-skills-generating-skills-from-logs — Combined shell + Claude log skill generator

### Blog posts & writeups
- https://dev.to/chigichan24/mining-hidden-skills-from-claude-code-session-logs-with-semantic-knowledge-graphs-2em8 — crune design writeup
- https://www.mindstudio.ai/blog/self-learning-claude-code-skill-learnings-md/ — Incremental self-annotation pattern (Learnings.md)

### Academic papers
- https://ar5iv.labs.arxiv.org/html/2310.07023 — CHI 2024: Automatic Macro Mining from Interaction Traces at Scale
- https://dl.acm.org/doi/abs/10.1145/1622176.1622214 — CommunityCommands: collaborative-filtering for software commands (UIST 2009)
- https://www.cs.cornell.edu/~hirsh/papers/1998/aaai-tsws1.pdf — Markov-chain UNIX command prediction (AAAI 1998)
- https://arxiv.org/pdf/2102.03670 — Recommending More Efficient Workflows to Software Developers
- https://arxiv.org/pdf/2012.10206 — Empirical Investigation of Command-Line Customization [unverified — PDF not parseable]

### Documentation & products
- https://docs.warp.dev/terminal/entry/command-corrections/ — Warp's thefuck-based command corrections (adjacent, not mining)
- https://autocomplete.sh/ — LLM-powered shell autocompletion
