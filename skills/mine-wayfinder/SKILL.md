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

**Tracker:** this skill uses `gh-issue` (a thin wrapper over `gh issue` — see [Tracker Operations](#tracker-operations)) for every map and ticket operation. If the repo has no GitHub Issues enabled, fall back to the local-markdown tracker described in that section instead.

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

A session **claims** a ticket by assigning it to the dev driving the map, **first**, before any work, so concurrent sessions skip it. That assignee _is_ the claim: an open, unassigned ticket is unclaimed.

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

### GitHub Issues (default)

All map and ticket operations go through `gh-issue` (a thin passthrough to `gh issue` that upgrades to bot-token auth when available — see the "GitHub tool notes" in `rules/common/capabilities-core.md`). Confirm the repo has Issues enabled with `gh-issue overview` before charting; if it errors, use the [local-markdown fallback](#local-markdown-fallback-no-github-issues) instead.

**Labels** (`wayfinder:map`, `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, `wayfinder:task`) must exist before they're used. Create any missing ones once per repo:

```bash
gh label create "wayfinder:map" --color 5319e7 --description "Wayfinder map issue" 2>/dev/null || true
gh label create "wayfinder:research" --color 0e8a16 2>/dev/null || true
gh label create "wayfinder:prototype" --color 1d76db 2>/dev/null || true
gh label create "wayfinder:grilling" --color fbca04 2>/dev/null || true
gh label create "wayfinder:task" --color d93f0b 2>/dev/null || true
```

**Create the map:**

```bash
gh-issue create --title "<destination title>" --label "wayfinder:map" --body "<map body>"
```

**Create a child ticket, wired to the map:** `gh issue create` supports native sub-issues via `--parent`, so a ticket is parented in the same call that creates it — no separate wiring step needed for parent/child:

```bash
gh-issue create --title "<ticket title>" --label "wayfinder:<type>" --body "<question>" --parent <map-issue-number>
```

**Wire blocking edges (second pass):** blocking between two tickets you're creating in the same batch still needs both issue numbers to exist first, so wire it after both are created:

```bash
gh-issue edit <blocked-ticket-number> --add-blocked-by <blocking-ticket-number>
```

This is GitHub's **native** blocking relationship (`gh` ≥2.90), so it renders in the tracker's own UI — the frontier is visible without opening the map.

**Claim a ticket** — use raw `gh`, not `gh-issue`: `gh-issue` may run under a bot token when one is configured, and a claim must reflect the human driving the map, not the bot (the same reasoning `capabilities-core.md` documents for PR authorship):

```bash
gh issue edit <ticket-number> --add-assignee @me
```

**Record the resolution and close:**

```bash
gh-issue comment <ticket-number> --body "<resolution answer>"
gh-issue close <ticket-number>
```

**Query the frontier** (open, unblocked, unclaimed children of the map): fetch the map's children as JSON and filter with `jq`. Inspect one row's shape first (`blockedBy` is `{nodes: [...], totalCount: N}`; `parent` is `null` or `{number, title}`) before scripting a batch query, since exact field availability can vary by `gh` version:

```bash
gh-issue list --state open --json number,title,labels,assignees,parent,blockedBy --limit 100 \
  --jq '[.[] | select(.parent.number == <map-issue-number>
    and (.assignees | length) == 0
    and (.blockedBy.nodes | map(select(.state != "CLOSED")) | length) == 0)]'
```

### Local-markdown fallback (no GitHub Issues)

When `gh-issue overview` fails (Issues disabled, or no GitHub remote at all), track the map and tickets as files under `.scratch/<effort-slug>/`:

```
.scratch/<effort-slug>/
├── map.md
└── tickets/
    ├── 001-<slug>.md
    └── 002-<slug>.md
```

`map.md` holds exactly the [map body](#the-map-body) template.

Each ticket file has frontmatter plus the question body:

```markdown
---
id: 001
title: <ticket title>
type: research | prototype | grilling | task
status: open | closed
assignee: none | self
blocked_by: []
---

## Question

<the decision or investigation this ticket resolves>

## Resolution

<filled in on close>
```

Ticket ids are zero-padded, incrementing integers assigned at creation. "Claim" sets `assignee: self`; "close" sets `status: closed` and fills in `## Resolution`. Blocking is the `blocked_by` frontmatter list of ids; a ticket is unblocked when every id in `blocked_by` points at a `status: closed` ticket. The frontier is every ticket file with `status: open`, `assignee: none`, and an empty or fully-closed `blocked_by` — found by grepping frontmatter across `tickets/`, same role the JSON query plays on GitHub.

## Invocation

Two modes. Either way, **never resolve more than one ticket per session** — with the exception of research tickets.

### Chart the map

User invokes with a loose idea.

1. **Name the destination.** Run `/mine-grill` and `/mine-domain-model` to pin down what this map is finding its way to — the spec, decision, or change. The destination fixes the scope, so it's settled first.
2. **Map the frontier.** Grill again, **breadth-first** this time: fan out across the whole space rather than deep on any one thread, surfacing the open decisions and the first steps takeable now. **If this surfaces no fog** — the way to the destination is already clear, the whole journey small enough for one session — you don't need a map. Stop and ask the user how they'd like to proceed.
3. **Create the map** (label `wayfinder:map`): Destination and Notes filled in, Decisions-so-far empty, the fog sketched into **Not yet specified**.
4. **Create the tickets you can specify now** as child issues of the map (parented at creation via `--parent`) — then wire blocking edges in a **second pass**, once every new ticket's number is known. Everything you can't yet specify stays in the fog — the **Not yet specified** section.
5. **Fire the research subagents.** For each `research` ticket you just created, dispatch the `researcher` agent directly — not `/mine-research`, whose Phase 1/Phase 3 `AskUserQuestion` gates require a human that isn't there for an AFK dispatch. Derive the agent's input-contract fields (Proposal, Motivation, Flexibility, Constraints) from the ticket's own title and body, and default Depth to `normal` unless the ticket specifies otherwise. Fire every research ticket's agent in parallel; this now genuinely runs AFK, since `researcher` (unlike `/mine-research`) has no interactive gates. Point Output file path at a throwaway `research/<name>` branch, then append a context pointer to the ticket linking that file.
6. Stop — charting is one session's work; it hand-resolves nothing.

### Work through the map

User invokes with a map (URL, number, or local `.scratch/<effort-slug>/` path). A ticket is **optional** — without one, you pick the next decision, not the user.

1. Load the **map** — the low-res view, not every ticket body.
2. Choose the ticket. If the user named one, use it. Otherwise take the first frontier ticket in order (see [Query the frontier](#github-issues-default) or its local-markdown equivalent). **Claim it**: assign it to yourself before any work.
3. Resolve it — **zoom as needed**: fetch the full body of any related or closed ticket on demand; invoke the skills the `## Notes` block names. If in doubt, use `/mine-grill` and `/mine-domain-model`.
4. Record the resolution: post the answer as a **resolution comment**, **close** the issue, and **append a context pointer** to the map's Decisions-so-far.
5. Add newly-surfaced tickets (create-then-wire); graduate any fog the answer has made specifiable, clearing each graduated patch from **Not yet specified** so it lives only as its new ticket. If the answer reveals a ticket — this one or another — sits beyond the destination, **rule it out of scope** rather than resolving it on the route. If the decision invalidates other parts of the map, update or delete those tickets.

The user may run unblocked tickets in parallel, so expect other sessions to be editing the tracker concurrently.
