---
name: mine.address-pr-comments
description: Fetch unresolved GitHub PR review comments and systematically address them. Uses plan mode for structured resolution, AskUserQuestion for decisions, and auto-resolves threads on GitHub with explanatory comments.
user-invokable: true
---

# Address PR Review Comments

Systematically fetch, filter, analyze, and address unresolved GitHub PR review comments. Uses plan mode to present a structured resolution approach, AskUserQuestion for user decisions, and automatically resolves threads on GitHub with reply comments explaining each resolution.

## When to Activate

- User asks to address, fix, or review PR comments
- User asks to check for unresolved PR feedback
- User mentions Copilot comments on a PR
- User says "address PR comments" or similar phrasing

## Usage

```
/address-pr-comments [PR#]
```

If no PR number is given, auto-detect from the current branch.

## Phase 1: Fetch PR Context

### Auto-detect or accept PR number

If a PR number argument was provided, use it. Otherwise, detect from the current branch:

```bash
gh pr view --json number,title,url,baseRefName,headRefName
```

If this fails, tell the user no PR is associated with the current branch and ask for a PR number.

### Error handling

- If `gh` is not authenticated: prompt the user to run `gh auth login`
- If the GraphQL query fails with a permissions error: the token may lack the `repo` scope — suggest `gh auth refresh -s repo`
- If rate-limited: inform the user and suggest waiting

### Fetch review threads via GraphQL

Use `gh api graphql` to fetch all review threads with resolution status, comment bodies, file paths, line numbers, and author info. This is the only way to get `isResolved` — the REST API does not expose it.

```bash
gh api graphql -f query='
query($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      title
      url
      baseRefName
      headRefName
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          startLine
          diffSide
          comments(first: 50) {
            nodes {
              id
              body
              author {
                login
              }
              createdAt
              updatedAt
            }
          }
        }
      }
    }
  }
}' -F owner='{owner}' -F repo='{repo}' -F pr={PR_NUMBER}
```

The `{owner}` and `{repo}` placeholders are auto-resolved by `gh` from the current repository context. Only `{PR_NUMBER}` needs to be substituted with the actual PR number.

**Pagination**: If the PR has more than 100 review threads, the response will include `pageInfo.hasNextPage: true`. In that case, add `pageInfo { hasNextPage endCursor }` to the query and fetch additional pages using the `after` cursor. For most PRs this is not needed, but check and warn the user if threads were truncated.

### Fetch general PR conversation comments

For non-inline feedback (general PR comments not attached to specific lines):

```bash
gh pr view {PR_NUMBER} --json comments --jq '.comments[] | {author: .author.login, body: .body, createdAt: .createdAt}'
```

## Phase 2: Filter, Deduplicate & Categorize

### Exclude resolved threads

Remove threads where:
- `isResolved: true` — already marked resolved on GitHub

### Triage outdated threads

Threads where `isOutdated: true` need individual assessment — the diff hunk changed but the reviewer's concern may still be valid. For each outdated thread:
1. Read the comment body to understand the reviewer's concern
2. Read the current code at that location
3. If the concern was clearly addressed by the code change that made it outdated, categorize as **already addressed**
4. If unclear whether the concern was addressed, include it in a **needs manual review** category in the summary

Do NOT blanket-exclude outdated threads.

### Filter general PR comments

General (non-inline) conversation comments have no resolution status. For each:
1. Determine if it contains actionable feedback (vs. discussion, approval, acknowledgment)
2. Check if the feedback has already been addressed in subsequent commits
3. Include only actionable, unaddressed comments in the summary

### Group by file path

Organize remaining unresolved comments by their `path` field for efficient processing.

### Check if changes were already made

