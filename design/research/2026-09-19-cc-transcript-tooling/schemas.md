# Claude Code JSONL Transcript Entry Schemas

Source: Claude Code v2.1.276 (`BUILD_TIME:"2026-09-18T00:40:43Z"`, `GIT_SHA:bc0a4292e0472d227ceecb07d892ab1a777a4926`),
extracted from `~/.cache/claude-cli-src/claude/root/*.js` (unpacked Bun bundle, 1873 chunk files).

## Critical finding: most entry types have NO Zod schema

`ENTRY_APPEND_POLICY` (`wQr` in `chunk-bp8ekm6v.js`) lists all 35 entry types, but a
full-bundle scan (every `*.js` chunk, ~35 MB) for `type:<ident>("<type-name>")` — the
`z.literal("...")`-discriminated-object pattern used by `cost-state` — found a real Zod
object schema for only **9 of the 35** types:

| Type | Defining chunk | Local literal alias |
|---|---|---|
| `user` | `chunk-y68kda6q.js` | `R` |
| `assistant` | `chunk-y68kda6q.js` | `R` |
| `attachment` | `chunk-y68kda6q.js` | `R` |
| `system` (32+ subtypes) | `chunk-y68kda6q.js` | `R` |
| `continued-in` | `chunk-7wy3qk0y.js` | `R` |
| `artifact-comment-monitor` | `chunk-dyrd95cz.js` | `R` |
| `artifact-autoreact-ledger` | `chunk-q252am71.js` | `R` |
| `cost-state` | `chunk-bp8ekm6v.js` | `Sd` |
| `frame-link` | `chunk-bp8ekm6v.js` | `Sd` |

The remaining **26 types** (`progress`, `summary`, `custom-title`, `ended-by-model`,
`last-prompt`, `tag`, `relocated`, `agent-name`, `agent-color`, `agent-setting`, `pr-link`,
`bridge-session`, `history-suppression`, `file-history-snapshot`, `file-history-delta`,
`attribution-snapshot`, `mode`, `permission-mode`, `isolation-latch`, `memory-mode`,
`atis-latch`, `worktree-state`, `queue-operation`, `content-replacement`,
`fork-context-ref`, `observer-ref`) are constructed as **plain JS object literals** —
`{type:"worktree-state", worktreeSession:...}` — with no corresponding
`z.object({type:z.literal(...), ...})` anywhere in the bundle. Their shape is
TypeScript-only (erased at compile time; no runtime trace survives in the compiled JS).
For these, the tables below are **reverse-engineered from construction call-sites and
consumption sites** in `chunk-bp8ekm6v.js` (the transcript writer/reader module), not
extracted from a schema. Confidence and evidence are noted per field.

This means a from-scratch Python parser for these 26 types cannot be schema-validated
against Claude's own source — only against the field shapes observed here, which should
be treated as "best known shape," not "guaranteed contract."

## Envelope fields added when a message is persisted to the JSONL transcript

`user`/`assistant`/`attachment` schemas in `chunk-y68kda6q.js` define only the **payload**
(the "engine SDK message" shape). When one of those is written to the on-disk JSONL
transcript, `toTranscriptEntries` (`Y0r` in `chunk-bp8ekm6v.js`) spreads it into an
envelope:

```js
function Y0r(e,n){
  let r=null;
  return wDe(e.slice()).map((s)=>{
    let g={...s, cwd:ne(), userType:pln(), sessionId:n, timestamp:s.timestamp,
           version:Kcr, parentUuid:r, isSidechain:!1};
    if(Hoe(s)) r=s.uuid;
    return g;
  });
}
```

A second construction site (writer, same chunk) adds further envelope fields not present
in `Y0r`'s simplified path:

```js
let Ye={parentUuid:Ue?null:ze, logicalParentUuid:Ue?we:void 0, isSidechain:n, teamName:g?.t...}
```

So the full observed on-disk envelope for `user`/`assistant` rows, layered on top of the
payload schema fields (`type`, `message`, `uuid`, etc. — see below), is:

