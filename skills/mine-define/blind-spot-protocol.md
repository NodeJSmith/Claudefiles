# Blind Spot Self-Assessment

**Skip for trivial features.**

After all information gathering is complete (discovery, codebase reconnaissance, research) and before writing the design doc, surface your own uncertainty. This is not the Phase 2 completeness self-check (which asks "could I write each section?"). This one is epistemic: where is your understanding weakest, and what might you not be seeing at all.

Surfacing uncertainty is only half the job. An unverified assumption handed to the user is still unverified; you have moved the work, not done it. Most of what lands on this list is settleable without the user, and settling it is your job. Draft, triage, investigate what you can, and spend the user's attention only on the calls that are actually theirs.

The routing rules below were calibrated against 121 real items from 17 past runs of this step, then re-tested against the same corpus. Where a rule looks oddly specific, it is closing a failure that actually happened.

## Step 1: Draft the raw list

Write these three buckets for yourself. This is working material; the user does not see it in this form.

**What I'm least confident about** — areas where your understanding is thin, your assumptions are unverified, or you took something at face value.

**What might be missing from the picture** — concerns, adjacent effects, or perspectives that haven't come up, including things you noticed during investigation and chose not to pursue.

**Tradeoffs of the current direction** — known costs the approach imposes. Not defects: legitimate costs where the direction makes something else harder, forecloses a future option, or accepts a known limitation.

Four rules on what goes in:

**No minimums. Do not pad.** An empty bucket is a valid answer and fewer items is better. Fixed quotas are what historically filled this list with filler: observations, restated conclusions, and checks already done. There is no target count; a ceiling was tried and never bound, because padding comes from the floor.

**Every item is one unverified claim plus its consequence:** `<claim that is either true or false>` — if it's wrong, `<what changes>`. The consequence half is not decoration; Step 2 cannot route the item without it. This is the single strongest predictor of a usable item.

**If you verified it while writing it, it is not an uncertainty.** "I didn't investigate whether the docs reference `toggle_service` (they do — line 59)" is a fact for the design doc, not a blind spot. Delete it from this list.

**Deduplicate before triaging.** The same underlying fact often surfaces in two buckets wearing different clothes: an unverified call site in "least confident" and the design consequence of that same call site in "tradeoffs." Merge them into one item, or you will dispatch a probe and a question about the same thing.

## Step 2: Triage

Tradeoffs skip the gates below. Route that bucket per Step 4.

**Before anything else: route the claim, not the editorializing.** Items routinely raise something real and wave it off in the same breath: "this is a timing edge case in Wallos, not in our code," "this is the accepted cost," "this is the intended fix." A dismissal you wrote yourself is not evidence and does not change where the item goes. Strip the clause, route what's left. This one rule prevents the worst observed failure in this step: an agent suppressing its own finding, including an auth-bypass property and a silent breaking change for external callers.

Then run four gates in order. First match wins.

### Gate 1: Does this propose work beyond what the user agreed to?

Pulling in adjacent work — absorbing another tool, reorganizing a file the issue never mentioned — both changes what they get and spends effort they didn't authorize. That is theirs to approve, regardless of how the rest of the questions would route it. → **Ask**

### Gate 2: Is the design incomplete here, rather than possibly wrong?

Some items name work that hasn't been done: "I haven't worked out the exact mapping table," "the current snippet hydration won't surface it — the user would get a match with no visible reason why." There is no claim to test and no option set to choose between. The design has a hole.

Do not park these in Open Questions. That is how a hole ships. → **Extend**: write the missing design section now, before the doc.

### Gate 3: Is it a fact or a choice?

A **fact** has an answer that is true or false independent of what anyone wants. A **choice** is a call between options where no amount of investigation produces "the answer."

Conflating the two is the most common failure here, in both directions: real facts get routed to the user as though they were preferences, and design decisions get dressed up as uncertainties so they can be handed over. **If you can't tell which it is without investigating — "does this classmethod need different extraction treatment?" — treat it as a fact and probe.** Which one it is *is* the answer.

**If it's a fact — can an agent settle it without asking the user?** The question is *who*, not *where*. All of these count: reading this repo, reading a dependency's source or docs, a web search, running a read-only command against a live system, or a throwaway spike. If a real answer exists somewhere an agent can reach, it is settleable.

- **Yes, and the design changes if I'm wrong** → **Probe**
- **Yes, but being wrong only changes a detail** → **Note**
- **No — nobody can settle it, including the user** → **Decide**

