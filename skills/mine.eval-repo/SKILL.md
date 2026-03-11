---
name: mine.eval-repo
description: Evaluate a third-party GitHub repo before adopting it. Assesses test coverage, code quality, maintenance health, contributor bus factor, and project maturity — then gives a clear recommendation.
user-invokable: true
---

# Evaluate Repository

Thorough assessment of a third-party GitHub repository to decide whether it's worth adopting as a dependency, tool, or reference. Answers the question: "Should I use this?"

## Arguments

$ARGUMENTS — a GitHub URL or `owner/repo` identifier. Examples:
- `/eval-repo https://github.com/pchuri/confluence-cli`
- `/eval-repo pallets/flask`
- Empty: ask the user for the repo

## Phase 1: Gather Data

Run `get-skill-tmpdir <repo-name>-eval` to create a unique directory, then clone the repo into it. Launch **parallel subagents** to collect data. All subagents work from the cloned repo.

Before launching subagents, fetch repo metadata with `gh`:

```bash
gh repo view <owner/repo> --json name,description,createdAt,updatedAt,pushedAt,stargazerCount,forkCount,issues,pullRequests,licenseInfo,primaryLanguage,languages,defaultBranchRef,isArchived,isFork
```

### Subagent 1: Project History & Maintenance (`subagent_type: Bash`)

Run git commands to assess project health over time:

- **Age**: first and most recent commit dates
- **Commit count**: total commits
- **Commit frequency**: commits per month over the project's lifetime — look for sustained activity vs. bursts and abandonment
- **Release cadence**: `git tag` — how many releases, how often, is semantic versioning used?
- **Recent activity**: commits in last 3 months — is this actively maintained or dormant?
- **Contributors**: `git shortlog -sne --all` — count of contributors, concentration of commits (bus factor)
- **Bot commits**: look for dependabot, renovate, semantic-release-bot, AI agents (jules, copilot, devin) — what proportion of commits are automated or AI-generated?

### Subagent 2: Test Coverage & CI (`subagent_type: Explore`)

- **Test files**: find test directories and files, count them relative to source files
- **Test framework**: identify what's used (jest, pytest, mocha, go test, etc.)
- **Coverage configuration**: look for coverage settings in config files (jest.config, pytest.ini, .coveragerc, nyc config)
- **Coverage reports**: check if coverage thresholds are enforced
- **CI/CD**: read workflow files (.github/workflows/, .gitlab-ci.yml, etc.) — what runs on PR/push? Is there a test matrix? Security scanning?
- **Test quality signals**: are tests just checking that functions exist, or do they test behavior with meaningful assertions and edge cases?

### Subagent 3: Code Quality (`subagent_type: Explore`)

- **File structure**: how is the project organized? Is it modular or monolithic?
- **Largest files**: identify files over 400 lines — are they god files or reasonably large?
- **Language & type safety**: TypeScript vs JavaScript? Type annotations in Python? Strong typing in general?
- **Linting**: is a linter configured (eslint, ruff, golangci-lint)? Is it enforced in CI?
- **Dependencies**: read package manifest — how many dependencies? Are they well-known/maintained or obscure?
- **Code smells**: scan the main source files for:
  - Duplicated patterns (copy-paste code)
  - Deep nesting
  - Overly long functions
  - Broad exception catches
  - Hardcoded values
  - No-op or dead code
- **Documentation**: README quality, inline docs, API documentation
- **Security basics**: secrets in code? Input validation? Dependency audit results?

### Subagent 4: API & Design (`subagent_type: Explore`)

- **Public API surface**: what does the user actually interact with? Is it clean and well-defined?
- **Error handling**: how does the project handle and communicate errors?
- **Configuration**: how is the project configured? Environment variables, config files, CLI flags?
- **Extensibility**: is there a plugin system, hooks, or clean extension points?
- **Breaking change history**: scan changelogs or release notes for breaking changes — how often do they happen?

## Phase 2: Synthesize

Combine subagent findings into a structured assessment. Don't just dump data — interpret it.

### Health Signals Matrix

Evaluate each dimension on a simple scale: **Strong / Adequate / Weak / Missing**

| Dimension | Assessment | Evidence |
|-----------|-----------|----------|
| Maintenance | Active / Sporadic / Dormant / Abandoned | commit frequency, last activity, open issues response time |
| Test Coverage | Comprehensive / Partial / Minimal / None | test file count, coverage config, CI enforcement |
| Code Quality | Clean / Acceptable / Rough / Poor | file sizes, structure, linting, type safety |
| Documentation | Thorough / Adequate / Sparse / None | README depth, API docs, examples |
| Community | Growing / Stable / Stagnant / Solo | contributors, stars, forks, issue/PR activity |
| Bus Factor | Healthy (3+) / Risky (2) / Critical (1) | commit distribution across contributors |
| Security | Proactive / Basic / Reactive / None | audit in CI, dependency scanning, input validation |