| Envelope field | Type | Optional | Notes |
|---|---|---|---|
| parentUuid | string \| null | no | `null` on the first row of a chain |
| logicalParentUuid | string | yes | present on rewind/fork boundaries |
| isSidechain | boolean | no | true for subagent/sidechain transcript rows |
| userType | string | no | `pln()` → hardcoded `"external"` (see `chunk-bp8ekm6v.js`) |
| cwd | string | no | `ne()` — process cwd at write time |
| sessionId | string | no | |
| version | string | no | `Kcr.VERSION`, the CLI version string |
| gitBranch | string | yes | seen in restore/reconstruction code paths |
| teamName | string | yes | |
| timestamp | string (ISO) | no | |

`system` rows carry their own `session_id`/`uuid` inside the payload schema itself (see
below) rather than through this envelope function.

---

## Entry Type: user

**Append policy:** dedup-transcript
**Zod schema:** confirmed (`hz`/`bl` in `chunk-y68kda6q.js`)

`hz()` defines the base payload; `bl()` (`hz().extend({...})`) is the schema actually used
for a full transcript row (adds `uuid`, `session_id`, and subagent fields). `Zse()` is a
third variant for SDK-replay user messages.

**Fields (bl = hz + extension):**

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("user") | no | discriminator |
| message | object (see `Yse` message content, below) | no | |
| parent_tool_use_id | string \| null | no | |
| isSynthetic | boolean | yes | |
| tool_use_result | unknown | yes | structured per-tool output; shape is tool-specific |
| priority | enum("now","next","later") | yes | |
| origin | `$f()` (origin enum, not traced) | yes | |
| client_platform | string | yes | `@internal` |
| inbound_origin | string | yes | `@internal` |
| historical | boolean | yes | `@internal` |
| shouldQuery | boolean | yes | |
| timestamp | string (ISO) | yes | |
| is_meta | literal(true) | yes | `@internal` |
| seeded_summon | literal(true) | yes | `@internal`, desktop-only |
| client_composed | literal(true) | yes | `@internal` |
| is_visible_in_transcript_only | literal(true) | yes | `@internal` |
| is_virtual | literal(true) | yes | `@internal` |
| is_compact_summary | literal(true) | yes | `@internal` |
| summarize_metadata | object `{messages_summarized:number, user_context?:string, direction?:enum("from","up_to")}` | yes | `@internal` |
| mcp_meta | object `{_meta?, structured_content?, resource_links?}` | yes | `@internal`, never sent to model |
| tool_result_meta | array of `{id, non_execution_kind?, user_feedback?, remedy?}` | yes | `@internal` |
| source_tool_use_id | string | yes | `@internal` |
| source_tool_assistant_uuid | string | yes | `@internal` |
| image_paste_ids | array of int | yes | `@internal` |
| plan_content | string | yes | `@internal` |
| permission_mode | `Vt()` (permission mode enum) | yes | `@internal` |
| interrupted_message_id | string | yes | `@internal` |
| **— fields added by `bl().extend()` —** | | | |
| uuid | string | yes (but always present on a real transcript row) | |
| session_id | string | yes (same) | |
| subagent_type | string | yes | |
| task_description | string | yes | |
| file_attachments | array of unknown | yes | `@internal` |

## Entry Type: assistant

**Append policy:** dedup-transcript
**Zod schema:** confirmed (`Yf` in `chunk-y68kda6q.js`)

