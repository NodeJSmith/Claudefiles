# Claude Code JSONL Transcript Anatomy

Complete structural inventory of Claude Code session transcripts (`.jsonl` files under `~/.claude/projects/`).

Sampled from 30 transcripts across Dotfiles, hassette, claude-code-recall, and other projects. Cross-referenced with the transcript-reader MCP source at `~/.local/share/custom-claude-mcps/transcript-reader/server.py`.

---

## File Layout

| Location | Contains |
|---|---|
| `~/.claude/projects/<project-dir-slug>/<session-uuid>.jsonl` | Main session transcript |
| `~/.claude/projects/<project-dir-slug>/<session-uuid>/subagents/agent-<id>.jsonl` | Subagent transcript (same JSONL format, subset of event types) |
| `~/.claude/projects/<project-dir-slug>/<session-uuid>/subagents/agent-<id>.meta.json` | Subagent metadata (keys: `agentType`, `description`, `model`, `spawnDepth`, `toolUseId`) |

The `<project-dir-slug>` encodes the working directory path with `-` replacing `/` (e.g., `-home-jessica-Dotfiles`). Worktrees get their own slug (e.g., `-home-jessica-source-hassette--claude-worktrees-new-ui`).

---

## Event Types (top-level `type` field)

Every JSONL line is one event. The `type` field discriminates them.

### 1. `user` — Human/system input

**Top-level keys:** `cwd`, `entrypoint`, `gitBranch`, `isMeta`, `isSidechain`, `message`, `origin`, `parentUuid`, `permissionMode`, `promptId`, `promptSource`, `sessionId`, `session_id`, `sourceToolAssistantUUID`, `sourceToolUseID`, `timestamp`, `toolUseResult`, `type`, `userType`, `uuid`, `version`

**`message` keys:** `content`, `role` (always `"user"`)

**`message.content`** is either:
- A **string** (plain user text)
- An **array** of content blocks (tool results, documents, text)

**Content block types in user messages:**
- `text` — keys: `type`, `text`
- `tool_result` — keys: `type`, `tool_use_id`, `content`, `is_error`
  - `content` is either a **string** or an **array** of nested blocks:
    - `text` — keys: `type`, `text`
    - `image` — keys: `type`, `source` (`source.type`: `"base64"`)
    - `tool_reference` — keys: `type`, `tool_name`
- `document` — keys: `type`, `source` (`source.type`: `"base64"`, `source.media_type`: `"application/pdf"`)

**`toolUseResult`** (optional, attached to tool_result events) — rich structured metadata about the tool execution. Keys vary by tool:
- Common: `type`, `status`, `durationMs`, `durationSeconds`
- Bash: `stdout`, `stderr`, `code`, `codeText`, `returnCodeInterpretation`, `noOutputExpected`
- Read: `content`, `filePath`, `bytes`, `isImage`
- Edit: `oldString`, `newString`, `replaceAll`, `originalFile`, `structuredPatch`
- Write: `filePath`, `content`
- Agent: `agentId`, `agentType`, `totalTokens`, `totalToolUseCount`, `totalDurationMs`, `toolStats`, `usage`
- Skill: `result`, `commandName`
- AskUserQuestion: `questions`, `answers`, `userModified`
- WebSearch/WebFetch: `url`, `query`, `searchCount`, `results`
- Task*: `taskId`, `task`, `updatedFields`
- ToolSearch: `total_deferred_tools`, `matches`
- SendUserFile: `file`, `caption`
- General: `success`, `interrupted`, `statusChange`, `attachments`, `prompt`

**Enum values:**
- `promptSource`: `"typed"`, `"queued"`, `"sdk"`, `"system"`
- `origin.kind`: `"human"`, `"channel"`, `"task-notification"`
- `toolUseResult.type`: `"text"`, `"image"`, `"pdf"`, `"create"`
- `toolUseResult.status`: `"completed"`
- `entrypoint`: `"cli"`, `"sdk-py"`
- `userType`: `"external"`
- `isMeta`: `true`/`false` (meta events are system-injected, not human)

### 2. `assistant` — Model response

**Top-level keys:** `attributionSkill`, `cwd`, `effort`, `entrypoint`, `gitBranch`, `isSidechain`, `message`, `parentUuid`, `requestId`, `sessionId`, `session_id`, `timestamp`, `type`, `userType`, `uuid`, `version`

