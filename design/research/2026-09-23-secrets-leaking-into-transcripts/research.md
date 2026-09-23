---
topic: "Preventing secrets/tokens from leaking into Claude Code session transcripts"
date: 2026-09-23
status: Draft
---

# Prior Art: Preventing Secrets from Leaking into AI Coding Agent Transcripts

## The Problem

Agentic coding tools routinely read files and run commands as part of normal operation. When one of those files or command outputs happens to contain a live credential — a `.env` value, an OAuth token in an auth.json, a `docker compose config` dump that resolves an `env_file:` reference — that credential gets printed verbatim into the tool result, which becomes part of the model's context and is persisted to the session transcript on disk. This is distinct from committing a secret to git (which pre-commit scanners already catch): the leak happens purely through the agent *reading* or *running* something, with no commit involved, so git-diff-based scanners never see it.

## How We Do It Today

`secrets-auditor` (Claudefiles) scans `git diff --cached`, `git diff`, and untracked files for known key patterns — but it's dispatched on-demand (e.g. via `mine-ship`/`mine-review`), not wired into any hook, and it only ever looks at git state. None of the four recent local incidents (tmux argv exposure, `docker compose config` leaking `env_file` secrets, `bills-bot.env` key exposure via grep, and today's `auth.json` full-file cat) involved a git-tracked change — all were live Read/Bash surface leaks that secrets-auditor's scope never touches. The hook mechanism itself is proven out locally (`security_guard.py` denies dangerous Bash commands by regex on the command *input*, matched via PreToolUse), but no existing hook is matched on `Read`, and no existing hook scans Bash *output*. There is zero redaction/masking anywhere in either repo.

## Patterns Found

### Pattern 1: Runtime Hook-Based Output Redaction (PostToolUse)

**Used by**: `SilentAutomaton/redact-hook`, `l-mb/claude-code-redaction-hooks`, a `ruvnet` gist, `moneymikeMD/night-watchman`, amux.io's cookbook `sed`-filter recipe.

**How it works**: A PostToolUse hook matched against `Read`, `Bash`, and MCP tool calls runs after the tool has executed but before Claude reads the result. It regex-scans the raw output for secret-shaped strings (AWS keys, `sk-`/`ghp_`-style prefixes, generic high-entropy assignments) and either masks matches or replaces the whole output via Claude Code's `updatedToolOutput` field. Content-based, not command-based — catches a leak regardless of *which* command produced it.

**Strengths**: Doesn't require enumerating every command that could leak a secret — a `cat`, a `docker compose config`, a `grep -n .env`, and a `printenv` all get caught the same way, since detection looks at what came out, not what was typed. Cheap (regex-only, negligible latency).

**Weaknesses**: Only catches known secret shapes — false negatives on non-standard formats, false positives on legitimate high-entropy strings (hashes, UUIDs). Confirmed real failure mode: a hook can be wired up and documented as active protection while never actually firing on real tool calls (`cooneycw/claude-power-pack` #1206) — must be verified end-to-end, not just unit-tested. Confirmed side-channel gap: Claude Code's automatic "file changed on disk" re-read notification can re-inject a file's content through a path this hook type doesn't intercept (`anthropics/claude-code` #94082).

**Example**: https://github.com/SilentAutomaton/redact-hook (cleanest, single-file, dependency-free, explicitly covers Read/Bash/MCP), https://github.com/l-mb/claude-code-redaction-hooks

### Pattern 2: Pre-Execution Blocking (PreToolUse deny / `permissions.deny`)

**Used by**: aitmpl.com's hook cookbook, `l-mb/claude-code-redaction-hooks`, general Claude Code hook guides.

**How it works**: A PreToolUse hook inspects the file path or command *before* it runs. If the path matches a denylist (`.env`, `*.pem`, `secrets/**`, `~/.ssh/**`, `.mcp.json`) the hook exits 2, blocking the call entirely — nothing executes, so there's no output to leak in the first place. Stronger when implemented as `permissions.deny` entries in `settings.json` (enforced by the harness's own permission system) rather than a hook script.

**Strengths**: Strictly stronger than output redaction when it applies — no execution, no side effect, no output to scan. `permissions.deny` is enforced structurally, not by agent cooperation.

**Weaknesses**: Enumerable by filename only — does nothing for a secret embedded in a file that isn't on the denylist (a hardcoded key inside `config.yaml`), or one surfaced by an unanticipated command (`docker compose config` resolving `env_file:`, which is exactly today's opencode `auth.json` cat and the earlier hautomate incident). Best paired with Pattern 1, not used alone.