Very large schema (~130 fields worth of description); full field list:

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("assistant") | no | |
| message | object (see `qse` message content, below) | no | |
| parent_tool_use_id | string \| null | no | |
| error | `Vf()` (error schema, not traced) | yes | |
| uuid | string | no | |
| historical | boolean | yes | `@internal` |
| session_id | string | no | |
| request_id | string | yes | |
| user_message_uuid | string | yes | |
| user_message_uuids | array of string (≤64) | yes | |
| resume_reason | string | yes | |
| resumed_from_incomplete_thinking | literal(true) | yes | |
| supersedes | array of string uuid | yes | |
| aborted | literal(true) | yes | |
| subagent_type | string | yes | |
| task_description | string | yes | |
| tool_use_meta | array of `{id, display_name, server_display_name?, icon_url?}` | yes | `@internal` |
| narration_block_indexes | array of nonneg int | yes | `@internal` |
| timestamp | string (ISO) | yes | |
| is_meta | literal(true) | yes | `@internal` |
| context_usage | object (`/context` report twin) | yes | |
| usage_report | object (`/usage` report twin) | yes | |
| local_command_source | string | yes | `@internal` |
| local_command_run | object `{command, args}` | yes | `@internal` |
| is_virtual | literal(true) | yes | `@internal` |
| batch_tool_uses | array of `{id, name}` | yes | `@internal` |
| wire_tool_inputs | record(string, unknown) | yes | `@internal` |
| wire_ingest_context | record(string, unknown) | yes | `@internal` |
| is_api_error_message | boolean | yes | `@internal` |
| api_error_status | int | yes | `@internal` |
| api_error | enum (many values, see source) | yes | `@internal` |
| api_error_params | object `{effort?, provider?, remedy?}` | yes | `@internal` |
| api_error_code | string | yes | `@internal` |
| error_details | string | yes | `@internal` |
| advisor_model | string | yes | `@internal` |
| attribution_agent | string | yes | `@internal` |
| attribution_skill | string | yes | `@internal` |
| attribution_plugin | string | yes | `@internal` |
| attribution_mcp_server | string | yes | `@internal` |
| attribution_mcp_tool | string | yes | `@internal` |

## Entry Type: attachment

**Append policy:** dedup-transcript
**Zod schema:** confirmed (`eIe` in `chunk-y68kda6q.js`)

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("attachment") | no | |
| attachment | unknown (`ae()`) | no | internal Attachment discriminated union — "wire shape pending a dedicated schema" per the source's own `.describe()` |
| timestamp | string | no | |
| uuid | string | no | |
| session_id | string | no | |

## Entry Type: system

**Append policy:** dedup-transcript
**Zod schema:** confirmed, one schema per subtype, all discriminated on `type:literal("system")` + `subtype:literal(<name>)`, defined in `chunk-y68kda6q.js`.

32+ subtypes were found (the bundle-wide count of `type:R("system")` occurrences was 51,
some of which are duplicate matches inside nested `.describe()` text/other unions, not all
distinct subtypes). Confirmed subtypes and their local variable:

| Subtype | Local var | Notes |
|---|---|---|
| init | `uae` | boot frame; `agents?`, `apiKey...`, etc. |
| compact_boundary | `fae` | `compact_metadata` |
| status | `_ae` | `status`, `permissionMode` |
| code_change_published | `wle` | PR/MR publish event; `provider`, `url`, `repo`, `identifier`, `action?`, `branch?` |
| vcs_state_changed | `kle` | `kind` (commit/push/merge/rebase), `cwd`, `branch?` |
| dev_intent | `Ole` | `kind` (ios_app/android_app/...), `trigger?` |
| turn_preempted | `Ple` | `reason`, `preempted_by_uuid`, `preempted_message_uuids` |
| cloud_session_delta | `Mle` | `seq`, `changed`, `cloud_session` |
| api_retry | `hae` | |
| control_request_progress | `Eae` | |
| model_refusal_fallback | `Sae` | |
| model_refusal_no_fallback | `bae` | |
| local_command_output | `Tae` | |
| hook_started | `Aae` | |
| hook_progress | `vae` | |
| hook_response | `Rae` | |
| plugin_install | `Cae` | |
| task_notification | `xae` | |
| task_started | `Iae` | |
| task_updated | `lle` | |
| task_progress | `gle` | |
| background_tasks_changed | `cle` | |
| thinking_tokens | `hle` | |
| session_state_changed | `ule` | |
| worker_shutting_down | `ple` | |
| commands_changed | `_le` | |
| notification | `mle` | |
| files_persisted | `Pae` | |
| memory_recall | `yle` | |
| elicitation_complete | `Tle` | |
| permission_denied | `Ale` | |
| mirror_error | `gae` | |
| informational | `mae` | |
| feedback_draft_queued | `dle` | |
| turn_handoff_available | `fle` | |