**`message` keys:** `container`, `content`, `context_management`, `diagnostics`, `id`, `model`, `role` (always `"assistant"`), `stop_details`, `stop_reason`, `stop_sequence`, `type`, `usage`

**`message.content`** is an array of:
- `text` — keys: `type`, `text` (the model's visible output)
- `thinking` — keys: `type`, `thinking`, `signature` (extended thinking content)
- `tool_use` — keys: `type`, `id`, `name`, `input`, `caller`
  - `caller.type`: `"direct"`

**`message.usage`** keys: `cache_creation`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `inference_geo`, `input_tokens`, `iterations`, `output_tokens`, `output_tokens_details`, `server_tool_use`, `service_tier`, `speed`

**Enum values:**
- `message.stop_reason`: `"end_turn"`, `"tool_use"`
- `message.model`: `"claude-opus-4-6"`, `"claude-sonnet-5"` (and older models in older transcripts)
- `effort`: `"high"` (others possible)
- `attributionSkill`: skill names like `"mine.commit-push"`, `"i-audit"`, etc.

### 3. `system` — Internal system events

**Common keys:** `content`, `cwd`, `entrypoint`, `gitBranch`, `isMeta`, `isSidechain`, `level`, `parentUuid`, `sessionId`, `session_id`, `subtype`, `timestamp`, `type`, `userType`, `uuid`, `version`

**Subtypes (`subtype` field):**

| Subtype | Extra keys | Description |
|---|---|---|
| `turn_duration` | `durationMs`, `messageCount` | How long an assistant turn took |
| `stop_hook_summary` | `hasOutput`, `hookAdditionalContext`, `hookCount`, `hookErrors`, `hookInfos`, `preventedContinuation`, `stopReason`, `toolUseID` | Hook execution summary after a stop |
| `local_command` | `level` | A `/command` was run locally |
| `away_summary` | — | Summary generated when user was away |
| `compact_boundary` | `compactMetadata` (see below), `slug` | Context window compaction event |
| `api_error` | `error` (status, headers, requestID, type, formatted, connection, isNetworkDown, rateLimits), `retryInMs`, `retryAttempt`, `maxRetries` | API call failure/retry |
| `scheduled_task_fire` | — | A scheduled/cron task fired |
| `bridge_status` | `url` | Remote control session status |

**`compact_boundary.compactMetadata` keys:** `trigger`, `preTokens`, `postTokens`, `durationMs`, `preCompactDiscoveredTools`, `preservedSegment` (`headUuid`, `anchorUuid`, `tailUuid`), `preservedMessages` (`anchorUuid`, `uuids`, `allUuids`), `cumulativeDroppedTokens`, `messagesSummarized`, `userContext`

**Enum values:**
- `level`: `"info"`, `"suggestion"`, `"error"`
- `compactMetadata.trigger`: `"manual"` (others possible)

### 4. `attachment` — Context injections

**Top-level keys:** `attachment`, `cwd`, `entrypoint`, `gitBranch`, `isSidechain`, `parentUuid`, `sessionId`, `session_id`, `timestamp`, `type`, `userType`, `uuid`, `version`

**`attachment.type` values (28 distinct types):**

| Type | Key fields | Description |
|---|---|---|
| `hook_success` | `hookName`, `hookEvent`, `stdout`, `stderr`, `exitCode`, `durationMs` | Hook ran successfully |
| `hook_additional_context` | `hookName`, `hookEvent`, `text` | Hook injected context |
| `hook_cancelled` | `hookName`, `hookEvent` | Hook was cancelled |
| `hook_system_message` | — | System-level hook message |
| `async_hook_response` | — | Async hook response |
| `edited_text_file` | `path`, `snippet`, `displayPath` | A file was edited |
| `file` | `filename`, `content` | A file attachment |
| `skill_listing` | `skillCount`, `names` | Available skills list |
| `agent_listing_delta` | `addedNames`, `removedNames`, `addedTypes`, `removedTypes`, `readdedNames` | Agent list changed |
| `deferred_tools_delta` | `addedNames`, `removedNames`, `itemCount` | Deferred tools changed |
| `deferred_tools_record` | — | Deferred tools snapshot |
| `command_permissions` | `allowedTools` | Tool permission update |
| `mcp_instructions_delta` | `addedBlocks`, `addedLines` | MCP instructions changed |
| `total_tokens_reminder` | — | Token count reminder |
| `task_reminder` | — | Task list reminder |
| `nested_memory` | — | Memory recall |
| `queued_command` | `command`, `commandMode` | A queued command |
| `environment` | — | Environment info |
| `date` | — | Current date |
| `date_change` | — | Date changed during session |
| `instructions` | — | Instructions injected |
| `invoked_skills` | — | Skills that were invoked |
| `model` | — | Model info |
| `session_context` | — | Session context |
| `prompt_snapshot` | `prompt` | Prompt snapshot |
| `plan_mode_exit` | — | Exited plan mode |
| `compact_file_reference` | — | File reference from compaction |
| `remote_session_change` | — | Remote session state changed |

**Hook event types (`hookEvent`):** `SessionStart`, `PreToolUse`, `Stop`, `Notification`, `UserPromptSubmit`

**Hook name patterns (`hookName`):** `"SessionStart"`, `"SessionStart:startup"`, `"SessionStart:clear"`, `"Stop"`, `"PreToolUse:Bash"`, `"PreToolUse:Read"`, `"PreToolUse:Edit"`, `"PreToolUse:TaskCreate"`, `"PreToolUse:TaskUpdate"`, `"PreToolUse:mcp__<server>__<tool>"`, etc.

### 5. `last-prompt` — Session resume state

**Keys:** `type`, `sessionId`, `leafUuid`, `lastPrompt` (optional — the user's last message text)

### 6. `ai-title` — Auto-generated session title

**Keys:** `type`, `sessionId`, `aiTitle`

### 7. `custom-title` — User-set session title

**Keys:** `type`, `sessionId`, `customTitle`

### 8. `mode` — Mode change

**Keys:** `type`, `sessionId`, `mode`

**`mode` values:** `"normal"` (others possible — plan mode, etc.)

### 9. `permission-mode` — Permission mode change

**Keys:** `type`, `sessionId`, `permissionMode`

**`permissionMode` values:** `"bypassPermissions"` (others exist)

### 10. `bridge-session` — Remote control link

**Keys:** `type`, `sessionId`, `bridgeSessionId`, `lastSequenceNum`

### 11. `pr-link` — PR association

**Keys:** `type`, `sessionId`, `timestamp`, `prNumber`, `prRepository`, `prUrl`

### 12. `queue-operation` — Message queue events

**Keys:** `type`, `sessionId`, `timestamp`, `operation`, `content`

**`operation` values:** `"enqueue"`, `"dequeue"`, `"popAll"`, `"remove"`

### 13. `worktree-state` — Worktree session info

**Keys:** `type`, `sessionId`, `worktreeSession`

### 14. `file-history-delta` — File backup diff

**Keys:** `type`, `messageId`, `snapshotMessageId`, `timestamp`, `trackingPath`, `backup` (object)

### 15. `file-history-snapshot` — File backup snapshot

**Keys:** `type`, `messageId`, `isSnapshotUpdate`, `snapshot` (object with `messageId`, `timestamp`, `trackedFileBackups`)

### 16. `cost-state` — Session cost tracking

**Keys:** `type`, `sessionId`, `startTime`, `totalCostUSD`, `totalDuration`, `totalAPIDuration`, `totalAPIDurationWithoutRetries`, `totalToolDuration`, `totalLinesAdded`, `totalLinesRemoved`, `hasUnknownModelCost`, `modelUsage`

**`modelUsage`** is keyed by model ID (e.g., `"claude-sonnet-5"`) with per-model:
- `inputTokens`, `outputTokens`, `thinkingTokens`, `cacheCreationInputTokens`, `cacheReadInputTokens`, `costUSD`, `webSearchRequests`

### 17. `atis-latch` — ATIS state

**Keys:** `type`, `sessionId`, `atis` (string)

---

## Envelope Fields (appear across multiple event types)

| Field | Type | Description |
|---|---|---|
| `uuid` | string | Unique event ID |
| `parentUuid` | string/null | Previous event in the conversation tree |
| `sessionId` | string | Session UUID |
| `session_id` | string | Alternative session ID field (newer?) |
| `timestamp` | ISO 8601 string | When the event occurred |
| `type` | string | Event type discriminator |
| `cwd` | string | Working directory |
| `entrypoint` | string | `"cli"` or `"sdk-py"` |
| `gitBranch` | string | Current git branch |
| `version` | string | Claude Code version (e.g., `"2.1.170"`) |
| `userType` | string | Always `"external"` in observed data |
| `isSidechain` | boolean | Whether this is a sidechain event |
| `isMeta` | boolean | Whether this is a meta/system-injected event |

---

## Content Block Types Summary

| Block type | Appears in | Keys |
|---|---|---|
| `text` | assistant content, user content, tool_result content | `type`, `text` |
| `thinking` | assistant content | `type`, `thinking`, `signature` |
| `tool_use` | assistant content | `type`, `id`, `name`, `input`, `caller` |
| `tool_result` | user content | `type`, `tool_use_id`, `content`, `is_error` |
| `document` | user content | `type`, `source` (base64 + media_type) |
| `image` | tool_result content | `type`, `source` (base64) |
| `tool_reference` | tool_result content | `type`, `tool_name` |

---

## Tool Names Observed (across 30 transcripts)

**Built-in tools:** `Agent`, `AskUserQuestion`, `Bash`, `CronCreate`, `CronDelete`, `Edit`, `ListAgents`, `Monitor`, `Read`, `ReadMcpResourceTool`, `ScheduleWakeup`, `SendMessage`, `SendUserFile`, `Skill`, `TaskCreate`, `TaskOutput`, `TaskStop`, `TaskUpdate`, `ToolSearch`, `WebFetch`, `WebSearch`, `Write`

**MCP tools (prefixed `mcp__<server>__<tool>`):**
- `mcp__plugin_playwright_playwright__browser_*` (click, navigate, resize, snapshot, take_screenshot, console_messages, evaluate, fill_form, press_key, select_option, type)
- `mcp__home-assistant__ha_config_*` (get_dashboard, list_dashboard_resources, set_dashboard, set_dashboard_resource)
- `mcp__browser-feedback__get_connection_status`
- `mcp__claude-design__list_files`, `mcp__claude-design__read_file`
- `mcp__serena__get_symbols_overview`, `mcp__serena__initial_instructions`

---

## What the transcript-reader MCP handles vs. misses

The transcript-reader (`server.py`) processes only `type: "user"` and `type: "assistant"` events. It formats:
- Assistant `text` blocks → `[ASSISTANT] ...`
- Assistant `tool_use` blocks → `[TOOL_CALL:xxxx] name(input)`
- User string content → `[USER] ...`
- User `tool_result` blocks → `[TOOL_RESULT:name:xxxx] content`
- User `toolUseResult` metadata → appended as `(agent=..., output=...)` on Agent results

**Not surfaced by transcript-reader:**
- `system` events (subtypes: turn_duration, compact_boundary, api_error, away_summary, etc.)
- `attachment` events (all 28 types — hooks, skill listings, context injections, etc.)
- `thinking` blocks (the thinking content is in assistant messages but `_format_content_block` doesn't handle it)
- `document` blocks in user messages
- `image` blocks in tool results
- `tool_reference` blocks in tool results
- All metadata-only events: `last-prompt`, `ai-title`, `custom-title`, `mode`, `permission-mode`, `bridge-session`, `pr-link`, `queue-operation`, `worktree-state`, `file-history-*`, `cost-state`, `atis-latch`
- Envelope metadata: `timestamp`, `cwd`, `gitBranch`, `version`, `uuid`, `effort`, `attributionSkill`, `requestId`
- `message.usage` (token counts per response)
- `message.model` (which model responded)

---

## Searchable Dimensions (for Phase 2)

When auditing "how often do we search transcripts," look for searches targeting any of these:

1. **Tool calls** — by tool name, input parameters, tool_use_id
2. **Tool results** — by content, is_error, tool_use_id
3. **User messages** — by text content
4. **Assistant text** — by output text
5. **Thinking blocks** — by thinking content
6. **System events** — by subtype (compact_boundary, api_error, turn_duration)
7. **Attachment events** — by attachment type (hook results, skill listings, context injections)
8. **Hook data** — by hookName, hookEvent, stdout/stderr
9. **Metadata** — timestamps, models, token usage, cost, effort level
10. **Session identity** — sessionId, cwd, gitBranch, version, entrypoint
11. **Conversation structure** — parentUuid chains, isSidechain, isMeta
12. **Subagent data** — via meta.json (agentType, model, description) and their transcripts
13. **File history** — file-history-delta/snapshot events, backup content
14. **PR associations** — pr-link events
15. **Queue operations** — enqueued user messages
16. **Cost/usage** — cost-state events, per-response message.usage
17. **Compaction events** — compact_boundary with pre/post token counts
18. **API errors** — error status, retry info
19. **Attribution** — which skill produced a response (attributionSkill)
