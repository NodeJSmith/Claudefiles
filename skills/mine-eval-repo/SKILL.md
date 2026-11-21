---
name: mine-eval-repo
description: "Use when the user says: \"evaluate this repo\", \"should I use this library\", or wants to assess a third-party dependency. Checks test coverage, code quality, maintenance health, bus factor, and maturity."
user-invocable: true
---

# Evaluate Repository

Answer "should I use this?" for a third-party GitHub repo: is it worth adopting as a dependency, tool, or reference. Done is a verdict grounded in evidence from the repo itself (files, line counts, commit data, test and CI config), calibrated to what the user would use it for, with a clear next step.

## Arguments

$ARGUMENTS: a GitHub URL or `owner/repo` (`/mine-eval-repo pallets/flask`). If empty, ask for the repo.

## Gathering evidence

Create a directory with `mktemp -d <scratchpad>/<repo-name>-eval-XXXXXX` (repo name only, no owner prefix or `/`, e.g. `flask`) and clone the repo into it. Fetch metadata first:

```bash
gh repo view <owner/repo> --json name,description,createdAt,updatedAt,pushedAt,stargazerCount,forkCount,issues,pullRequests,licenseInfo,primaryLanguage,languages,defaultBranchRef,isArchived,isFork
```

Then dispatch parallel `standard-worker` subagents over the clone, one per question the verdict depends on:

- **History and maintenance.** How old is it, and is activity sustained, bursty, or dormant? Release cadence and versioning; contributor count and how concentrated commits are (bus factor); how much is bot or AI-agent authored (dependabot, renovate, jules, copilot, devin).
- **Tests and CI.** How much is tested relative to source, with what framework; whether coverage is configured and enforced; what CI runs and across what matrix, including security scanning; whether tests assert behavior and edge cases or only that functions exist.
- **Code quality.** Structure, god files, type safety, linting and whether CI enforces it, dependency count and health, smells actually found in the main source (duplication, deep nesting, broad catches, dead code), documentation, security basics.
- **API and design.** The public surface and how clean it is, error handling, configuration, extension points, and how often breaking changes appear in changelogs.

## Interpreting it

Interpret, don't dump. Rate maintenance, tests, code quality, documentation, community, bus factor, and security each on a short scale with the evidence behind it (for example Active/Sporadic/Dormant/Abandoned for maintenance; Healthy 3+/Risky 2/Critical 1 for bus factor). Call out the non-obvious red flags (high share of AI-generated commits, a single contributor with no succession plan, an incompatible license, known vulnerable dependencies) and green flags beyond the baseline (test matrix across runtimes, enforced coverage thresholds, security scanning, active triage). Obvious failings like no tests are already visible in the ratings.

Calibrate to the use. A personal utility with 20 stars and one maintainer can be fine for light scripting; the same profile on a payment library is a hard no. A single red flag isn't disqualifying, but several compound. Distinguish "mature and stable" from "dead". AI-generated code is a signal to look closer, not a verdict. And if wrapping the underlying API directly is simpler than the library, say so rather than recommending a dependency because it exists.

## The report

Present conversationally: overview; vitals (created, last activity, version, stars/forks, contributors and bus factor, license, language); the ratings with evidence; red and green flags; 2-4 specific code observations grounded in what you read; test coverage findings; then the verdict, one of **Adopt with confidence**, **Adopt with caution**, **Use for reference only**, **Avoid**, or **Build your own** (wrapping the underlying API is safer than this abstraction), with 2-3 sentences of reasoning.

## Next step

For *Adopt with confidence* and *Avoid* the verdict is the answer: end with it, no question. For the others, ask, tying the options to the verdict: offer the outcomes that fit it, recommend the one it points to, and name the specific concern in each description. Keep "dig deeper" (naming the gaps worth checking) and "skip it" available alongside the fitting ones: adopt it for *Adopt with caution*, look for alternatives for *Use for reference only*, build it yourself for *Build your own* (a library search would contradict that verdict). At most four options. The question is always asked before acting; the verdict never starts the work on its own.

Building it yourself means implementing the wrapper now through the normal pre-commit reviewers, covering only what the project needs from the underlying API and borrowing from the evaluated repo where its code was sound. Do it before cleanup removes the clone. Digging deeper means investigating the weakest-rated dimensions and red flags, then reporting; ask only if the user names something else. Looking for alternatives means `WebSearch` for competing projects and then offering an abbreviated evaluation of the top 2-3 (the ratings only, no full subagent sweep).

## Cleanup

When the evaluation is done, remove the clone: `rm -rf "<dir>"`. This is intentionally not pre-approved, so the user sees a permission prompt.

## Not this skill

No code is written before the next-step gate. Not an audit of the user's own codebase (`/mine-audit`), not integration feasibility (`/mine-research`), and not a thorough security audit, benchmark, or license-compatibility analysis; it flags the license and basic security hygiene only.