Field-level detail was extracted in full for `init`, `compact_boundary`, `status`,
`code_change_published`, `vcs_state_changed`, `dev_intent`, `turn_preempted`, and
`cloud_session_delta` (shown above in the "Notes" column and in the `chunk-y68kda6q.js`
source directly). The remaining ~24 subtypes were enumerated by name/subtype only —
extracting each one's full field list was out of scope for this pass; re-run the same
`extract_stmt`-style brace-matcher against each local variable name in `chunk-y68kda6q.js`
to pull them.

## Entry Type: cost-state

**Append policy:** always
**Zod schema:** confirmed (`Sbe` in `chunk-bp8ekm6v.js`)

```js
var Sbe=p(()=>{
  let e=nn().nonnegative().finite();
  return et({
    type:Sd("cost-state"),
    sessionId:ce(),
    totalCostUSD:e,
    totalAPIDuration:e,
    totalAPIDurationWithoutRetries:e,
    totalToolDuration:e,
    totalLinesAdded:e,
    totalLinesRemoved:e,
    totalDuration:e,
    startTime:e,
    modelUsage:Lm(ce().regex(/^[^\p{Cc}\p{Cf}]+$/u), et({
      inputTokens:e, outputTokens:e, thinkingTokens:e.optional(),
      cacheReadInputTokens:e, cacheCreationInputTokens:e,
      webSearchRequests:e, costUSD:e
    })),
    hasUnknownModelCost:ao().optional()
  })
})
```

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("cost-state") | no | |
| sessionId | string | no | |
| totalCostUSD | nonneg finite number | no | |
| totalAPIDuration | nonneg finite number | no | |
| totalAPIDurationWithoutRetries | nonneg finite number | no | |
| totalToolDuration | nonneg finite number | no | |
| totalLinesAdded | nonneg finite number | no | |
| totalLinesRemoved | nonneg finite number | no | |
| totalDuration | nonneg finite number | no | |
| startTime | nonneg finite number | no | |
| modelUsage | record(model-name-string → ModelUsage) | no | see nested type below |
| hasUnknownModelCost | boolean | yes | |

### Nested Type: ModelUsage (value type of `modelUsage`)

| Field | Type | Optional |
|---|---|---|
| inputTokens | nonneg finite number | no |
| outputTokens | nonneg finite number | no |
| thinkingTokens | nonneg finite number | yes |
| cacheReadInputTokens | nonneg finite number | no |
| cacheCreationInputTokens | nonneg finite number | no |
| webSearchRequests | nonneg finite number | no |
| costUSD | nonneg finite number | no |

## Entry Type: frame-link

**Append policy:** always
**Zod schema:** confirmed (`x$s` in `chunk-bp8ekm6v.js`)

```js
var x$s=p(()=>et({
  type:Sd("frame-link"),
  frameUrl:ce().optional().catch(void 0),
  artifactCount:nn().int().positive().optional().catch(void 0)
}));
```

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("frame-link") | no | |
| frameUrl | string | yes | `.catch(undefined)` — malformed values silently drop to undefined rather than failing validation |
| artifactCount | positive int | yes | same `.catch` behavior |

## Entry Type: continued-in

**Append policy:** always
**Zod schema:** confirmed (`chunk-7wy3qk0y.js`)

```js
var O=p(()=>lt({type:R("continued-in"),continuedInSessionId:o()}))
```

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("continued-in") | no | |
| continuedInSessionId | string | no | |

## Entry Type: artifact-comment-monitor

**Append policy:** always
**Zod schema:** confirmed (`chunk-dyrd95cz.js`)

```js
n=u({
  type:R("artifact-comment-monitor"),
  v:R(1),
  sessionId:o(),
  artifacts:fe(o(),ae()),
  crossLineMerged:R(!0).optional().catch(void 0),
  tailTorn:R(!0).optional().catch(void 0)
})
```

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("artifact-comment-monitor") | no | |
| v | literal(1) | no | schema version tag |
| sessionId | string | no | |
| artifacts | record(string, unknown) | no | |
| crossLineMerged | literal(true) | yes | `.catch(undefined)` |
| tailTorn | literal(true) | yes | `.catch(undefined)` |