That last case is real and recurring: "whether any external users already call these methods." The user cannot answer it either. Asking converts an unanswerable question into a shrug. Accept the risk explicitly, name the mitigation, and record both.

*Does the design change if I'm wrong?* means: would you write a *different design doc*: a different approach, a different module boundary, or a section you'd have to rewrite? More instances of the same mechanical edit is not a design change. If you cannot answer that without already knowing the probe's result (normal for "how many call sites are there"), treat it as **Yes**. A cheap probe beats a design written on a guess.

**If it's a choice — is it yours or theirs?**

- **Yours** — both options sit inside a decision the user already approved, and either is reversible → **Decide**
- **Theirs** — it changes what they get → **Ask**

Default to Decide once Gate 1 has cleared. A choice between two implementations of an approved approach is the designer's job; routing it to the user spends their attention on your work. Pick one, record it with the rejected alternative and why.

### Gate 4: Is it compound?

"The generator could either (a), (b), or (c) — I haven't verified which is least disruptive" is a fact and a choice, and the choice is *downstream* of the fact. Do not classify the halves in parallel and act on both. Record it as **Probe → then Decide**: dispatch the probe now, make the call from what comes back.

### Dispositions

| | Meaning |
|---|---|
| **Probe** | Dispatch a subagent to settle it now |
| **Extend** | Write the missing design section before the doc |
| **Decide** | You choose; record the choice and the rejected alternative in design.md |
| **Ask** | One `AskUserQuestion` for this item |
| **Note** | Record in Open Questions and move on |

**The failure mode this step exists to stop:** routing everything to Ask. Asking is cheap for you and expensive for the user, so the pull toward it is constant. And the user has *less* information than you do about which of your assumptions is load-bearing. "Does the retry wrapper already handle 429s?" is a Probe. "Should a 429 surface to the user or retry silently?" is an Ask.

**The opposite failure mode:** inflating consequences so every item becomes a Probe, turning this step into a second research phase. Most unverified assumptions are about details, not directions. If more than roughly half the list lands on Probe, the Phase 3 investigation was too thin; say so when you present the ledger.

## Step 3: Dispatch the probes

Show the ledger and dispatch in the same turn. Do not ask permission first. Judging a list of research questions would require the user to do the research themselves.

