---
name: mine-why
description: "Use when the user says: \"why is this code like this\", \"why does this exist\", \"why was this built this way\", \"decision rationale\", \"what's the history behind\". Decision archaeology — reconstructs historical rationale from evidence, not speculation."
user-invocable: true
---

# Why

Reconstruct why existing code is shaped the way it is, from evidence. This matters most before refactoring: if you don't know why a constraint exists, removing it can break things the diff doesn't show.

The trap is a plausible story. Code invites a tidy rationale, and a narrative with no evidence behind it is worse than "unknown" because it gets trusted. Absence of evidence is a finding: "no issues reference this code" tells the reader the decision predates the tracker or was never contested. Never fill a gap with speculation.

Related: `/mine-how` explains how code works now; `/mine-research` investigates a proposed change. This one is about history and rationale.

## Arguments

$ARGUMENTS — the code or decision to investigate: a pattern, file, constraint, or structural choice. If empty, ask what they want to understand (offering "something in the current diff" as a way in, if there is one).

Pin down the target: the specific files and line ranges. If the user named a pattern or constraint, locate the code first.

## Gathering evidence

Rationale hides in different places, so search these sources in parallel with `light-worker` agents, one per source, each writing findings to its own file under a directory made with `mktemp -d <scratchpad>/mine-why-XXXXXX`. Every agent reports null results explicitly, and a search that couldn't run is reported as such rather than folded into an empty result.

- **Git history:** the introducing commit, reshaping refactors, reverts, whether the commit message explains why, whether the code is stable or volatile. Say so if history is shallow or the file moved.
- **Issues and PRs:** the issue tracker and the PR host are independent, so search both. `$ISSUE_TRACKER` (unset or empty means GitHub) says which tracker's tools to use for issues; `git-platform` says which host's tools to use for PRs. The tracker says nothing about where PRs live, so don't skip one search because the other couldn't run.
- **Design docs and research:** wherever this repo keeps them, for example `design/specs/*/design.md`, `design/research/*/research.md`, CLAUDE.md, README, ARCHITECTURE.md, `docs/`.
- **Rules, comments, inline rationale:** comments near the target (does it explain why, or only what?), TODO/HACK/WORKAROUND/NOTE markers, `rules/`.
- **Tests as constraints:** assertions, regression test names, and comments that imply why the code must be shaped this way.
- **Past conversations:** `ccrecall --json search-messages -q "<question or key terms>" -n 8`, then `ccrecall tail <session_uuid>` for promising matches too short to judge. Note whether a conversation settled the decision or only touched it. This history is often thin.

## Synthesis

A `standard-worker` reads all the evidence files and writes a confidence-calibrated explanation: a one-paragraph summary of the most likely rationale with overall confidence, then each aspect with its confidence, cited evidence (commit hash, issue number, doc path, test name), and what the evidence says, ending with the evidence gaps, which tell a would-be refactorer what isn't documented.

Confidence means: HIGH, multiple independent sources agree; MEDIUM, one source states it directly; LOW, the evidence is indirect; UNKNOWN, nothing found. Where sources conflict, present both and flag the conflict rather than picking a winner.

## Done looks like

The synthesis is presented conversationally in the main context, with no files or artifacts produced for the user. If every aspect is UNKNOWN, say so directly: you searched all of the above and the rationale appears to be undocumented.