## Entry Type: artifact-autoreact-ledger

**Append policy:** always
**Zod schema:** confirmed (`chunk-q252am71.js`)

```js
s=Je({
  type:R("artifact-autoreact-ledger"),
  v:R(1),
  sessionId:o(),
  accountUuid:o().nullable(),
  artifacts:fe(o(),ae())
})
```
The record value type (`n`, used inside `artifacts`) is a "thread" object:
```js
i=Je({
  savedAt:r, stampHighWater:e.nullable(), everBaselined:H(), everHadThreads:H(),
  turnTimestamps:C(r).max(xo), threads:C(n).max(Po).optional(), interrupted:R(!0).optional()
})
```

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("artifact-autoreact-ledger") | no | |
| v | literal(1) | no | schema version tag |
| sessionId | string | no | |
| accountUuid | string \| null | no | |
| artifacts | record(string → ledger-entry, shape `i` above) | no | see nested |

### Nested Type: ledger-entry (`i`, value type of `artifacts`)

| Field | Type | Optional |
|---|---|---|
| savedAt | number | no |
| stampHighWater | number \| null | no |
| everBaselined | boolean | no |
| everHadThreads | boolean | no |
| turnTimestamps | array of number (max `xo`) | no |
| threads | array (max `Po`) | yes |
| interrupted | literal(true) | yes |

---

## The remaining 26 types (no Zod schema — reverse-engineered from construction/consumption sites)

All in `chunk-bp8ekm6v.js` unless noted. Confidence: **High** = literal object-construction
site found and read directly. **Medium** = field inferred from a consuming/destructuring
site, not a construction site. **Low** = single ambiguous reference, type unconfirmed.

### Entry Type: progress

**Append policy:** dedup-transcript
**Confidence:** High (two distinct construction shapes observed — this type is polymorphic; there is no single fixed schema)

```js
{type:"progress", toolUseID:`${n}-heartbeat-${y}`, data:{type:"tool_heartbeat", toolName, elapsedTimeSeconds}}
{type:"progress", data:{type:"hook_progress", hookEvent, hookName, command, promptText?, statusMessage?}, parentToolUseID, toolUseID, timestamp, uuid}
```

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("progress") | no | |
| toolUseID | string | no (seen in both variants) | |
| parentToolUseID | string | yes | seen on hook_progress variant |
| timestamp | string (ISO) | yes | |
| uuid | string | yes | |
| data | object, discriminated by nested `type` (`tool_heartbeat`, `hook_progress`, and likely other ephemeral kinds — see `yFs` set: `bash_progress`, `powershell_progress`, `mcp_progress`, `repl_tool_call`, `tool_heartbeat`, `agent_api_retry`, `artifact_publish_retry`) | no | fully polymorphic; is never persisted long-term (dedup-transcript = ephemeral) |

### Entry Type: summary

**Append policy:** always
**Confidence:** High

```js
r.set(er.leafUuid, er.summary)   // consumption site
```

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("summary") | no | |
| leafUuid | string | no | uuid of the transcript leaf this summary describes |
| summary | string | no | the summary text |

### Entry Type: custom-title

**Append policy:** always
**Confidence:** High

```js
{type:"custom-title", customTitle:this.currentSessionTitle, sessionId:h}
```

| Field | Type | Optional |
|---|---|---|
| type | literal("custom-title") | no |
| customTitle | string | no |
| sessionId | string | no |

### Entry Type: ended-by-model

**Append policy:** always
**Confidence:** High

```js
{type:"ended-by-model", timestamp:new Date().toISOString(), sessionId:e}
```

| Field | Type | Optional |
|---|---|---|
| type | literal("ended-by-model") | no |
| timestamp | string (ISO) | no |
| sessionId | string | no |

### Entry Type: continued-in (also has a Zod schema — see above)

Documented under the Zod-schema section; the two are the same type — `continued-in` was
one of the 9 types found with a real schema (in `chunk-7wy3qk0y.js`).

