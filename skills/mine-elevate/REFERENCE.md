# Elevate — Reference

Lens prompts, judge prompt, and templates for `mine-elevate`. Referenced by SKILL.md — do not reference further files from here.

---

## Candidate record format (all generators emit this)

Each candidate is one block. Fill only the generator fields — leave **Cost** and **Case against** out; a separate judge adds them.

```
**<Title>** (<lens>)
- Motivation: <why this — see your lens>
- Minimal move: <the cheapest concrete first step; cite file:line where it touches existing code>
- Escalation: <the gold-plated version, if any — optional; omit the line if none>
- Prior art: <real URL, or [no source found]>
```

The **Prior art** line is **required on every Latent candidate**. For Friction and Maximalist candidates, include it only if there's a genuine source; otherwise omit the line entirely — do not fill it to satisfy the format.

Shared rules for every generator:
- **Minimal-variant-first.** The minimal move is the cheap version. The escalation is the optional gold-plate. Lead with cheap; never bundle the two as one candidate (that bundling is what made past candidates look like overkill).
- **Prior-art discipline.** Any "mature codebases do X" claim carries a real URL or `[no source found]` — never cite from memory; that's hallucinated authority. (Required on Latent; see above for the other lenses.)
- **Distinct and landable.** Each candidate is one independently-shippable move. Don't pad the list; quality over count, no cap.
- **Don't manufacture.** If your lens turns up little for this subsystem, return few or none and say so plainly. A thin honest list beats a padded one.
- **You do not judge.** Do not add cost, verdict, or a case against — that's a separate context's job. Generating and grading your own ideas inflates them.
- Write all your candidates to the output path you were given.

---

## Lens 1 — Friction / v2 (high signal)

> Knowing what we know now, if we rebuilt this subsystem, what would we change? This lens is **reactive** — anchor every candidate in friction the code has *actually* felt: awkward call sites, special-case branches, duplicated handling, comments apologizing for something, `TODO`/`FIXME`, signatures that fight their callers, churn (`git log`). Each candidate is the next iteration that removes real felt friction. If you can't point to the friction in the code, don't invent it — that's what the other lenses are for.

## Lens 2 — Latent / peer-adoption (medium signal)

> What would a mature peer codebase adopt here that this one hasn't felt the need for yet? This lens is **proactive** — the safeguards you only miss *after* they bite, so felt friction won't surface them: property-based tests, first-class observability/metrics, making illegal states unrepresentable, invariants enforced at the boundary, idempotency, typed errors over stringly-typed ones. Ground every candidate in **real prior art** — a named library, framework, or article with a URL, or `[no source found]`. "Mature codebases do X" from memory is hallucinated authority; cite or mark it.

## Lens 3 — Maximalist / provocation (low signal, high divergence)

> Take the most sophisticated, enterprise, pattern-heavy version of this subsystem as a thought experiment — event sourcing, CQRS, plugin architecture, a DI container, an explicit state machine, the works. Most of it is overkill here, and that's expected. Your job is **not** to recommend the pattern. It's **provocation → nugget**: name the heavyweight pattern, then extract the cheap thing hiding inside it that's genuinely worth doing. *"The Saga pattern is overkill, but the nugget is: your three-step publish has no rollback story — here's the ten-line version."* The pattern is the lens; the nugget is the candidate. Put the nugget in **Minimal move** and the full pattern in **Escalation**. A candidate that's just "adopt CQRS" with no extracted nugget is a failure of this lens.

---

## Judge prompt (one independent annotator)

> You are the judge — an independent annotator who did **not** generate these candidates. Your job is to judge them honestly, including arguing against the ones you doubt. **Copy each candidate block verbatim** — its title, lens tag, and every generator field unchanged, including `file:line` citations — then append exactly these two new bullet lines to each, and change nothing else:
>
> - **Cost:** qualitative effort + blast radius. E.g. "an evening; touches the run loop's core branch; low risk if the default preserves today's behavior." No story points, no numbers.
> - **Case against:** the strongest honest reason to skip it. If the idea is solid, name the condition under which it isn't worth it ("only if missed triggers have never caused a visible bug"). **Never write "none"** — every candidate costs attention; surface the skeptical read.
>
> Calibrate cost across *all* candidates on one scale, so "an evening" means the same thing in every lens. Do **not** drop, merge, reorder, rewrite, paraphrase, or filter candidates — only append the two bullet lines. Group output in this exact order — **Friction, then Latent, then Maximalist** — preserving each generator's order within a lens. Write every candidate to the output path.

The judge annotates; it never deletes. A weak candidate gets a sharp case against, not removal — the user decides, not the skill.

---

## Report template (rendered inline by the main session)

```markdown
## Elevate: <subsystem>

**Scope:** N files — the <subsystem> subsystem

### How to read this
Three lenses, highest signal first. **Friction** = what we've felt; **Latent** = blind spots a mature peer would cover; **Maximalist** = browse for the occasional nugget. This is a menu, not a mandate — nothing here says "do all of it." Each candidate is independently landable. Skim down; stop when you lose interest.

### Friction / v2
[candidates]

### Latent / peer-adoption
[candidates]

### Maximalist / provocation
[candidates]
```

Render each candidate as:

```markdown
**<Title>**
- *Motivation:* …
- *Minimal move:* …
- *Escalation:* …            (omit if none)
- *Prior art:* …             (omit if none for Friction/Maximalist)
- *Cost:* …
- *Case against:* …
```

If a lens returned nothing, show the heading with one line: "Nothing surfaced through this lens for this subsystem." Don't hide the empty lens — the absence is information.
