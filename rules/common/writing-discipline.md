---
tool: claude, antigravity
---

# Writing Discipline

The prose equivalent of `laziness-protocol.md`. LLMs default to completionist writing: including every finding, hedging every claim, expanding scope to cover adjacent topics. Counter it by treating the reader's time as the binding constraint, not coverage.

This applies to any prose task: writeups, briefs, documentation, research summaries, messages drafted for the user. It does not apply to code or commit messages (those have their own conventions).

## Rules

- **The reader's question comes first.** Start with the answer, not the reasoning. A reader who knows the answer can choose to read the reasoning; a reader buried in reasoning may never reach the answer.
- **Cut before you polish.** When a draft is too long, remove content. Do not compress. Compression keeps every idea but tightens the wording, so density goes up and clarity drops. Removal drops whole ideas, so what's left stays clear.
- **One idea per paragraph.** If a paragraph is doing two things, split it or cut the weaker half.
- **Earn every section.** A section that does not change what the reader knows or does after reading it does not belong. Apply the So What test: does this change a decision? If not, cut or demote to an appendix reference.
- **Do not hedge to preserve coverage.** "This may or may not apply" is not a finding. Either state the finding and its confidence, or leave it out.
- **Respect editorial direction.** When the user says to cut, shorten, or remove, do it. Do not argue, relocate to an appendix, summarize into a smaller section, or reintroduce the content elsewhere. The user knows their audience.

## The Completionist Trap

Long research sessions produce accumulated findings that feel load-bearing. They are not all load-bearing for the reader. The instinct to include everything is a training artifact: thoroughness correlates with helpfulness in most contexts, but in writing it correlates with documents that don't get read.

When writing from source material, apply:

- **So What test.** Does this finding change a decision the reader needs to make? If not, it belongs in the source material, not the writeup.
- **Forwarding test.** If the reader forwards this to someone with less context, will it still make sense? If a section requires the reader to explain it, rewrite or cut.
- **30-second test.** Can a reader get the bottom line from the first paragraph alone? If not, the document is structured wrong. Restructure before adding detail.

This rule's So What, Forwarding, and 30-second tests are duplicated in `skills/mine-writeup/SKILL.md` by design (the skill must be self-contained). If you change the tests here, update the other file too.