### Entry Type: ai-title

**Append policy:** always
**Confidence:** High

```js
{type:"ai-title", aiTitle:this.currentSessionAiTitle, sessionId:h}
```

| Field | Type | Optional |
|---|---|---|
| type | literal("ai-title") | no |
| aiTitle | string | no |
| sessionId | string | no |

### Entry Type: last-prompt

**Append policy:** always
**Confidence:** High

```js
{type:"last-prompt", ...currentSessionLastPrompt && {lastPrompt}, ...currentSessionLeafUuid && {leafUuid}, sessionId}
{type:"last-prompt", ...lastPrompt&&{lastPrompt}, leafUuid, explicit:true, ...rewound&&{rewound:true}, sessionId}
```

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("last-prompt") | no | |
| lastPrompt | string | yes | |
| leafUuid | string \| null | yes | `null` used explicitly to mean "clear" (see reader logic: `leafUuid===null && explicit===true`) |
| explicit | boolean | yes | |
| rewound | boolean | yes | |
| sessionId | string | no | |

### Entry Type: tag

**Append policy:** always
**Confidence:** High

```js
{type:"tag", tag:this.currentSessionTag, sessionId:h}
```

| Field | Type | Optional |
|---|---|---|
| type | literal("tag") | no |
| tag | string | no |
| sessionId | string | no |

### Entry Type: relocated

**Append policy:** always
**Confidence:** High

```js
{type:"relocated", relocatedCwd:this.currentSessionRelocatedCwd, sessionId:h}
{type:"relocated", sessionId:r, relocatedCwd:w}
```

| Field | Type | Optional |
|---|---|---|
| type | literal("relocated") | no |
| relocatedCwd | string | no |
| sessionId | string | no |

### Entry Type: agent-name

**Append policy:** always
**Confidence:** High

```js
{type:"agent-name", agentName:this.currentSessionAgentName, sessionId:h}
```

| Field | Type | Optional |
|---|---|---|
| type | literal("agent-name") | no |
| agentName | string | no |
| sessionId | string | no |

### Entry Type: agent-color

**Append policy:** always
**Confidence:** High

```js
{type:"agent-color", agentColor:this.currentSessionAgentColor, sessionId:h}
```

| Field | Type | Optional |
|---|---|---|
| type | literal("agent-color") | no |
| agentColor | string | no |
| sessionId | string | no |

### Entry Type: agent-setting

**Append policy:** always
**Confidence:** High (construction), Low (value type of `agentSetting`)

```js
{type:"agent-setting", agentSetting:this.currentSessionAgentSetting, sessionId:h}
```

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("agent-setting") | no | |
| agentSetting | unknown (string or small enum; exact shape not traced) | no | |
| sessionId | string | no | |

### Entry Type: pr-link

**Append policy:** always
**Confidence:** High

```js
{type:"pr-link", sessionId:h, prNumber, prUrl, prRepository, timestamp:new Date().toISOString()}
```

| Field | Type | Optional |
|---|---|---|
| type | literal("pr-link") | no |
| sessionId | string | no |
| prNumber | string or number (not disambiguated) | no |
| prUrl | string | no |
| prRepository | string | no |
| timestamp | string (ISO) | no |

### Entry Type: bridge-session

**Append policy:** always
**Confidence:** High

```js
{type:"bridge-session", sessionId, bridgeSessionId, lastSequenceNum,
 ...declaredDialogKinds?.length && {declaredDialogKinds},
 ...sessionGroupingId && {sessionGroupingId},
 ...noHistoryBackfill && {noHistoryBackfill:true},
 ...ownerAccountUuid && {ownerAccountUuid},
 ...ownerOrganizationUuid && {ownerOrganizationUuid}}
```

| Field | Type | Optional |
|---|---|---|
| type | literal("bridge-session") | no |
| sessionId | string | no |
| bridgeSessionId | string | no |
| lastSequenceNum | number (defaults to 0) | no |
| declaredDialogKinds | array of string | yes |
| sessionGroupingId | string | yes |
| noHistoryBackfill | literal(true) | yes |
| ownerAccountUuid | string | yes |
| ownerOrganizationUuid | string | yes |