> Before writing the design doc, here's what I'm unsure of and what I'm doing about each:
>
> - **Probing now:** [one line per Probe item]
> - **For you:** [one line per Ask item, coming once the probes land]
> - **Deciding myself:** [one line per Decide item, with the call you're making]
> - **Design gap to close first:** [one line per Extend item]
> - **Noted for Open Questions:** [one line per Note item]

Keep this order and the Step 5 report order aligned: Probe, Ask, Decide, Extend, Note.

Omit any empty bucket. If nothing landed on Probe, show the ledger anyway and go to Step 4; the user still needs to see what you triaged away, and that is their chance to redirect you.

Record each dispatch first. Skip these `cfl` calls if tracking was disabled in Phase 1 (no `<spec_number>` set):

```bash
cfl dispatch blind-spot-probe --agent-type general-purpose --model sonnet --spec <spec_number>
```

Record each `dispatch_id`, and call `cfl dispatch end <dispatch_id>` as each probe returns.

Dispatch every Probe in a single message so they run in parallel:

```
Agent:
  subagent_type: general-purpose
  model: sonnet
  prompt: |
    Settle one factual claim. Report what you find; do not fix anything.

    Claim: <the assumption, stated so it is either true or false>
    Why it matters: <what changes in the design if it is false>
    Where to look: <repo paths, a dependency's source, specific docs, a command
                    to run — whatever you already suspect will settle it>

    You may read this repo, read installed dependency source, search the web, and
    run read-only commands. You may write a throwaway script under /tmp if that is
    what settles it. Do not edit project files, and do not run anything that
    mutates a live system, database, or remote service.

    Report exactly:

    VERDICT: CONFIRMED | REFUTED | INCONCLUSIVE
    EVIDENCE: file:line, a doc URL, or the command and its output
    CONSEQUENCE: one sentence — if REFUTED, what is actually true instead

    INCONCLUSIVE is a real answer. Use it when nothing you can reach settles the
    claim, and say what you tried and why it did not decide. Do not guess to
    avoid it.
```

## Step 4: Ask the Asks

Only after the probes return; a refutation can change what the right question is, or remove the need for it. Drop any Ask the probes made moot and say which ones you dropped.

One `AskUserQuestion` per item, never batched. These are genuine either/or decisions and each needs its own answer:

```
AskUserQuestion:
  question: "<the decision, stated concretely>"
  header: "<2-3 word topic>"
  multiSelect: false
  options:
    - label: "<option A> (Recommended)"
      description: "<what it costs and what it buys>"
    - label: "<option B>"
      description: "<what it costs and what it buys>"
    - label: "Leave open"
      description: "Record in Open Questions and decide during implementation"
```

Recommend an option when you have a view, and put it first. If you genuinely do not have one, do not manufacture it.

### Tradeoffs are one question, not one each

A tradeoff is a cost only the user can accept, so per-item triage produces nothing; historically every tradeoff routed to the same cell. Sort by shape instead, then batch what's left.

**First, pull out the ones that aren't costs at all.** Three shapes hide in this bucket and none of them answer "is this unacceptable?":

- An unresolved design gap ("the Protocol needs to be reconciled", "it needs a different dispatch mechanism") → **Extend**, per Gate 2.
- Known, planned future work ("a follow-up migration is likely") → **Note**.
- Two named alternatives ("thin wrappers vs. update all consumers directly") → its own **Ask** with both options as choices. Collapsing an either/or into a yes/no throws away the alternative the item already worked out.

**Then drop only what the user actually accepted.** Not what *you* decided was acceptable. The item must cite where they accepted it: a discovery answer, an earlier decision in this conversation. "(confirmed acceptable)" with a traceable source qualifies; "this is the accepted cost of staying simple" does not.

This is deliberately strict. When self-dismissal was allowed to drop items, it suppressed an auth-bypass property and a silent breaking change for external callers, both dropped on the agent's own say-so, neither ever shown to the user. If you cannot point to where it was accepted, it goes in the question.

Put the survivors in a single question:

```
AskUserQuestion:
  question: "These are the costs this direction imposes. Is any of them unacceptable?"
  header: "Tradeoffs"
  multiSelect: true
  options:
    - label: "<cost 1, one line>"
      description: "<what it makes harder or forecloses>"
    - label: "<cost 2, one line>"
      description: "<what it makes harder or forecloses>"
    - label: "All acceptable"
      description: "Proceed; these are recorded in the design doc"
```

If the user flags one, that single cost becomes its own conversation; it is a design change, not a checkbox.

## Step 5: Report and record

Report in this order, so what changed comes first and what didn't comes last:

1. **Refuted** — each with what is actually true and how the design shifts.
2. **Answered** — the user's Step 4 decisions, one line each.
3. **Decided** — each call you made, with the alternative you rejected.
4. **Extended** — each design gap you closed, and what you wrote to close it.
5. **Confirmed** — one line per probe with the evidence that settled it. These stop being assumptions; cite the evidence in design.md instead of hedging.
6. **Still open** — Notes plus any INCONCLUSIVE probes, with what was tried.

**Every one of these carries into Phase 4.** Refutations get folded into the sections they invalidate. The user's answers get written in as decisions, with the option they chose. An answer you collected and never recorded is the same as never having asked. Your own Decides get recorded with the alternative you rejected and why. Extended gaps become the sections you wrote. Confirmed facts get stated with their evidence rather than hedged. Only item 6 goes to Open Questions.

If a refutation invalidates the direction rather than a detail, stop and say so before writing design.md. That is a return to investigation, not a line in a section.

Record the gate. Skip if cfl tracking was disabled in Phase 1:

```bash
cfl gate define-blindspot --verdict <v> --spec <spec_number> \
  --data '{"probed": <N>, "refuted": <R>, "inconclusive": <I>, "asked": <A>, "decided": <D>, "extended": <E>, "noted": <X>}'
```

Verdict mapping, applied mechanically from the counts: any `refuted` or `extended` → FAIL; otherwise any `inconclusive` → WARN; otherwise PASS. Emit SKIPPED only when Step 1 produced no items at all; a run where everything routed to Note is a real triage outcome, not an absent one.

`extended` counts as FAIL for the same reason `refuted` does: the doc was about to ship with a hole in it and this step caught it.

`noted` is recorded so the counts sum to the size of the raw list. Without it, the Probe-to-total ratio that Step 2 tells you to watch cannot be reconstructed after the fact.

FAIL here does not mean the design is bad. It means the step did its job and caught a wrong assumption before it reached the doc. The gate record is what makes it answerable later whether this step earns its cost.