For each remaining comment:
1. Read the current code at the referenced file and line number
2. Compare against what the reviewer requested
3. If the requested change is already present in the current code, categorize as **already addressed** (this catches GitHub Copilot's repeat-comment problem and comments addressed in subsequent commits)

Do NOT resolve any threads yet — all resolutions happen in Phase 4 after user approval.

### Present summary using AskUserQuestion

After filtering and categorizing, use `AskUserQuestion` to confirm which comments to address:

Present the categorized summary as the question context, then ask:

```
AskUserQuestion:
  question: "I found N genuinely unresolved comments across M files, plus K comments that appear already addressed. How would you like to proceed?"
  header: "PR Comments"
  options:
    - label: "Address all"
      description: "Analyze and fix all N unresolved comments"
    - label: "Let me pick"
      description: "I'll specify which comments to address or skip"
    - label: "Show details first"
      description: "Show me the full list before deciding"
```

If the user picks "Let me pick", use a follow-up `AskUserQuestion` with `multiSelect: true` listing each comment so they can select which ones to address.

If the user picks "Show details first", display the full categorized table, then ask again with "Address all" / "Let me pick".

## Phase 3: Enter Plan Mode — Analyze & Plan Solutions

**Enter plan mode** using the `EnterPlanMode` tool. This structures the analysis and gives the user a clear plan to approve before any code changes.

### In plan mode:

For each unresolved comment (or group of related comments on the same file), launch an **Explore** subagent to:

1. Read the relevant code and surrounding context
2. Understand the reviewer's intent — what specific change are they requesting?
3. Determine the action type:
   - **Code change needed**: Identify the root cause and propose the best fix (not just a bandaid)
   - **Response needed**: The code is correct but the reviewer needs an explanation
   - **Not relevant / False positive**: The comment doesn't apply (e.g., Copilot misunderstanding)
4. If code change: describe the specific edit needed

**Run subagents in parallel** for comments on independent files. Group comments on the same file into a single subagent.

### Write the plan

Write a structured plan covering **every** comment with the proposed action — including already-addressed and not-relevant items. The user must approve all resolutions before anything is marked resolved on GitHub.

```
## Plan: Address PR Review Comments

### Code Changes
1. **src/foo.py:42** — Replace `print()` with `logging.info()` (reviewer: @reviewer)
   Root cause: print statements bypass log configuration and won't appear in production logs.
   Action: Apply fix, reply, and resolve thread.

2. **src/bar.py:17** — Add type annotation `-> list[str]` to `get_names()` (reviewer: @copilot)
   Root cause: Missing return type annotation.
   Action: Apply fix, reply, and resolve thread.

### Already Addressed — Reply & Resolve
3. **src/old.py:10** — @copilot: "Add docstring" (already present in current code)
   Reply: "This was already addressed in a previous commit — the current code includes this change."
   Action: Post reply and resolve thread.

4. **src/utils.py:25** — @copilot: "Add type annotation" (outdated, code was refactored)
   Reply: "The code at this location was refactored and this concern no longer applies."
   Action: Post reply and resolve thread.

### Reply & Resolve (no code change needed)
5. **src/baz.py:5** — @copilot suggested removing unused import, but `typing.TYPE_CHECKING` is used for circular import avoidance.
   Reply: "This import is guarded by `TYPE_CHECKING` and is needed to avoid circular imports at runtime."
   Action: Post reply and resolve thread.

### Not Relevant — Reply & Resolve
6. **src/qux.py:20** — @copilot: "Consider using dataclass" — already using a NamedTuple which is appropriate here.
   Reply: "NamedTuple is the appropriate choice here for immutability and unpacking support."
   Action: Post reply and resolve thread.
```

Use `ExitPlanMode` to present the plan for user approval.

### Handle plan feedback with AskUserQuestion

If the user has concerns about specific items in the plan, use `AskUserQuestion` to clarify:

```
AskUserQuestion:
  question: "For the TYPE_CHECKING import comment on src/baz.py:5, would you prefer to:"
  header: "Resolution"
  options:
    - label: "Reply & resolve"
      description: "Post explanation and mark as resolved"
    - label: "Make the change"
      description: "Remove the import as the reviewer suggested"
    - label: "Skip"
      description: "Leave this comment unresolved for now"
```

## Phase 4: Apply Changes & Resolve Threads

Once the plan is approved, execute it. For each item, apply the change AND resolve the thread on GitHub.

### For already-addressed items

These were identified during triage but held until now for user approval:
1. **Post a reply comment** explaining how/when the change was already made
2. **Resolve the thread** on GitHub

### For code changes

For each approved code change:
1. Read the target file
2. Apply the edit using the Edit tool
3. Verify the edit was applied correctly
4. **Post a reply comment** on the thread explaining what was changed
5. **Resolve the thread** on GitHub

### For "reply & resolve" items (no code change)

1. **Post a reply comment** explaining why no code change is needed
2. **Resolve the thread** on GitHub

### For "not relevant" items

1. **Post a reply comment** explaining why the comment is not applicable
2. **Resolve the thread** on GitHub

### Run code review

After all edits are complete, run the **code-reviewer** agent on all modified files to catch any issues introduced by the changes.

## Helper Scripts

**IMPORTANT**: Use these helper scripts instead of inline `python3 -c` commands. They are in PATH (`bin/` in this repo, symlinked by `install.sh`) and avoid unnecessary permission prompts.

### Fetch unresolved threads

```bash
gh-pr-threads [pr-number]
```

Auto-detects PR from current branch if no number given. Outputs: PR title, URL, thread count, and a summary of each unresolved thread with path, line, thread ID, comment database ID, author, and body preview.

### Post a reply comment on a thread

```bash
gh-pr-reply <pr-number> <comment-id> <body>
```

Where `comment-id` is the `databaseId` of the comment being replied to (from `gh-pr-threads` output or the GraphQL query). Auto-detects owner/repo from git remote. Prints `Reply posted: <id>` on success.

### Resolve review threads

```bash
gh-pr-resolve-thread <thread-id> [thread-id...]
```

Resolves one or more threads by their GraphQL node IDs (`PRRT_...`). Supports bulk resolve — pass all thread IDs as arguments:

```bash
gh-pr-resolve-thread PRRT_abc123 PRRT_def456 PRRT_ghi789
```

Prints `Resolved <thread-id>: true` for each.

### Combined reply + resolve pattern

For each thread, reply first, then resolve:

```bash
gh-pr-reply 262 2818193159 "Fixed — replaced print() with logging.info() as suggested."
gh-pr-resolve-thread PRRT_kwDOPoHyzs5vG-cc
```

### Getting comment IDs

The `databaseId` field is included in the `gh-pr-threads` output. If you need to fetch comment IDs separately:

```bash
gh api repos/{owner}/{repo}/pulls/{PR_NUMBER}/comments --jq '.[] | {id, path, body}'
```

Or add `databaseId` to the GraphQL comments query in Phase 1.

### Reply comment guidelines

Reply comments should be concise and explain the resolution:

- **Code change made**: "Fixed — replaced `print()` with `logging.info()` as suggested."
- **Already addressed**: "This was already addressed in a previous commit — the current code includes this change."
- **Not relevant**: "This NamedTuple is intentional — it provides immutability and tuple unpacking which dataclass doesn't offer here."
- **Outdated and addressed**: "The code at this location was refactored and this concern no longer applies."
- **Disagreement**: "Keeping the current approach because [reason]. Happy to discuss further."

Keep replies professional and direct. Don't be dismissive of reviewer feedback even when declining to make a change.

## Phase 5: Summary

Present a final summary:

```
## Summary

### Resolved with code changes (N threads)
- src/foo.py:42 — Replaced print() with logging.info() [replied & resolved]
- src/bar.py:17 — Added return type annotation [replied & resolved]

### Resolved with reply (M threads)
- src/baz.py:5 — Explained TYPE_CHECKING import usage [replied & resolved]
- src/qux.py:20 — Explained NamedTuple choice [replied & resolved]

### Auto-resolved during triage (K threads)
- src/old.py:10 — Already addressed in current code [replied & resolved]

### Left unresolved (J threads)
- src/unclear.py:30 — Needs manual review (outdated, concern may still apply)
- User declined: W

### Next steps
- Review the code changes and commit when satisfied
- Check any threads left for manual review
```

---

**Remember**: Always get user approval via plan mode before applying code changes. Use AskUserQuestion for decisions throughout. Resolve threads on GitHub as you go — don't leave resolution as a manual step.
