<!-- caller-protocol-version: 3 -->

# Caller Protocol

Defines how callers invoke challenge, what they receive, and how they handle
each finding status. Applies to mine.define and mine.gap-close.

## Invocation

```
challenge --findings-out=<path> --target-type=<type> --mode=<mode> <target>
```

| Flag | Values | Meaning |
|---|---|---|
| `--findings-out` | absolute path | Where challenge writes the findings file |
| `--target-type` | `design-doc` \| `code` \| `skill` | Guides critic selection |
| `--mode` | `passthrough` | Present summary only; skip inline resolution. Omit for normal use — mode is derived from `--findings-out` presence |

Challenge returns when all findings are resolved (or overflow). The findings
file at `--findings-out` is the only output contract.

## What Callers Receive

A findings file at `<--findings-out>` containing `## Finding N:` sections per
`findings-protocol.md`. Each finding has `status` and `overflow` fields
populated by challenge before it returns.

Callers read the findings file after challenge returns. They do not interact
with challenge's inline resolution flow.

## Handling Findings by Status

### `status: applied`

The finding was resolved during challenge execution (auto-apply or user
chose an option). For doc-edit callers (mine.define): if `design-level: Yes`,
verify the edit was applied correctly to the target document. If the edit is
missing or incorrect, re-apply it via the Edit tool using the finding's
`better-approach` or chosen option.

### `status: pending`

Challenge resolves all in-scope findings before returning. A `pending` finding
after challenge returns means challenge exited early (token exhaustion, crash,
or user abort). Do not silently ignore it — surface it to the user for manual
resolution.

### `status: overflow`

The finding exceeded the finding cap and was not presented. Callers may log
these for reference but should not act on them. Do not re-present overflow
findings unless the user explicitly asks to see them.

### `status: skipped`

The user explicitly skipped this finding during resolution. No caller action
needed. Record skipped findings in the session summary.

## Design-Level Field

`**Design-level:** Yes | No` — set by the synthesis subagent on each finding.

- `Yes`: the finding targets the design document itself (a missing requirement,
  an untestable AC, a structural inconsistency). Doc-edit callers (mine.define)
  should verify the finding's resolution was applied to the design doc.
- `No`: the finding targets implementation concerns that should be addressed
  during build, not in the design doc. Callers should flag these for
  implementers (e.g., add to a task list or file an issue) rather than editing
  the design doc.