### Entry Type: history-suppression

**Append policy:** always
**Confidence:** High

The dedup-canonicalization function explicitly narrows this type to two fields when
computing equality (implying these are also the only fields the entry carries in
practice):

```js
if(Me.type==="history-suppression") return S({type:Me.type, sessionId:Me.sessionId})
```

| Field | Type | Optional |
|---|---|---|
| type | literal("history-suppression") | no |
| sessionId | string | no |

### Entry Type: file-history-snapshot

**Append policy:** always
**Confidence:** High

```js
{type:"file-history-snapshot", messageId:e, snapshot:n, isSnapshotUpdate:r}
```

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("file-history-snapshot") | no | |
| messageId | string | no | |
| snapshot | unknown | no | file-history snapshot payload, shape not traced |
| isSnapshotUpdate | boolean | no | |

### Entry Type: file-history-delta

**Append policy:** always
**Confidence:** High

```js
{type:"file-history-delta", messageId:e, snapshotMessageId:n, trackingPath:r, backup:s, timestamp:new Date().toISOString()}
```

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("file-history-delta") | no | |
| messageId | string | no | |
| snapshotMessageId | string | no | |
| trackingPath | string | no | |
| backup | unknown | no | backup payload, shape not traced |
| timestamp | string (ISO) | no | |

### Entry Type: attribution-snapshot

**Append policy:** always
**Confidence:** Medium

Construction call site (`insertAttributionSnapshot`) receives an already-built object with
no literal visible in this chunk; consumption confirms a `messageId` key exists
(`ln.set(er.messageId, er)`, `messageId` used as a Map key elsewhere alongside
`file-history-snapshot`/`file-history-delta`). The assistant-message schema's
`attribution_agent`/`attribution_skill`/`attribution_plugin`/`attribution_mcp_server`/
`attribution_mcp_tool` fields strongly suggest this entry is a point-in-time snapshot of
those same attribution fields for a given message, but no direct construction site was
found to confirm the exact key names.

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("attribution-snapshot") | no | |
| messageId | string | no | confirmed via consumption site |
| (attribution fields) | unknown | unknown | plausible but unconfirmed — likely mirrors `attribution_agent`/`attribution_skill`/`attribution_plugin`/`attribution_mcp_server`/`attribution_mcp_tool` from the assistant schema |

### Entry Type: mode

**Append policy:** always
**Confidence:** High

```js
{type:"mode", mode:"acceptEdits"}
{type:"mode", mode:n.mode}
```

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("mode") | no | |
| mode | string enum (permission-mode-like values, e.g. `"acceptEdits"`) | no | exact enum not fully enumerated |

### Entry Type: permission-mode

**Append policy:** always
**Confidence:** High

```js
{type:"permission-mode", permissionMode:this.currentSessionPermissionMode, sessionId:h}
```

| Field | Type | Optional |
|---|---|---|
| type | literal("permission-mode") | no |
| permissionMode | string (permission mode enum, shared with `Vt()` in the user schema) | no |
| sessionId | string | no |

### Entry Type: isolation-latch

**Append policy:** always
**Confidence:** High

```js
{type:"isolation-latch", side:this.currentSessionIsolationLatch, sessionId:h}
```

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("isolation-latch") | no | |
| side | unknown (likely small enum — "which side of an isolation boundary") | no | |
| sessionId | string | no | |

### Entry Type: memory-mode

**Append policy:** accumulate
**Confidence:** High

```js
{type:"memory-mode", mode, afterUuid, timestamp, ...reason!==undefined&&{reason}, ...account!==undefined&&{account}, sessionId}
```

| Field | Type | Optional |
|---|---|---|
| type | literal("memory-mode") | no |
| mode | unknown (memory-mode enum) | no |
| afterUuid | string | no |
| timestamp | string (ISO) | no |
| reason | unknown | yes |
| account | unknown | yes |
| sessionId | string | no |

### Entry Type: atis-latch

**Append policy:** always
**Confidence:** High

