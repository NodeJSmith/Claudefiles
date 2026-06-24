---
name: mine-elevate
description: "Use when the user says: \"what would a v2 look like\", \"how would we rebuild this\", \"next iteration of this design\", \"what improvements are we skipping\", \"what would a mature version look like\", \"what are we not considering here\", \"how would we make this more robust\", \"sophistication ceiling\", \"elevate this subsystem\". Surfaces upward improvements to an existing subsystem through three generator lenses — each candidate annotated with cost and the case against, ordered by signal. A counterweight to solo-dev myopia: it proposes, it never decides."
user-invocable: true
---

# Elevate

Looks *up* at existing code and asks "if we did this over, knowing what we know now, what would we change?" — surfacing the upward moves that normally get skipped as "not worth it at this level." The deliberate inverse of `/mine-simplify` and `/mine-decompose` (which look down and remove). It produces an impact-ordered menu of independently-landable candidates, each with a cheap first move, a cost, and an honest case against — **not** a ranked mandate.

Use it to pressure your own design choices on a subsystem you suspect could be better. It is **not** a correctness review (`/mine-review`), a debt audit (`/mine-audit`), a collapse pass (`/mine-simplify`), or a UI overhaul (`/i-overdrive`).

## Arguments

$ARGUMENTS — the subsystem to elevate (a directory or module). Empty → the skill asks. It does not silently sweep the repo.

## The one rule

**The skill's job is to make upward options visible and let *you* judge them — never to decide for you that something isn't worth it.** Suppression is the exact myopia this exists to fight. Everything generated is shown; nothing is filtered out. The judge annotates and argues against, but it never deletes a candidate.

## Named failure modes to resist

- **Pre-filtering ("not worth it at this level").** Agents suppress upward ideas to look disciplined. That instinct is wrong here — it *is* the echo chamber. Show everything; annotate, don't cut.
- **Self-grading.** A generator judging its own ideas inflates them. Generation and annotation run in **separate subagent contexts**.
- **Gold-plating dump.** The maximalist lens wants to recommend heavyweight patterns wholesale (tutorial bias). Its job is provocation→nugget: extract the cheap thing inside the pattern, not the pattern.
- **Hallucinated authority.** "Mature peers do X" from memory is fabricated. Prior-art claims carry a real URL or `[no source found]`.

## How to analyze

Subagents read code directly with Read, Grep, Glob, and `git`. Do NOT write or run analysis scripts.

## Phase 1: Scope to one subsystem

Run `get-skill-tmpdir mine-elevate` — note the dir; all intermediate files live here.

Resolve $ARGUMENTS to the subsystem's source files and confirm they're a **single coherent design unit**:
- **A directory/module** → expand to its source files; that's the unit.
- **Spans several distinct subsystems, or is the whole repo** → do not fan out across all of them. Pick the one unit that looks most worth elevating, state which and why, and proceed on it. Three un-filtered lenses across a repo is a candidate dump.
- **Empty or all paths missing** → ask:

```
AskUserQuestion:
  question: "Which subsystem should I elevate? (One coherent unit works best.)"
  header: "Target"
  multiSelect: false
  options:
    - label: "A specific module"
      description: "I'll name a directory or module"
    - label: "Specific files"
      description: "I'll list the files for one subsystem"
```

Resolve the user's answer — the module or files they name (typically via the free-text option) — to the subsystem's source file list. Do not build subsystem-detection logic; the user's pointer decides the boundary.

## Phase 2: Generate (three lenses, in parallel)

Read REFERENCE.md. Dispatch **three generator subagents in a single message** (parallel; `model: sonnet`, `subagent_type: general-purpose`; read-only, no worktree isolation). One per lens — **Friction**, **Latent**, **Maximalist**. Each receives: the subsystem file list, **only its own** lens block from REFERENCE.md verbatim, the candidate record format from REFERENCE.md, and an output path `<tmpdir>/<lens>-candidates.md`. There is no cap on candidate count — quality over count.

Keep the generators isolated: each receives **only its own** lens block and the subsystem — never another generator's prompt or output file. If one lens sees another's restraint, the maximalist lens regresses to the cautious mean.

Model note: `sonnet` is the default; the Latent and Maximalist lenses are architecture-flavored, so `opus` may earn its place there — tune from usage, don't commit up front.

After they complete, verify each output file exists and is non-empty.

## Phase 3: Annotate (one independent judge)

Dispatch **one** judge subagent (`model: sonnet`, `subagent_type: general-purpose`) — not three. One judge over the whole set keeps cost and the case-against *calibrated* across lenses. It runs in a context separate from every generator, which is what preserves no-self-grading.

It receives: all three candidate files, the subsystem files, the judge prompt from REFERENCE.md, and output path `<tmpdir>/annotated.md`. Its job is to add **Cost** and **Case against** to every candidate — including arguing against ideas it doubts — and to add nothing else. It must not drop, merge away, or reorder candidates.

## Phase 4: Render and offer next steps

Read `<tmpdir>/annotated.md`. Render the report inline using the template in REFERENCE.md. Sort candidates by their lens tag into the fixed tier order **Friction → Latent → Maximalist**, regardless of the order they appear in `annotated.md` (high signal first; the reader stops when they lose interest — this ordering is the volume control, not a filter). Then:

```
AskUserQuestion:
  question: "What would you like to do with these?"
  header: "Next steps"
  multiSelect: false
  options:
    - label: "Implement some"
      description: "Pick candidates to build now; each is independently landable"
    - label: "File as issues"
      description: "Turn selected candidates into issues via /mine-create-issue"
    - label: "Note and move on"
      description: "Acknowledged — no changes this session"
```

**Implementing any candidate is a refactor or a feature change** — pin behavior first per `refactoring-discipline.md`: confirm test coverage (or write a characterization test), apply the minimal move, then run the suite. After changes, say: "Run `/mine-review` before committing."