### Red Flags

Explicitly call out any of these if present:
- Single maintainer with no succession plan
- Large proportion of AI-generated commits (Jules, Copilot agents)
- No tests at all, or tests that only check method existence
- Archived or abandoned with no fork continuing development
- License incompatible with user's needs
- Known security vulnerabilities in dependencies
- Massive monolithic files with no separation of concerns
- Dormant for 6+ months with open issues/PRs unanswered

### Green Flags

Also call out positives:
- Semantic versioning with regular releases
- CI with test matrix across multiple runtime versions
- High test coverage with meaningful assertions
- Active issue triage and PR review
- Clean modular architecture
- TypeScript/type annotations throughout
- Security scanning in CI
- Good documentation with examples

## Phase 3: Present the Verdict

Present findings conversationally, then use `AskUserQuestion` to determine next steps.

### Report Structure

```
## Repository Evaluation: <owner/repo>

### Overview
<1-2 sentences: what it is, what it does>

### Project Vitals
| Metric | Value |
|--------|-------|
| Created | <date> (<age>) |
| Last activity | <date> |
| Version | <latest tag/release> |
| Stars / Forks | <count> |
| Contributors | <count> (bus factor: <N>) |
| License | <license> |
| Language | <primary language> |

### Health Assessment
<The health signals matrix from Phase 2>

### Red Flags
<Bulleted list, or "None identified">

### Green Flags
<Bulleted list>

### Code Quality Notes
<2-4 specific observations about the code — not generic, grounded in what you read>

### Test Coverage
<Specific findings: what's tested, what isn't, how thorough>

### Verdict
<Clear recommendation: one of>
- **Adopt with confidence** — well-maintained, well-tested, low risk
- **Adopt with caution** — usable but has notable gaps; document what you're accepting
- **Use for reference only** — interesting ideas but not production-ready as a dependency
- **Avoid** — significant quality, maintenance, or security concerns
- **Build your own** — the problem is simple enough that wrapping the underlying API/library directly is safer than this abstraction

<2-3 sentences explaining the recommendation>
```

### Ask what to do

```
AskUserQuestion:
  question: "Based on this evaluation, what would you like to do?"
  header: "Next step"
  multiSelect: false
  options:
    - label: "Adopt it"
      description: "I'll add it as a dependency — thanks for the review"
    - label: "Dig deeper"
      description: "I want to look at specific areas more closely before deciding"
    - label: "Look for alternatives"
      description: "Search for other libraries/tools that solve the same problem"
    - label: "Skip it"
      description: "Not worth it — I'll find another approach"
```

If the user wants to **dig deeper**, ask what specifically concerns them and focus investigation there.

If the user wants to **look for alternatives**, use `WebSearch` to find competing projects, then offer to evaluate the top 2-3 candidates with the same process (abbreviated — skip the full subagent sweep, focus on the health signals matrix for comparison).

## Cleanup

After the evaluation is complete, remove the cloned repo directory:

```bash
rm -rf "<dir>"
```

Note: `rm -rf` is intentionally not pre-approved — the user will see a permission prompt for this cleanup step.

## Principles

1. **Evidence over opinion** — every assessment should cite specific files, line counts, commit data, or test results. No "this looks fine" without backing it up.
2. **Context matters** — a personal utility with 20 stars and one maintainer might be perfectly fine for light scripting. A payment processing library with the same profile is a hard no. Calibrate the verdict to the user's likely use case.
3. **Red flags are not disqualifying on their own** — a single-maintainer project with excellent tests and clean code can still be a good choice. Multiple red flags compound.
4. **Be honest about alternatives** — if wrapping the underlying API directly is simpler than using this library, say so. Don't recommend a dependency just because it exists.
5. **Time is a signal** — a project that's been stable for 3 years with infrequent commits is different from one that was abandoned after 3 months. Distinguish between "mature and stable" and "dead."
6. **AI-generated code is a signal, not a verdict** — flag it because it often correlates with less thoughtful design and lower test quality, but judge the output on its own merits.

## What This Skill Does NOT Do

- **Audit your own codebase** — use `/mine.audit` for that
- **Research feasibility of adopting it** — use `/mine.research` if you need to evaluate how this would integrate into your specific project
- **Security audit** — this checks for basic security hygiene (audit in CI, no secrets in code) but won't do a thorough vulnerability assessment
- **Performance benchmarking** — can flag likely performance concerns from code reading but won't run benchmarks
- **License compliance analysis** — flags the license but doesn't evaluate compatibility with your project's license