```js
{type:"atis-latch", atis:_e, sessionId:h}
```

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("atis-latch") | no | |
| atis | unknown | no | "ATIS" not expanded/traced elsewhere in this pass |
| sessionId | string | no | |

### Entry Type: worktree-state

**Append policy:** always
**Confidence:** High

```js
{type:"worktree-state", worktreeSession:this.currentSessionWorktree, sessionId:h}
```

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("worktree-state") | no | |
| worktreeSession | unknown object (session-scoped worktree state; not traced field-by-field) | no | |
| sessionId | string | no | |

### Entry Type: queue-operation

**Append policy:** always
**Confidence:** High

```js
{type:"queue-operation", operation, timestamp:new Date().toISOString(), sessionId:V(),
 ...content!==undefined&&{content}, ...reason!==undefined&&{reason}}
```

| Field | Type | Optional |
|---|---|---|
| type | literal("queue-operation") | no |
| operation | unknown (operation-name enum/string) | no |
| timestamp | string (ISO) | no |
| sessionId | string | no |
| content | unknown | yes |
| reason | unknown | yes |

### Entry Type: content-replacement

**Append policy:** route-by-agent
**Confidence:** High (envelope), Low (replacements array item shape)

```js
{type:"content-replacement", sessionId:this.store.getSessionId(), agentId:n, replacements:e}
```

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("content-replacement") | no | |
| sessionId | string | no | |
| agentId | string | yes | routing key for `route-by-agent` append policy |
| replacements | array of unknown | no | item shape not confirmed — no construction call site with a literal array found in this pass |

### Entry Type: fork-context-ref

**Append policy:** route-by-agent
**Confidence:** Medium

```js
await Ti().appendEntry({type:"fork-context-ref", ...e}, void 0, void 0, n)
```

The full payload is a spread of a caller-supplied object `e`; the caller was not found in
this pass. Consumption confirms an `agentId` field is present:

```js
(e.type==="content-replacement"||e.type==="fork-context-ref"||e.type==="observer-ref") && e.agentId
```

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("fork-context-ref") | no | |
| agentId | string | yes | confirmed via consumption site |
| (rest of `e`) | unknown | unknown | caller-supplied object not located |

### Entry Type: observer-ref

**Append policy:** route-by-agent
**Confidence:** Medium

```js
await Ti().appendEntry({type:"observer-ref", ...e, timestamp:new Date().toISOString()}, void 0, void 0, n)
```

Same caveat as `fork-context-ref`: spread of caller-supplied `e`, caller not located.
`agentId` confirmed present via the same consumption site as above.

| Field | Type | Optional | Notes |
|---|---|---|---|
| type | literal("observer-ref") | no | |
| timestamp | string (ISO) | no | added at append time, not part of `e` |
| agentId | string | yes | confirmed via consumption site |
| (rest of `e`) | unknown | unknown | caller-supplied object not located |

---

## Methodology notes / how to extend this

1. **Locating a schema**: `python3 -c "import re; data=open('chunk-X.js').read(); ..."`
   searching for `type:<ident>\("<name>"\)` across all `*.js` in
   `~/.cache/claude-cli-src/claude/root/`. Each closure in the bundle has its **own**
   local aliases for `z.object`/`z.string`/`z.literal`/etc. — `Sd` in `chunk-bp8ekm6v.js`
   is unrelated to `R` in `chunk-y68kda6q.js`; there is no bundle-wide consistent alias.
2. **Extracting a full statement**: brace/paren-balanced scan from `<name>=` to the
   matching top-level `;`, skipping over string/template literal contents (a naive
   paren-counter breaks on `.describe("...(...)")` text containing unbalanced
   parentheses).
3. **`clisrc.py --fn NAME`** (in this scratchpad) does brace-matched extraction directly
   from the live binary and was used to confirm the `Sbe` (`cost-state`) reference schema
   given in the task.
4. For the 26 types with no Zod schema, further confidence can only come from finding
   more construction/consumption call sites — there is no schema left to find; TypeScript
   interface names are erased at compile time and do not appear in the bundle.
