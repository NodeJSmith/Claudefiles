---
description: "Use when the user says: \"show issue\", \"investigate this issue\". Deep-dive issues by key, inferring one from the branch name if none are given."
---

# Issues Command

Give the user a grounded picture of one or more issues (what is asked, what code it touches, how big it is) and help them choose how to proceed. Works with whatever issue tracker Claude has tools for, signaled by the `$ISSUE_TRACKER` env var.

## Arguments

$ARGUMENTS — zero or more issue keys, in whatever format the configured tracker uses (e.g. `123 456`, `PROJ-123 PROJ-456`). With none, infer one from the current branch name, or ask.

## Tracker

Read `$ISSUE_TRACKER`. Unset or empty means GitHub (`gh`). If it names a tracker you have no tools for, say which one was configured, ask the user how to proceed, and stop. Don't guess at a tool and don't fall back to a different tracker.

## Finding the key

With no arguments, judge whether the branch name (`git branch --show-current`) unambiguously names an issue in the tracker's key format: for example `123-fix-thing` or `fix/123-description` on GitHub, `PROJ-123-fix-thing` on a project-prefixed tracker. A number that is more plausibly a date or version (`2026-08-cleanup`) is not a key. If you infer one, say so and use it as the sole key. If none is inferred, or its lookup returns `LOOKUP_FAILED`, ask the user which issue to look at.

## Deep dive

For each key, dispatch a subagent (`subagent_type: light-worker`), in parallel for several keys, with this prompt:

> Check `$ISSUE_TRACKER` (e.g., `printenv ISSUE_TRACKER`) to know which platform's tools to use; if it is unset or empty, use GitHub (`gh`). Fetch the full issue for key <KEY>: title, body, comments, labels/tags, assignees, and milestone/sprint if applicable.
>
> If the issue does not exist, or the fetch fails for a reason specific to this one key, return exactly `LOOKUP_FAILED` and nothing else. Reserve `TRACKER_ERROR: <reason>` for the tracker itself being unusable (no tools for it, auth rejected, unreachable), which would fail every key equally.
>
> Then scan the codebase for the files and areas the issue mentions or relates to. Also look for design docs that reference it: a spec directory or `design.md` naming its key, or a parent design the issue body points to.
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

Display all summaries. `TRACKER_ERROR` means stop and surface the reason: a different key won't fix an unusable tracker, so don't ask for a different key or continue to the next step. `LOOKUP_FAILED` is per key: name the failed key and carry the others forward.

## Next step

Issues passed together are meant to be worked together: one change, one sketch, one build. Ask once for the whole set with `AskUserQuestion`, not once per issue. Build the menu from what the deep dives found and mark your pick recommended, with descriptions about these issues' actual content. The usual outcomes:

- **Sketch it (`/mine-sketch`)**: settle the change's decisions in a ledger before any code is written
- **Decide inline, then build**: answer a few open questions now, then implement in this session
- **Build it directly**: implement now, when the change leaves nothing to decide
- **Research first**: `/mine-research`, when it's unclear whether or how the change can be done

Beyond those:

- **Push back when the issues don't belong together** (unrelated areas with no shared decisions, or a combined change too large for one ledger). Say why and offer the split you'd suggest. A sketch session ends once its ledger is ratified, so a split means working one group now and naming the others for a later run.
- **Offer to close an issue that is already fixed, superseded, or invalid**, showing the closing comment before posting it. The rest carry on without it.
- **A ratified build-altitude ledger covering the issues** (from **Design docs**): offer to build from it with `/mine-sketch <feature_dir>` instead of sketching again.
- **A Breakdown issue of a milestone-altitude ledger** is a plan, not a build spec; a pickup sketch checks the ledger against the code that has landed since. Recommend "Sketch it" however settled the ledger looks, and leave out inline and direct build, which skip that check; if the scan shows the issue needs no ledger, the pickup offers the inline path itself. A pickup takes one issue, so with several Breakdown issues work one now and name the rest for later.

To choose among sketch, inline, and build, look at the implementation decisions the change leaves unmade and route them per `sketch-before-building.md`. A parent design or detailed issue body settles *what* to build, not the decisions underneath, so "the design is already decided" alone isn't a reason to build directly. List the decisions you found so the user can see why you recommend what you do.

Then carry out the choice:

- **Sketch it**: for a Breakdown issue of a milestone ledger, invoke `/mine-sketch <milestone_dir> <key>` with the structured summary, so the sketch runs as that issue's pickup. Otherwise invoke `/mine-sketch` once with every remaining issue's key and summary as the change description, asking it to list the keys on the ledger's `**Issues:**` line so the eventual PR closes all of them.
- **Decide inline**: send each open decision with `SendUserMessage` (options and your recommendation), ask them together in one `AskUserQuestion`, then build as below. If an answer opens new decisions or the questions turn out to depend on each other, stop and offer `/mine-sketch`: continuing inline would produce a sketch that never got challenged.
- **Build directly**: implement the remaining issues together from their summaries, with a `Closes #N` line per key in a commit message (GitHub) so the PR closes all of them.
- **Research first**: invoke `/mine-research` with the issues' context as one proposal to investigate.
