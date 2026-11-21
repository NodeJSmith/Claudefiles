---
name: mine-writeup
description: "Use when the user says: \"write this up\", \"write up for my boss\", \"summarize this for leadership\", \"executive summary\", \"distill this research\", \"write a summary for leadership\", or needs to turn technical research into a readable document for a specific audience."
user-invocable: true
---

# Writeup

Turn technical research, investigation notes, or dense working documents into a document a specific reader can act on. The input is messy and thorough; the output is short enough to read and complete enough to decide from.

This skill is an editor, not a researcher. It works from existing material and doesn't discover findings, expand scope, or add sections the user didn't ask for. Long research leaves findings that feel load-bearing but aren't all load-bearing for the reader, and the pull to include everything produces documents nobody reads. See [Editorial Discipline](#editorial-discipline).

## Arguments

$ARGUMENTS — path(s) to the source material, space-separated. If empty, ask what to distill. If a path doesn't resolve, say so plainly rather than surfacing a raw tool error.

Read every source file end to end first. The source files are read-only to this skill.

If the user didn't say where to save the writeup, run `mktemp -d <scratchpad>/mine-writeup-XXXXXX`, write to `<dir>/writeup.md`, and tell them where.

## Know the reader first

Before writing, settle who reads this, what they should do after reading (decide, approve an approach, understand scope, or just be informed), and how long it should be. Ask for whatever the user's prompt didn't already answer, together in one `AskUserQuestion` call. Let the answers drive depth, tone, and which sections exist: a one-page note for a manager leads with the bottom line and drops situation setting; a longer one for leadership curates findings; even an unbounded one applies the tests below to every paragraph.

## Scope, outline, and reader brief

Define the closed-world scope (what this covers, and "everything else stays in the source docs"), then propose an outline, then draft the reader brief for the cold read below. Present them together and get approval through `AskUserQuestion` (approve, or adjust and re-confirm). Approval is the single gate for scope and structure; once approved, scope is locked and no topic, section, or finding outside it is added unless the user asks. No prose is written before approval.

The outline needs only the sections this reader needs, and you say which you dropped and why. What a good one tends to contain:

- **Bottom line** (always): everything the reader needs if they stop here — what you found, what it means, what you need from them. The answer, not the journey.
- **Findings** (when the source holds investigation results), each as fact → so what for the project, with technical evidence referenced rather than inlined.
- **Decisions needed** (when the outcome is "make decisions"): a table of what needs deciding, who can decide it, and what it gates, ordered by urgency. **Proposed approach** (when the outcome is "approve an approach"): the recommendation, key tradeoffs, and what sign-off enables, concrete enough that the reader knows exactly what they're approving.
- **Situation** only if the reader lacks context; **real scope** if the work is bigger than expected (what must be done, by whom, in what order, showing what gates what, no hour or week estimates unless asked); **risks** only the few that could change the shape of the work, each with what could go wrong, why it matters, and what to do.
- **Appendix pointer** (always): one line to the full source material.

The tests that decide what survives (duplicated from `rules/common/writing-discipline.md` by design, since this skill must be self-contained; if you change them here, update that file too):

- **So What test.** Does this finding change a decision the reader needs to make? If not, it belongs in the source material, not the writeup.
- **Forwarding test.** If the reader forwards this to someone with less context, will it still make sense? If a section requires the reader to explain it, rewrite or cut.
- **30-second test.** Can a reader get the bottom line from the first paragraph alone? If not, the document is structured wrong. Restructure before adding detail.

### Reader brief

The audience answer is a label; the cold reader needs knowledge boundaries. Infer them from the audience and source material:

- **Persona:** role, what they know (their domain, business context), and what they do NOT know (this work's internal vocabulary, methods, earlier drafts, anything only the sources contain). "Doesn't know statistics vocabulary (precision, holdout, confidence interval)" beats "non-technical."
- **Reading goal:** what the reader needs to do with the document.
- **Intent:** `decide` when the reader must make decisions, `recommend` when they must approve an approach, `describe` when they should understand scope or just be informed.
- **Deliberate positions:** statements the writeup makes on purpose that could look like they break the intent or invite a finding, such as firm requirements in a descriptive writeup, or qualitative wording ("most teams," "a small share") where an exact number wouldn't change what the reader does. Often none.
- **Intended takeaways:** the 3-5 things the reader should be able to repeat after one read, with a key number only where the decision depends on it. The reader never sees these; the comparison below uses them.

## Writing

Write the full draft to the writeup file. It should work at three reading speeds: 30 seconds (the bottom line alone gives the answer), 3 minutes (headers and first sentences give the shape), 30 minutes (the full read gives the reasoning). A section that only works at the last speed needs rewriting.

Answer first, evidence second, in every section. Use plain language: define a needed technical term on first use, otherwise use the plain word. Prefer concrete to abstract ("the network path doesn't exist yet" over "infrastructure prerequisites remain outstanding"). One idea per paragraph. Use a table when the same shape repeats three or more times.

Keep a number only when the decision depends on it. Every number invites the reader to check it (out of what, which population, which period), and one the reader doesn't need costs that check for nothing. Ask whether the reader would act differently at 40% than at 60%; if not, say it in words ("most," "roughly double") or cut it, and add the substitute wording to the brief's deliberate positions.

Re-read the file from disk before every write so user edits are preserved. Edit sections in place when the user wants one rewritten, cut, or shortened.

## Cold read

The three-speed check is the author's, and an author can't un-know what they meant. Before presenting, have a reader with the persona's knowledge read the draft cold. Skip it only when the gap is small (a short writeup for a reader who shares the context, with few numbers to check), and say you skipped it and why. Run it whenever the reader is far from the work or the writeup leans on numbers.

Isolation is what makes it a cold read, so keep it:

1. `mktemp -d <scratchpad>/mine-writeup-reader-XXXXXX`, and copy the writeup in as `document.<ext>` (same extension). Nothing else goes in that directory.
2. `mktemp -d <scratchpad>/mine-writeup-key-XXXXXX`, and write the intended takeaways to `<key-dir>/intended-takeaways.md`. Never give the reader this path or quote the takeaways in its prompt.
3. Dispatch the `cold-reader` agent with the brief only: `document` (the copied path), `persona`, `reading_goal`, `intent`, `deliberate_positions`, and no commentary of yours. If it returns `{"error": "incomplete brief", ...}`, fill the named fields and dispatch again.

The reader's findings are hypotheses about the text; the user's scope and the stated intent outrank its reactions.

**Teach-back.** Mark each intended takeaway `landed`, `partly` (present but late, vague, or missing a number the decision depends on), `missed`, or `misread`, and note any point the reader took away that you didn't intend, which is often a misreading caused by emphasis. Every takeaway that isn't `landed` is a fix whether or not the reader raised a finding, since a reader can only quote text that exists. Write each fix from the scope-locked sources: add the point, move it earlier, give it its number, or reword what misled. If the sources can't support it (the number isn't in them), don't invent it; list it for the user as a possible follow-up.

**Perceived asks.** For `decide` and `recommend`, the reader's `perceived_asks` should name the actual decision or recommendation; a reader who leaves with the wrong ask is the most expensive failure for those writeups. For `describe` the reader should perceive no ask. A wrong, missing, or unwanted ask is a fix too, planned the same way: state the ask plainly and early, or reword the passage that reads as a request.

**Verify every finding before acting on it.**
- `unsupported-number`: first ask whether the reader needs the number at all. If not, remove it or reword it qualitatively and add the wording to the deliberate positions, since added context to an unneeded number only adds more to check. If needed, check it against the sources: fix it if wrong or irreconcilable, and if right but unexplained, add the denominator, population, or period.
- A finding about wording the brief lists as a deliberate position, or one that conflicts with the stated intent: set it aside. The reader is told to check deliberate positions, so it may still raise one.
- A finding that asks for content outside the scope (a cost analysis the sources lack, a new section): don't add it; list it as a possible follow-up.
- Anything else: judge whether it's real for this audience and set it aside with a one-line reason if not.

Keep the reader's `works_well` passages intact when planning fixes, since a revision that removes what worked leaves the reader worse off. A verified fix still wins when the passage itself is the problem (a wrong number, content outside scope); flag that conflict beside the fix.

### Presenting the results

The user decides from what's on screen, so send with `SendUserMessage` before the draft: the takeaway table (plus the perceived ask if wrong); the planned fixes grouped by section (verified findings with quote and fix, takeaway fixes, the ask fix); out-of-scope requests and set-aside findings, each with its reason; and the reader's `overall_verdict`, `forwardable` answer, and `works_well` passages.

If everything landed and nothing needs fixing, say so and present the draft. If the verdict is `lost`, or several takeaways were missed or misread, line edits won't help: recommend restructuring the sections that lost the reader. Otherwise ask how to handle the fixes (apply all, apply a picked subset, or skip and present as-is), building the options from what the reader found per `rules/common/interaction.md`.

After applying fixes, offer a second cold read on a freshly copied document with a fresh dispatch when the fixes changed enough that the first read no longer describes the draft; a second read finds what the first missed. Don't loop beyond that unless asked. Then present the (revised) draft.

## Editorial Discipline

Don't re-expand: content the user cut doesn't return in another section under a different framing.

## Handoff

When the writeup is complete, say where it is and where the source material is for anyone wanting the evidence: "Writeup saved at `<path>`. Source material is at `<source paths>` for anyone who wants the full evidence." If the user wants to refine the prose, point them at `/mine-humanize <path>`.
