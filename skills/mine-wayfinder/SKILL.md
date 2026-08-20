---
name: mine-wayfinder
description: "Use when the user says: \"wayfinder\", \"chart this effort\", \"too big for one session\", \"multi-session plan\", \"foggy effort\", \"progressive discovery\", or has a large uncertain effort that needs progressive discovery before planning."
user-invocable: true
---

# Wayfinder

A loose idea has arrived — too big for one agent session, and wrapped in fog: the way from here to the **destination** isn't visible yet. Wayfinding is about finding that way, not charging at the destination. This skill charts the way as a **shared map** on the repo's issue tracker, then works its **decision tickets** — questions whose resolution is a decision, not slices of a build to execute — one at a time until the route is clear.

The destination varies per effort, and naming it is the first act of charting — it shapes every ticket. It might be a spec to hand off and iterate on, a decision to lock before planning starts, or a change made in place like a data-structure migration. The map is domain-agnostic — engineering work, research, whatever fits the shape.

## Plan, Don't Do

Wayfinder is **planning** by default: each ticket resolves a decision, and the map is done when the way is clear — nothing left to decide before someone goes and does the thing. The pull to just do the work is usually the signal you've reached the edge of the map and it's time to hand off. An effort can override this in its **Notes** — carrying execution into the map itself — but absent that, produce decisions, not deliverables.

## Refer by Name

Every map and ticket is an issue, so it has a **name** — its title. In everything the human reads — narration, the map's Decisions-so-far — refer to it by that name, never by a bare id, number, or slug. A wall of `#42, #43, #44` is illegible; names read at a glance. The id and URL don't vanish — a name wraps its link — but they ride *inside* the name, never stand in for it.

## The Map

The map is a single issue, labelled `wayfinder:map` — the canonical artifact. Its tickets are child issues of the map.

The map is an **index**, not a store. It lists the decisions made and points at the tickets that hold their detail; a decision lives in exactly one place — its ticket — so the map never restates it, only gists it and links.

**Tracker:** this skill tracks the map and its tickets as issues in the project's issue tracker — see [Tracker Operations](#tracker-operations) for every map and ticket operation, and for the authoritative statement of the preflight gate. Wayfinder currently requires GitHub: charting and working the map lean on native sub-issues, native blocking edges, and assignee-based claim, and no other tracker exposes all three yet. It also requires a repo that can actually hold issues, and both are checked before charting. If either fails, stop and ask the user how to track the effort — don't invent a parallel tracker, and don't start a map on a repo that can't carry it through.

### The map body

The whole map at low resolution, loaded once per session. Open tickets are **not** listed — they are open child issues, found by query.

```markdown
## Destination

<what reaching the end of this map looks like — the spec, decision, or change this effort is finding its way to. One or two lines; every session orients to it before choosing a ticket.>

## Notes

<domain; skills every session should consult; standing preferences for this effort>

## Decisions so far

<!-- the index — one line per closed ticket: enough to judge relevance, then zoom the link for the detail the ticket holds -->

- [<closed ticket title>](link) — <one-line gist of the answer>

## Not yet specified

<!-- see "Fog of war": in-scope fog you can't ticket yet; graduates as the frontier advances -->

## Out of scope

<!-- see "Out of scope": work ruled beyond the destination; closed, never graduates -->
```

### Tickets

Each ticket is a **child issue** of the map; the tracker's issue number is its identity. Its body is the question, sized to one session:

```markdown
## Question

<the decision or investigation this ticket resolves>
```