**Example**: https://aitmpl.com/blog/security-hooks-secrets/

### Pattern 3: Third-Party Cross-Agent Real-Time Secret Scanning (ggshield)

**Used by**: GitGuardian's `ggshield`, with explicit support for Cursor, Claude Code, Copilot Chat, Codex, and Mistral Vibe.

**How it works**: `ggshield install` wires into the agent's lifecycle at three points — user prompts (scanned before reaching the model), MCP tool calls (scanned before execution), and tool output (desktop notification on detection). Effectively Patterns 1+2 combined into one maintained product, backed by GitGuardian's 500+-signature detection engine rather than hand-rolled regex.

**Strengths**: Detection quality benefits from a continuously maintained signature database instead of a few regexes. Covers prompt input, tool-call input, and output in one install. The only source found explicitly claiming multi-agent support beyond Claude Code alone.

**Weaknesses**: Third-party dependency with a network-connected scanning path added to every tool call (latency + trust surface). **Confirmed via GitGuardian's own docs (2026-09-23 follow-up)**: only the prompt-submission and pre-tool-use stages actually block. The post-tool-use stage is a desktop *notification only* — it does not redact or withhold output, and by the time it fires the secret has already reached the model's context and the transcript. This means ggshield does **not** cover the failure mode this brief is centered on (an unanticipated command's output containing a secret) — it only alerts after the fact, same outcome as having no protection at that stage. Also requires a GitGuardian account + API key (not local-only), and **fails open**: per their docs, if ggshield can't reach the GitGuardian API (unauthenticated, network down, misconfigured) "it does not block the action" — silent-permissive on failure. Install syntax is also mid-migration (`ggshield install -t <agent>` deprecated as of 1.53.0 in favor of `ggshield machine setup`).

**Example**: https://www.gitguardian.com/ggshield, https://docs.gitguardian.com/ggshield-docs/integrations/ai-coding-tools/secret-scanning-for-ai-coding-tools (canonical docs, confirms the block/notify split above)

### Pattern 4: Deny-by-Default Ignore/Permission Files (`.claudeignore` / `permissions.deny`)

**Used by**: Claude Code, Cursor (`.cursorignore`), Windsurf, JetBrains AI, plus the community `claude-agentignore` project layering stricter enforcement on top.

**How it works**: A gitignore-syntax file (or `permissions.deny`) declares paths the agent should never read. Intent: refuse access before any content loads into context at all — the earliest possible intervention point.

**Strengths**: Cheapest, simplest control conceptually — no regex, no scanning. `permissions.deny` specifically is enforced by the harness's own permission system.

**Weaknesses**: **Confirmed unreliable for the convention-file form** — The Register (Jan 2026) documented Claude Code reading `.env` even when explicitly listed in `.claudeignore`; a JetBrains YouTrack issue documents the same gap for `.aiignore`. Same enumerability limitation as Pattern 2. `permissions.deny` is repeatedly recommended *instead of* the ignore-file convention for exactly this reason.

**Example**: https://github.com/yurekami/claude-agentignore, https://www.theregister.com/software/2026/01/28/claude-code-ignores-ignore-rules-meant-to-block-secrets/4336684

### Pattern 5: Eliminate the Secret-Bearing File Entirely (Secrets Manager / Short-Lived Injection)

**Used by**: General Claude Code security guidance (generalanalysis.com), independent developer tooling (dev.to "encrypted secrets manager" writeup).

**How it works**: Instead of filtering what the agent sees, remove plaintext secrets from the filesystem entirely. Store them in a secrets manager (1Password, Vault, an encrypted local store) and inject into the process environment only at the moment a command needs them — never persisted as a standing `.env`/`auth.json` file.

**Strengths**: Root-cause fix — no hook or ignore-file gap can leak a secret that isn't on disk in plaintext. Also shrinks blast radius for whatever does leak (short-lived/scoped vs. long-lived master credentials).

**Weaknesses**: Bigger lift than a hook — requires re-architecting how the project sources secrets. Doesn't help with files that must exist on disk for other tooling regardless (some CLIs, including opencode itself, only support file-based token storage).

**Example**: https://generalanalysis.com/guides/anthropic-claude-code-security-best-practices

## Anti-Patterns

- **Trusting CLAUDE.md prose as the only control.** `anthropics/claude-code` #44868: Claude Code read `.env`/`.dev.vars` via `grep -n` and `Read` *despite* an explicit CLAUDE.md prohibition. A textual instruction isn't a structural control and gets bypassed by tool calls it didn't anticipate.
- **Assuming a documented redaction hook is actually running.** `cooneycw/claude-power-pack` #1206: the masking logic passed its own tests, but the hook invoking it never fired on real tool calls — README claimed protection that provided none. Verify end-to-end against a real tool call, not just the function in isolation.
- **Relying on `.claudeignore`/`.aiignore` as a security boundary.** Documented unenforced in real usage (The Register, JetBrains YouTrack). Treat as UX convenience only; put actual enforcement in `permissions.deny`.
- **Only covering the primary `Read`/`Bash` call and missing side channels.** `anthropics/claude-code` #94082: the "file changed on disk" auto re-read notification bypassed a PreToolUse block on the same file.
- **Redacting command text (input) but not command output.** `twistedmelonman/claude-config` PR #538: the majority failure mode is an innocuous command (`cat`, `env`, `docker compose config`) *printing* a secret nobody typed — input-side scrubbing does nothing for that.

## Emerging Trends

- Commercial vendors (GitGuardian) are building first-class, cross-agent runtime protection rather than leaving this to community hook scripts — signals a maturing "AI agent secret scanning" category distinct from traditional pre-commit scanning.
- Prompt-injection research treats accidental leakage and deliberate credential exfiltration as the same underlying surface: if an agent's context never contains plaintext secrets, a successful injection has nothing to steal. Defenses that reduce accidental leaks (output scanning, deny-by-default access, keeping secrets off disk) double as injection mitigations.

## Relevance to Us

This setup already has every mechanical piece Pattern 1 and Pattern 2 need — the PreToolUse/PostToolUse hook plumbing (`security_guard.py` proves regex-based Bash-input denial already works here), a `settings.json` merge pipeline across Claudefiles/Dotfiles/machine layers that's the natural place to register a new hook, and `secrets-auditor`'s existing regex patterns for provider key shapes that could be reused rather than rewritten. What's missing is entirely additive: no hook is currently matched on `Read`, and no hook scans Bash output. All four recent local incidents are exactly what Pattern 1 (output-side scanning) would catch, since none involved a predictable filename Pattern 2/4 could have denylisted in advance — `auth.json`, `bills-bot.env`, and a `docker compose config` dump aren't names you'd think to pre-list, but a live OAuth token or `sk-`-prefixed key is a shape a regex scanner catches regardless of which file it came from.

Pattern 4 (ignore files) is the weakest fit for this codebase's actual incident history — the incidents weren't caused by a missing denylist entry, they were caused by content-based leaks from files/commands nobody had listed in advance, and the research shows ignore-file enforcement is documented as unreliable besides. Pattern 5 (eliminate the file) is already partially true here for 1Password-sourced secrets (`personal.tpl` → `op inject`) but doesn't apply to opencode's `auth.json`, which is a third-party tool's own token cache this repo doesn't control.

## Recommendation

Build a PostToolUse hook (Pattern 1) matched on `Read|Bash` that regex-scans tool output for secret shapes and replaces matches with a placeholder via `updatedToolOutput`, reusing `secrets-auditor`'s existing key-pattern regexes as the starting signature set rather than writing new ones. Pair it with a small `permissions.deny` addition (Pattern 2/harness-enforced, not the unreliable ignore-file convention) for a short list of known-dangerous paths (`auth.json` under known CLI config dirs, `*.pem`, `id_rsa*`) as defense-in-depth, not as the primary control — the incident history shows the output-scanning layer is the one that actually would have caught what happened.

Two things to build in from the start, since both are documented real-world failure modes rather than hypothetical: (1) a way to verify the hook actually fires on a real tool call (a test invocation, not just a unit test of the redaction function alone) — `cooneycw/claude-power-pack` #1206 is the cautionary tale; (2) awareness that PostToolUse fires after execution, so it protects the transcript/context but not any external system the command already touched (e.g., it wouldn't have stopped `dumpsys`/`cat` from having already run — only from having its output reach the model).

**Update (2026-09-23, confirmed against GitGuardian's canonical docs):** `ggshield` is a complement, not a substitute, for the hook above. Its prompt-submission and pre-tool-use stages genuinely block and are cheap to add (`ggshield install`), but its post-tool-use stage — the one that matters for this brief's incident class — is notification-only and does not redact. It would not have prevented any of the four local incidents from reaching the transcript; it would only have alerted after the fact. It also requires a GitGuardian account/API key (not local-only) and fails open on auth/network failure. Worth adding for the free blocking coverage it does provide, but the local PostToolUse redaction hook remains necessary for the actual problem.

## Sources

### Reference implementations
- https://github.com/SilentAutomaton/redact-hook — cleanest single-file PostToolUse redaction hook, covers Read/Bash/MCP
- https://github.com/l-mb/claude-code-redaction-hooks — dedicated hook package for secret/PII leakage prevention
- https://gist.github.com/ruvnet/332336ad5e0516daa810d98f8f0ddca9 — minimal redaction hook example
- https://github.com/twistedmelonman/claude-config/pull/538 — names the input-vs-output redaction gap explicitly
- https://github.com/moneymikeMD/night-watchman/pull/48 — output-side secret-shaped-value redaction for Bash
- https://github.com/yurekami/claude-agentignore — stricter three-tier ignore/ban/exclude enforcement layer

### Blog posts & writeups
- https://scottspence.com/posts/nopeek-keep-secrets-out-of-claude-code — "nopeek" tool/approach
- https://aitmpl.com/blog/security-hooks-secrets/ — PreToolUse Edit/Write secret-blocking walkthrough
- https://amux.io/guides/claude-code-hooks-cookbook/ — sed-filter output redaction recipe
- https://claudcod.com/blog/claude-code-hooks-modify-output/ — `updatedToolOutput` mechanics and limitations
- https://dev.to/olicastle/your-ai-coding-agent-is-reading-your-env-right-now-3909 — practitioner account of routine .env exposure
- https://dev.to/jack_baum_08809d366a13558/i-built-an-encrypted-secrets-manager-so-my-ai-coding-agent-stops-leaking-api-keys-3386 — secrets-manager-first mitigation
- https://dev.to/crypled/i-audited-my-own-claude-code-logs-and-found-real-leaked-credentials-3oo — retroactive transcript-log audit finding real leaked creds
- https://www.knostic.ai/blog/claude-cursor-env-file-secret-leakage — cross-agent (Claude + Cursor) .env mishandling research
- https://bdtechtalks.com/2026/04/27/claude-code-api-token-leak/ — leaked keys propagating into public package registries
- https://www.helpnetsecurity.com/2026/04/15/product-showcase-gitguardian-ggshield-ai-hook/ — ggshield product coverage
- https://www.theregister.com/software/2026/01/28/claude-code-ignores-ignore-rules-meant-to-block-secrets/4336684 — .claudeignore enforcement gap
- https://labs.cloudsecurityalliance.org/research/csa-research-note-claude-code-github-action-prompt-injection/ — CI/CD analog via pull_request_target
- https://venturebeat.com/security/ai-agent-runtime-security-system-card-audit-comment-and-control-2026 — cross-vendor prompt-injection secret leak report

### Documentation & standards
- https://hidekazu-konishi.com/entry/claude_code_hooks_complete_guide.html — PreToolUse/PostToolUse mechanics reference
- https://code.claude.com/docs/en/best-practices — official docs (no dedicated redaction feature found)
- https://generalanalysis.com/guides/anthropic-claude-code-security-best-practices — permissions.deny + workload-identity recommendations
- https://www.gitguardian.com/ggshield — cross-agent real-time secret scanning product
- https://docs.gitguardian.com/releases/saas/2026/04/10/changelog — ggshield AI-agent hook changelog
- https://github.com/anthropics/claude-code/issues/58043 — Read/cat config leak bug report
- https://github.com/anthropics/claude-code/issues/44868 — grep -n bypasses CLAUDE.md prohibition
- https://github.com/anthropics/claude-code/issues/59094 — no first-party redaction, remediation left to user
- https://github.com/anthropics/claude-code/issues/94082 — file-changed-on-disk re-read side channel
- https://github.com/cooneycw/claude-power-pack/issues/1206 — documented-but-inert redaction hook
- https://youtrack.jetbrains.com/projects/LLM/issues/LLM-20693/Claude-Agent-ignores-.aiignore — JetBrains .aiignore gap
- https://arxiv.org/pdf/2509.22040 — academic study of prompt injection in agentic coding editors
