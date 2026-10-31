---
description: "Use when the user says: \"show issue\", \"investigate this issue\". Deep-dive issues by key, inferring one from the branch name if none are given."
---

# Issues Command

Deep-dive specific issues by key. If no keys are given, infer one from the current branch name, or ask. Works with whatever issue tracker Claude has tools for, signaled by the `$ISSUE_TRACKER` env var.

## Arguments

$ARGUMENTS — zero or more issue keys, in whatever format the configured tracker uses (e.g. `123 456` for a numeric tracker, `PROJ-123 PROJ-456` for a project-prefixed tracker). If none provided, infer a key from the branch name, or ask.

## Phase 1: Tool Detection

Read `$ISSUE_TRACKER`.

- If **unset or empty**: use GitHub (`gh`). It is the default tracker.
- If **set to a tracker you have no tools for**: say which tracker was configured, ask the user how to proceed, and **stop** — don't continue to Phase 2. Don't guess at a tool and don't fall back to a different tracker.
- Otherwise: proceed — use whatever tool matches that tracker.

## Phase 2: Route

- **Arguments provided**: Continue to Phase 3 (Deep Dive).
- **No arguments provided**: Try to infer an issue key from the current branch name before asking.
  1. Run `git branch --show-current`.
  2. Judge whether the branch name unambiguously names an issue, in whatever key format the configured tracker uses. For a numeric tracker like GitHub, recognize the same patterns as `skills/mine-create-pr/SKILL.md`'s closing-keyword detection: a leading number (`123-fix-thing`), `issue-N`/`issue/N`, or `fix/N-description`, `feat/N-description`, `chore/N-description`, etc. For a project-prefixed tracker like Jira, a leading project-prefixed key (`PROJ-123-fix-thing` → `PROJ-123`). Don't infer from a number that's more plausibly a date, version, or something unrelated (e.g. `2026-08-cleanup`).
  3. **If a key is inferred**: say so (e.g. "Inferred issue #123 from the branch name — deep diving.") and use it as the sole argument, continuing to Phase 3. If the Phase 3 subagent returns `LOOKUP_FAILED` (issue doesn't exist), fall back to step 4 instead of surfacing a raw tool error.
  4. **If no key is inferred, or the inferred key's lookup failed**: ask the user which issue to deep-dive: "No issue key in the branch name — which issue should I look at?" If they give a key, use it as the sole argument and continue to Phase 3.

## Phase 3: Deep Dive (Subagent)

For **each** issue key in the arguments, use the **Agent** tool (`subagent_type: light-worker`) with this prompt:

> Check `$ISSUE_TRACKER` (e.g., `printenv ISSUE_TRACKER`) to know which platform's tools to use; if it is unset or empty, use GitHub (`gh`). Then fetch the full issue for key <KEY> from the project's issue tracker — title, body, comments, labels/tags, assignees, and milestone/sprint if applicable.
>
> If the issue does not exist, or the fetch fails for a reason specific to this one key, return exactly `LOOKUP_FAILED` and nothing else. Reserve `TRACKER_ERROR: <reason>` for the tracker itself being unusable — no tools for the configured tracker, auth rejected, tracker unreachable — since that condition would fail every key equally, not just this one. The caller's branch-name fallback only makes sense for a key that might be wrong, so don't report an unusable tracker as one.
>
> Then scan the codebase for files and areas mentioned in or related to the issue (grep for keywords, check referenced file paths, look at relevant modules). Also look for design docs that reference the issue: a spec directory or `design.md` naming its key, or a parent design the issue body points to.
>
> Return this structured summary and nothing else:
>
> ```
> ## Issue <KEY> — Title
> - **Description**: [condensed from body, 2-3 sentences max]
> - **Key comments**: [relevant discussion points, or "None" if no useful comments]
> - **Design docs**: [each doc's path, its `**Status:**` line and `## Posture` Altitude (`build` or `milestone`) when the doc has those, and what it decides for this issue, or "None"]
> - **Affected areas**: [files/modules identified from codebase scan]
> - **Estimated scope**: [small/medium/large with brief reasoning]
> - **Suggested approach**: [1-2 sentences]
> ```

Launch subagents **in parallel** when multiple keys are provided. Display all structured summaries.

If a subagent returns `TRACKER_ERROR`, surface the reason to the user and **stop** — an unusable tracker isn't fixed by asking for a different issue key, so don't fall through to Phase 2's branch-name fallback or to Phase 4.

A `LOOKUP_FAILED` is per-key. In a multi-key run, name the key that failed and carry the summaries that did come back through to Phase 4 — one bad key shouldn't discard the others' work.

## Phase 4: Next Step (Main Context)

Issues passed together are meant to be worked together: one change, one sketch, one build. Ask once for the whole set via `AskUserQuestion`, not once per issue. Push back when the deep dives say they don't belong together, such as unrelated areas with no shared decisions, or a combined change too large for one ledger. Say why in the message, and offer the split you'd suggest as an option in place of the least relevant usual one. A sketch session ends once its ledger is ratified, so a split means working one group now and naming the others for a later run. Pick the option that fits best and mark it recommended. Write each description around the issues' actual content. The usual options:

- **Sketch it (`/mine-sketch`)**: settle the change's decisions in a ledger before any code is written
- **Decide inline, then build**: answer a few open questions now, then implement in this session
- **Build it directly**: implement now, when the change leaves nothing to decide
- **Research first**: run `/mine-research` when it's unclear whether or how the change can be done

When a split or close offer needs a slot, drop whichever of Build directly or Decide inline your findings rule out.

To choose among sketch, inline, and build, look at the implementation decisions the change leaves unmade (data shape, boundaries, edge-case behavior, test strategy), then route them (`sketch-before-building.md` holds the full rule). None open means build. Independent calls that fit in one `AskUserQuestion` call, each local and cheap to reverse, mean inline. Decisions that interact, reshape data or a module boundary, add something with no natural home, are hard to reverse, or outnumber one call mean sketch. A parent design or a detailed issue body settles *what* to build, not the decisions underneath it, so "the design is already decided" is not by itself a reason to build directly. In the message, list the decisions you found, so the user can see why you recommend what you do.

If an issue is already fixed, superseded, or no longer valid, offer to close it, and show the closing comment before posting it; the rest of the set carries on without it. If **Design docs** lists a ratified build-altitude ledger covering the issues, offer to build from it with `/mine-sketch <feature_dir>` instead of sketching again. A ratified milestone-altitude ledger is a plan, not a build spec. Its issues are picked up through a pickup sketch, which checks the ledger against the code that has landed since. So for a Breakdown issue, recommend "Sketch it" however settled the ledger looks, and drop "Decide inline" and "Build it directly", which skip that check. A pickup takes one issue: when the set holds several Breakdown issues, work one now and name the rest for later runs.

**If the user picks "Sketch it":** when the issue is a Breakdown issue of a milestone ledger, invoke `/mine-sketch <milestone_dir> <key>` with the structured summary, so the sketch runs as that issue's pickup. Otherwise invoke `/mine-sketch` once, passing every remaining issue's key and structured summary (title, description, design docs, affected areas, suggested approach) as the change description, and ask it to list the keys on the ledger's `**Issues:**` line so the eventual PR closes all of them.

**If the user picks "Decide inline, then build":** write each open decision in the message with its options and your recommendation, then ask them in one `AskUserQuestion` call. Once they're answered, continue as in "Build it directly", including its `Closes #N` lines. If an answer opens new decisions, or the questions turn out to depend on each other, stop and offer `/mine-sketch` instead: carrying on inline would produce a sketch that never got challenged.

**If the user picks "Build it directly":** use the remaining issues' structured summaries as the change description and implement them together. Put a `Closes #N` line for each key in a commit message (GitHub) so the PR closes all of them.

**If the user picks "Research first":** invoke `/mine-research`, passing the issues' context as one proposal to investigate.