Each ticket carries a `wayfinder:<type>` label — one of `research`, `prototype`, `grilling`, `task` (see [Ticket Types](#ticket-types)).

A session **claims** a ticket by assigning it to the dev driving the map, **first**, before any work, so concurrent sessions skip it — see [Claim a ticket](#tracker-operations) for the race-safe procedure (assignment alone isn't exclusive). An open, unassigned ticket is unclaimed.

Blocking uses the tracker's **native** dependency relationship — essential because it renders the frontier _visually_ in the tracker's own UI, so the human sees what's takeable without opening the map. A ticket is **unblocked** when every ticket blocking it is closed; the **frontier** is the set of open, unblocked, unclaimed children — the edge of the known.

The answer isn't part of the body — it's recorded on resolution (see [Work through the map](#work-through-the-map)). Assets created while resolving a ticket are linked from the issue, not pasted in.

## Ticket Types

Every ticket is either **HITL** — human in the loop, worked *with* a human who speaks for themselves — or **AFK**, driven by the agent alone. A HITL ticket only resolves through that live exchange; the agent never stands in for the human's side of it (a grilling session that answers its own questions has broken this).

- **Research** (AFK): Reading documentation, third-party APIs, or local resources like knowledge bases to surface a fact a decision waits on. Resolved by dispatching the `researcher` agent directly (`Agent(subagent_type: "researcher")`) — not `/mine-research`, whose Phase 1 and Phase 3 are interactive `AskUserQuestion` gates that block on a live human and can't be satisfied by an AFK, ticket-driven dispatch. Write the ticket's title and body so they already carry the agent's input contract (Proposal, Motivation, Flexibility, Constraints) — that scoping happens once, when the ticket is charted, not re-interrogated at dispatch time. Depth defaults to `normal` unless the ticket says otherwise. Use when knowledge outside the current working directory is required.
- **Prototype** (HITL): Raise the fidelity of the discussion by making a cheap, rough, concrete artifact to react to — an outline, a rough take, a stub, or UI/logic code via `/mine-mockup`. Links the prototype as an asset. Use when "how should it look" or "how should it behave" is the key question.
- **Grilling** (HITL): Conversation via `/mine-grill` and `/mine-domain-model`, one question at a time. The default case.
- **Task** (HITL or AFK): Manual work that must happen before a *decision* can be made — nothing to decide, prototype, or research, but the discussion is blocked until it's done. Signing up for a service so its API can be judged, provisioning access, moving data so its shape can be seen. This is the one type that *does* rather than decides — and it earns its place by unblocking a decision, not by delivering the destination. The agent drives it alone where it can (AFK); otherwise it hands the human a precise checklist (HITL). Resolved when the work is done; the answer records what was done and any resulting facts (credentials location, new URLs, row counts) later tickets depend on.

## Fog of War

The map is _deliberately_ incomplete: don't chart what you can't yet see. Beyond the live tickets lies the **fog of war** — the dim view of decisions and investigations you can tell are coming but can't yet pin down, because they hang on questions still open. Resolving a ticket clears the fog ahead of it, graduating whatever's now specifiable into fresh tickets — one at a time, until the way to the destination is clear and no tickets remain.

The map's **Not yet specified** section is where that dim view is written down: the suspected question, the area to revisit later. It's the undiscovered frontier _toward_ the destination — everything here is in scope, just not sharp enough to ticket. Write as loosely or as fully as the view allows; it doubles as a signpost for collaborators reading where the effort is headed.

**Fog or ticket?** The test is whether you can state the question precisely now — _not_ whether you can answer it now.

- **Ticket when** the question is already sharp — even if it's blocked and you can't act on it yet.
- **Not yet specified when** you can't yet phrase it that sharply. Don't pre-slice the fog into ticket-sized pieces: it's coarser than a ticket, and one patch may graduate into several tickets, or none, once the frontier reaches it.

**Not yet specified** excludes what's already decided (Decisions so far), what's already a live ticket, and what's out of scope (the next section).

## Out of Scope

Fog only ever gathers _toward_ the destination. The destination fixes the scope, so work beyond it is **out of scope** — it isn't fog, and it doesn't belong in **Not yet specified**. It gets its own **Out of scope** section on the map: work you've consciously ruled out of _this_ effort. Scope, not sharpness, lands it here.

Out-of-scope work never graduates — the frontier stops at the destination — so it returns only if the destination is redrawn, and then as a fresh effort, not a resumption.

Ruling something out of scope is a scoping act, not a step on the route. When a ticket that already exists turns out to sit past the destination — mis-scoped in while charting, or exposed by a resolution — **close it** (a closed ticket is unambiguously off the frontier) and leave one line in the **Out of scope** section: the gist plus why it's out of scope, linking the closed ticket. It stays out of **Decisions so far**, which records the route actually walked — a scope boundary isn't a step on it.

## Tracker Operations

All map and ticket operations happen through the project's issue tracker. These operations assume GitHub's native sub-issues, native blocking/dependency edges, and assignee-based claim — Wayfinder doesn't yet know how to drive them on a tracker that lacks one. Two preflight checks, both before charting; either failing means stop and ask the user how to track the effort rather than charting a map that would fail partway through:

1. **The tracker is GitHub** — `$ISSUE_TRACKER` is set to `gh`.
2. **The repo has Issues enabled** — query the repo's own settings through the tracker's repo API, not an issue-listing command. An issue-list wrapper exits 0 on a repo with Issues turned off, so it can't tell "this repo has no issues yet" apart from "this repo can't have issues," and charting would only fail once it tried to create the map.

**Labels:** Ensure these labels/tags exist in the tracker: `wayfinder:map`, `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, `wayfinder:task`. Create any that are missing — verify each doesn't already exist before creating it, and don't suppress creation errors: a real failure (permissions, network) should not look identical to "already exists."

**Create the map:** Create an issue with the map body, labeled `wayfinder:map`.

**Create a child ticket, wired to the map:** Create a child issue of the map issue, labeled with the ticket type (`wayfinder:<type>`).

**Wire blocking edges (second pass):** Blocking between two tickets created in the same batch still needs both issue numbers to exist first, so wire it after both are created. Add blocking relationships between tickets where dependencies exist, using the tracker's native blocking/dependency feature so the frontier is visible in the tracker's own UI without opening the map.

**Claim a ticket:** Assign yourself to the ticket, then verify you're the first assignee — assignment isn't guaranteed to be exclusive, so two concurrent sessions can both claim the same ticket and both believe they won. Claim under your own distinct identity, not a shared or service identity — if concurrent sessions all claim under the same identity, the first-assignee check can't tell them apart and the race-safety guarantee breaks. Do this every time you claim, whether claiming for manual work ([Work through the map](#work-through-the-map) step 2) or before dispatching a research agent ([Chart the map](#chart-the-map) step 5). If you're not the first assignee, someone else won the race — drop this ticket and pick a different one from the frontier instead of proceeding.

**Record the resolution and close:** Add the resolution as a comment, then close the ticket.

**Query the frontier** (open, unblocked, unclaimed children of the map): Query the tracker for open child issues of the map that have no assignee and no open blocking issues.

## Invocation

Two modes. Either way, **never resolve more than one ticket per session** — with the exception of research tickets.

### Chart the map

User invokes with a loose idea.

0. **Run the preflight** — both checks in [Tracker Operations](#tracker-operations). Do this before step 1, not after: steps 1-2 spend real work grilling the idea, and there's no point paying for it on a repo that can't hold the map.
1. **Name the destination.** Run `/mine-grill` and `/mine-domain-model` to pin down what this map is finding its way to — the spec, decision, or change. The destination fixes the scope, so it's settled first.
2. **Map the frontier.** Grill again, **breadth-first** this time: fan out across the whole space rather than deep on any one thread, surfacing the open decisions and the first steps takeable now. **If this surfaces no fog** — the way to the destination is already clear, the whole journey small enough for one session — you don't need a map. Stop and ask:

```
AskUserQuestion:
  question: "The frontier surfaced no fog — the way to the destination looks clear enough for one session. How do you want to proceed?"
  header: "Wayfinder"
  multiSelect: false
  options:
    - label: "Handle it directly, no map"
      description: "Skip wayfinder — the effort is small enough to just do now"
    - label: "Chart it as a map anyway"
      description: "Still worth tracking as tickets, even though it's small"
```
3. **Create the map** (label `wayfinder:map`): Destination and Notes filled in, Decisions-so-far empty, the fog sketched into **Not yet specified**.
4. **Create the tickets you can specify now** as child issues of the map — then wire blocking edges in a **second pass**, once every new ticket's number is known. Before ending the session, re-fetch the new tickets and confirm every intended blocking edge landed — an interrupted second pass leaves tickets that look unblocked but shouldn't be. **Verification is a hard stop:** if re-fetching shows a missing blocking edge, stop here — do not proceed to step 5 — and repair or retry the edge, then re-fetch and verify again, looping until every intended edge lands. Only move on once verification passes; otherwise research tickets can be dispatched while their prerequisites remain open. Everything you can't yet specify stays in the fog — the **Not yet specified** section.
5. **Fire the research subagents.** First, **claim every research ticket in this batch** (see [Claim a ticket](#tracker-operations)) — all of them, before any dispatch, so no other session grabs one mid-batch; drop any ticket that loses its claim race and proceed without it. For each claimed `research` ticket, dispatch the `researcher` agent directly — not `/mine-research`, whose Phase 1/Phase 3 `AskUserQuestion` gates require a human who isn't there for an AFK dispatch. Derive the agent's input-contract fields (Proposal, Motivation, Flexibility, Constraints) from the ticket's own title and body, and default Depth to `normal` unless the ticket specifies otherwise. Fire every research ticket's agent in parallel; this now genuinely runs AFK, since `researcher` (unlike `/mine-research`) has no interactive gates. Point Output file path at `design/research/<ticket-slug>/research.md`, committed — the same durable convention `mine-prior-art`, `mine-define`, `mine-research`, and `mine-why` use (a topic directory holding a fixed `research.md`, matching the `design/research/*/research.md` glob `mine-define` and `mine-why` already scan for prior research). After each dispatch completes, verify the output file exists and contains the `# Research Brief:` header (same check `mine-define` uses). **On success:** resolve the ticket exactly as [Work through the map step 4](#work-through-the-map) does — post a resolution comment summarizing the finding, close the ticket, and append a context pointer to the map's Decisions-so-far (re-fetching the map body fresh immediately before the append, per the note in that step — several research tickets in this batch may be writing to it in sequence). **On failure:** post a comment on the ticket noting the dispatch failed, and release the claim (unassign yourself) so a later session can retry it rather than finding it claimed and stuck.
6. **Report back.** Tell the user the frontier size (how many tickets are now takeable), list them by name, and give the map's link. Stop — charting is one session's work; it hand-resolves nothing.

### Work through the map

User invokes with a map (URL or number). If no map is named, first look for one by querying the tracker for open issues labeled `wayfinder:map`, and ask the user which to resume if more than one is open. A ticket is **optional** — without one, you pick the next decision, not the user.

0. **Run preflight check 1** — `$ISSUE_TRACKER` is set to `gh` (see [Tracker Operations](#tracker-operations)). Do this before looking for a map, not after: on a machine pointed at a different tracker, a map lookup by number resolves against the wrong system and can silently land on an unrelated issue, and steps 2-5 then attempt sub-issue, blocking-edge, and assignee operations that tracker doesn't have. Check 2 (Issues enabled) needs no rerun here — an existing map is proof of it.
1. Load the **map** — the low-res view, not every ticket body.
2. Choose the ticket. If the user named one, use it. Otherwise take the first frontier ticket in order (see [Query the frontier](#tracker-operations)). **Claim it** (see [Claim a ticket](#tracker-operations)) before any work — if the race check shows someone else got there first, go back and pick a different frontier ticket.
3. Resolve it — **zoom as needed**: fetch the full body of any related or closed ticket on demand; invoke the skills the `## Notes` block names. If in doubt, use `/mine-grill` and `/mine-domain-model`.
4. Record the resolution: post the answer as a **resolution comment** and **close** the issue, then **append a context pointer** to the map's Decisions-so-far — before writing it, re-fetch the map's current body fresh (not the copy loaded in step 1) and apply the edit on top of that, so a stale in-memory copy never overwrites another session's concurrent edit.
5. Add newly-surfaced tickets (create-then-wire); graduate any fog the answer has made specifiable, clearing each graduated patch from **Not yet specified** so it lives only as its new ticket — re-fetch the map body fresh again before this edit, for the same reason as step 4. If the answer reveals a ticket — this one or another — sits beyond the destination, **rule it out of scope** rather than resolving it on the route. If the decision invalidates other parts of the map, update or delete those tickets.
6. **Report back.** Tell the user what was resolved, the current frontier size, and the map's link. If the frontier is now empty, say plainly that the destination is reached and suggest the natural next step (e.g., handing the map off to `/mine-define`).

The user may run unblocked tickets in parallel, so expect other sessions to be editing the tracker concurrently.
