---
name: mine-elevate
description: "Use when the user says: \"what would a v2 look like\", \"how would we rebuild this\", \"next iteration of this design\", \"what improvements are we skipping\", \"what would a mature version look like\", \"what are we not considering here\", \"how would we make this more robust\", \"sophistication ceiling\", \"elevate this subsystem\". Surfaces upward improvements to an existing subsystem through three generator lenses — each candidate annotated with cost and the case against, ordered by signal. A counterweight to solo-dev myopia: it proposes, it never decides."
user-invocable: true
---

# Elevate

Look *up* at an existing subsystem and ask "if we did this over, knowing what we know now, what would we change?" Surface the upward moves that normally get skipped as "not worth it at this level." It is the inverse of `/mine-decompose` (which looks down and removes), and it is not a correctness review (`/mine-review`) or a debt audit (`/mine-audit`).

Done is an impact-ordered menu of independently-landable candidates, each with a cheap first move, a cost, and an honest case against, shown to the user to judge. It is a menu, not a ranked mandate.

## Arguments

$ARGUMENTS: the subsystem to elevate (a directory or module). If empty, ask which one; a coherent design unit works best. Never silently sweep the repo.

## The one rule

**Make upward options visible and let the user judge them; never decide for them that something isn't worth it.** Suppression is the echo-chamber myopia this skill exists to fight. Everything generated is shown, annotated and argued against, never filtered out.

Traps that defeat this:

- **Pre-filtering.** Agents drop upward ideas to look disciplined. Show everything; annotate, don't cut.
- **Self-grading.** A generator judging its own ideas inflates them, so generation and annotation run in separate subagent contexts, and generators never see each other's prompt or output (a lens that sees another's restraint regresses to the cautious mean).
- **Gold-plating.** The maximalist lens wants to recommend heavyweight patterns wholesale. Its job is provocation to nugget: the cheap thing inside the pattern, not the pattern.
- **Hallucinated authority.** "Mature peers do X" from memory is fabricated. Prior-art claims carry a real URL or `[no source found]`.

## How it runs

Subagents read code with Read, Grep, Glob, and `git`; they don't write or run analysis scripts. Intermediate files live in a `mktemp -d <scratchpad>/mine-elevate-XXXXXX` directory.

1. **Scope to one coherent unit.** Resolve $ARGUMENTS to the subsystem's source files. If it spans several subsystems or is the whole repo, pick the single unit that looks most worth elevating, say which and why, and proceed; three unfiltered lenses across a repo is a candidate dump.
2. **Generate.** Read `REFERENCE.md`. In a single message, dispatch three generators in parallel (`subagent_type: standard-worker`), one per lens: Friction, Latent, Maximalist. Each gets the subsystem file list, only its own lens block verbatim, the candidate record format, and an output path `<tmpdir>/<lens>-candidates.md`. No candidate cap; quality over count. They write only to their own file, so no worktree isolation. Verify each output exists and is non-empty.
3. **Annotate.** Dispatch one judge (`standard-worker`) in a context separate from every generator, with all three candidate files, the subsystem files, the judge prompt from `REFERENCE.md`, and output path `<tmpdir>/annotated.md`. One judge over the whole set keeps cost and case-against calibrated across lenses. It adds Cost and Case against to every candidate and changes nothing else.
4. **Render.** Read `<tmpdir>/annotated.md` and render inline with the report template in `REFERENCE.md`, in tier order Friction, Latent, Maximalist regardless of the order in the file (high signal first; the ordering is the volume control, not a filter). If there are no candidates at all, say so and stop.

## Next steps

Ask what to do with the candidates, even when the judge rates every one weak, since worth is the user's call. Build the menu from the candidates and name them in the descriptions. The outcomes are: implement some (recommend when Friction candidates are cheap and independently landable), file as issues via `/mine-create-issue` (when the strong ones are Latent or Maximalist and need design first), or note and move on (recommend when every candidate is weak or its case against dominates; this wins over the others).

Implementing a candidate is a refactor or feature change: pin behavior first per `refactoring-discipline.md` (confirm test coverage or write a characterization test, apply the minimal move, run the suite). After changes, say: "Run `/mine-review` before committing."
