---
proposal: "Set up OpenAI and Google Gemini model access as tools that Claude Code subagents can use programmatically for cross-model review, arena-style parallel implementations, and adversarial verification."
date: 2026-06-06
status: Draft
flexibility: Exploring
motivation: "Enable Claude Code to dispatch work to other model families. The user has subscriptions to both OpenAI and Google but no tooling installed. These models will never be used directly -- only consumed by Claude Code subagents."
constraints: "Ubuntu (VPS + WSL2), uv for Python tooling, must work from subagents, practical and installable today"
non-goals: "Direct human use of these models, replacing Claude as the primary model"
depth: deep
---

# Research Brief: Multi-Model Access for Claude Code Subagents

**Initiated by**: How to set up OpenAI and Google Gemini models as tools Claude Code subagents can call programmatically.

## Context

### What prompted this

The user wants Claude Code to dispatch work to OpenAI and Gemini models for three use cases: cross-model code review (a second opinion from a different model family), arena-style parallel implementations (same task, different models, compare outputs), and adversarial verification (one model checking another's work). The user has ChatGPT and Google subscriptions but no API keys or tooling configured.

### Current state

The Claudefiles repo has no multi-model tooling. No OpenAI or Gemini API keys are configured. No MCP servers for external models are registered. All subagent work currently runs on Claude models (Haiku, Sonnet, Opus) via the built-in Agent tool.

### Key constraints

- Subagents are the consumer, not the user directly
- Must work on Ubuntu (VPS and WSL2 machines)
- User prefers `uv` for Python package management
- ChatGPT subscription billing is separate from OpenAI API billing (confirmed: a ChatGPT Plus/Pro subscription does NOT include API credits)
- Gemini has a free tier via AI Studio for Flash models; Pro models became paid-only April 2026

## Critical Finding: Subagent MCP Access

The official Claude Code docs (as of v2.1.153+) confirm that subagents **do** support MCP servers via the `mcpServers` frontmatter field. This means:

- You can define inline MCP servers scoped to specific subagents
- MCP tools are inherited from the parent session by default
- Inline definitions keep MCP tool descriptions out of the main conversation context

This is the load-bearing finding. Earlier GitHub issues (#34935, #13254, #23374) reported MCP access as broken or missing in subagents. The current docs describe working `mcpServers` support with inline definitions. The Bash tool is also available to all subagents, so CLI-based approaches work regardless.

## Feasibility Analysis

### What would need to change

| Area | Work | Effort | Risk |
|------|------|--------|------|
| API key setup | Create accounts at platform.openai.com and aistudio.google.com, add credits, generate keys | Low | None |
| Tool installation | Install chosen CLI/MCP tools | Low | None |
| Agent definitions | Create subagent `.md` files with MCP or Bash-based model access | Low | None |
| Skills/workflows | Modify review and challenge skills to optionally dispatch to external models | Medium | Integration testing needed |

### What already supports this

- Subagent `mcpServers` frontmatter allows scoped MCP server definitions per agent
- Subagents have Bash tool access, enabling CLI-based approaches
- The existing agent/skill architecture (code-reviewer, challenge critics) already uses parallel subagent dispatch -- adding external models is a routing change, not an architecture change
- `uv tool install` works for Python CLI tools

### What works against this

- MCP servers add tool descriptions to context, consuming tokens (the RLabs Gemini MCP exposes 37 tools by default)
- API latency for external models adds to subagent execution time
- ChatGPT subscription does not include API credits -- separate prepaid billing required at platform.openai.com ($5 minimum)
- Gemini free tier has rate limits (1,500 RPD for Flash, 50 RPD for 2.5 Pro)

## Options Evaluated

### Option A: Simon Willison's `llm` CLI via Bash

**How it works**: Install `llm` as a CLI tool with `uv tool install llm`. Install provider plugins (`llm install llm-gemini` for Gemini; OpenAI is built-in). Set API keys via `llm keys set openai` and `llm keys set gemini`. Subagents call it via Bash:

```bash
echo "Review this code for bugs:" | cat - code.py | llm -m gpt-4o --no-stream
echo "Review this code for bugs:" | cat - code.py | llm -m gemini-2.5-pro --no-stream
```

The `--no-stream` flag ensures clean output capture. The `-m` flag selects the model. Stdin piping is the primary input mechanism. Output is plain text to stdout.

**Pros**:
- Single tool covers both OpenAI and Gemini (and 100+ other models via plugins)
- Clean non-interactive CLI designed for scripting and piping
- No MCP server process to manage -- just a CLI binary
- Well-maintained by a prolific open-source author (v0.31, April 2026)
- `uv tool install llm` integrates with existing Python tooling
- Works from any subagent via Bash without MCP configuration
- Key management is built in (`llm keys set <provider>`)
- Supports system prompts (`-s`), templates, conversation continuation, and code extraction (`-x`)

**Cons**:
- Adds Python process startup latency per call (~1-2s before API latency)
- No structured output by default (though JSON mode exists via `-o json_object 1`)
- Plugin system requires separate `llm install` calls after the main install
- Less visibility into token usage and costs compared to direct API calls

**Effort estimate**: Small. Install tool, install plugins, set keys. Working in under 10 minutes.

**Dependencies**: `llm` (PyPI), `llm-gemini` plugin

### Option B: Dedicated MCP Servers (one per provider)

**How it works**: Install npm-based MCP servers that expose `askOpenAI` and `gemini-query` tools. Register them in subagent frontmatter via `mcpServers`:

For OpenAI, use `jsindy/mcp-openai` (exposes `askOpenAI` and `listOpenAIModels`):
```yaml
mcpServers:
  - openai:
      type: stdio
      command: npx
      args: ["-y", "mcp-openai"]
      env:
        OPENAI_API_KEY: "${OPENAI_API_KEY}"
```

For Gemini, use `@rlabs-inc/gemini-mcp` (exposes `gemini-query` plus 36 other tools):
```yaml
mcpServers:
  - gemini:
      type: stdio
      command: npx
      args: ["-y", "@rlabs-inc/gemini-mcp"]
      env:
        GEMINI_API_KEY: "${GEMINI_API_KEY}"
        GEMINI_TOOL_PRESET: "minimal"
```

The `GEMINI_TOOL_PRESET=minimal` setting limits the exposed tools to just query and brainstorming, avoiding 37 tools flooding the subagent's context.

**Pros**:
- Native MCP integration -- subagents call model tools the same way they call any other tool
- No shell escaping or stdout parsing concerns
- MCP servers handle retries, rate limiting, and error formatting
- Can be scoped to specific subagents (not polluting the main session)
- The OpenAI MCP server supports fuzzy model matching ("o3" resolves to latest)

**Cons**:
- Requires Node.js/npm (npx) on all machines
- Two separate MCP servers to install, configure, and maintain
- The Gemini MCP server is heavy (37 tools by default; requires preset config to trim)
- MCP server processes consume memory while running
- Community-maintained npm packages -- dependency risk is higher than a well-known CLI
- Each MCP server adds tool descriptions to subagent context, consuming tokens
- The OpenAI MCP server (`jsindy/mcp-openai`) requires cloning and building; no simple npx install

**Effort estimate**: Medium. npm install, env var setup, agent frontmatter configuration, testing MCP tool invocation from subagents.

**Dependencies**: Node.js, npm/npx, `mcp-openai`, `@rlabs-inc/gemini-mcp`

### Option C: Official Provider CLIs via Bash

**How it works**: Install the official OpenAI CLI and Google Gemini CLI. Subagents shell out via Bash.

OpenAI CLI (Go-based):
```bash
# Install: go install 'github.com/openai/openai-cli/cmd/openai@latest'
# Or: brew install openai/tools/openai
# Auth: export OPENAI_API_KEY=...

openai responses create -m gpt-4o -i "Review this code for security issues: $(cat code.py)"
```

Gemini CLI (Node-based):
```bash
# Install: npm install -g @google/gemini-cli
# Auth: export GEMINI_API_KEY=...

gemini -p "Review this code for security issues" -m gemini-2.5-pro < code.py
```

**Pros**:
- Official tools maintained by the providers themselves
- The Gemini CLI has clean headless mode (`-p` flag, `--output-format json`)
- The OpenAI CLI supports multiple output formats (json, yaml, pretty)
- Direct access to latest models as providers add them

**Cons**:
- Two different runtimes: OpenAI CLI needs Go 1.25+, Gemini CLI needs Node.js 20+
- The Gemini CLI is a full agent, not just an API client -- it has file tools, shell access, and its own context. Using it in `-p` mode works but it is overbuilt for this use case
- The OpenAI CLI is relatively new and documentation is sparse for non-interactive use
- No unified interface -- different flags, different output formats, different auth mechanisms
- The Gemini CLI is being replaced by "Antigravity CLI" on June 18, 2026 for unpaid/Google One users (potential churn risk)

**Effort estimate**: Medium. Two separate installs with different runtimes, testing non-interactive modes.

**Dependencies**: Go 1.25+ (OpenAI), Node.js 20+ (Gemini)

### Option D: Direct API calls via curl or thin Python scripts

**How it works**: Subagents use Bash to curl the APIs directly, or call a small Python script installed via `uv tool install`.

```bash
# OpenAI
curl -s https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"Review this code"}]}'

# Gemini
curl -s "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=$GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"contents":[{"parts":[{"text":"Review this code"}]}]}'
```

**Pros**:
- Zero dependencies beyond curl (already installed everywhere)
- Full control over request parameters
- No process overhead, no plugins, no MCP servers

**Cons**:
- JSON construction in bash is fragile and error-prone, especially with code content that contains quotes, newlines, and special characters
- Response parsing requires jq
- No retry logic, no rate limit handling, no timeout management
- No key management -- raw env vars
- Maintaining two different API formats is tedious

**Effort estimate**: Small for a proof of concept, Medium to make robust.

**Dependencies**: curl, jq

## Concerns

### Technical risks

- **Subagent MCP access stability**: The docs describe `mcpServers` support, but multiple GitHub issues reported it as broken historically. This may be version-dependent. Testing on the user's actual Claude Code version is essential before committing to Option B.
- **Gemini CLI lifecycle**: Google announced Antigravity CLI replacing Gemini CLI on June 18, 2026 for some tiers. This creates churn risk for Option C.

### Complexity risks

- **Two providers = two auth flows**: OpenAI requires prepaid credits at platform.openai.com. Gemini offers a free tier at aistudio.google.com but Pro models are paid. Managing two separate billing accounts adds ongoing overhead.
- **Token cost visibility**: External model calls are invisible to Claude Code's token tracking. You need separate cost monitoring at each provider's dashboard.

### Maintenance risks

- **Community MCP servers**: The OpenAI and Gemini MCP servers (Option B) are community-maintained npm packages. If they go unmaintained, you inherit the maintenance burden or need to switch approaches.
- **`llm` plugin compatibility**: When providers change their APIs, the `llm` plugins need updates. Simon Willison has been responsive historically, but there is a dependency chain.

## Model Availability and Pricing

### OpenAI (requires separate API billing at platform.openai.com)

| Model | Input $/M tokens | Output $/M tokens | Notes |
|-------|------------------|--------------------|-------|
| GPT-4o | ~$2.50 | ~$10.00 | Multimodal, good general purpose |
| o3 | $2.00 | $8.00 | Reasoning model, replaced o1 |
| o4-mini | $1.10 | $4.40 | Cost-effective reasoning |
| GPT-4.1 nano | $0.10 | $0.40 | Cheapest, good for simple tasks |
| GPT-5.4 | $2.50 | $15.00 | Latest generation |

Minimum top-up: $5. Credits expire after 1 year. Auto-recharge available.

### Google Gemini (free tier available at aistudio.google.com)

| Model | Input $/M tokens | Output $/M tokens | Free tier |
|-------|------------------|--------------------|-----------|
| Gemini 2.5 Pro | $1.25 | $10.00 | 50 RPD |
| Gemini 2.5 Flash | $0.30 | $2.50 | 1,500 RPD |
| Gemini 2.5 Flash-Lite | $0.10 | $0.40 | Yes |
| Gemini 3 Flash Preview | Free tier pricing TBD | TBD | Yes |

No credit card required for free tier. API key from aistudio.google.com.

## Open Questions

- [ ] Does `mcpServers` inline definition in subagent frontmatter work reliably on the user's current Claude Code version? The docs say yes (v2.1.153+), but earlier versions had bugs. Check `claude --version`.
- [ ] Which specific use cases justify the API cost? Cross-model review of every commit would get expensive. Selective use on high-stakes changes is more practical.
- [ ] Should external model calls be opt-in per invocation (user triggers explicitly) or automatic (built into review/challenge workflows)?
- [ ] For arena-style implementations, how will outputs be compared? The orchestrator needs a diff/evaluation step after collecting outputs from multiple models.

## Recommendation

**Start with Option A (`llm` CLI via Bash)**. It is the simplest path that covers both providers with a single tool, works from any subagent without MCP configuration, and installs in minutes with `uv`.

The reasoning:

1. **Bash works everywhere.** Every subagent has Bash access. No MCP version compatibility concerns, no process management, no npm dependency. This is the approach with the fewest moving parts.

2. **Unified interface.** One tool, one key management system, one output format for both OpenAI and Gemini. You write `llm -m gpt-4o "prompt"` or `llm -m gemini-2.5-pro "prompt"` and get text back. The subagent prompt stays provider-agnostic.

3. **Escape hatch to MCP later.** If you find that Bash-based calls have friction (output parsing, latency, error handling), upgrading to MCP servers is a non-breaking change. You would add `mcpServers` to the relevant agent frontmatter and update the prompt to use the MCP tool instead of Bash. The reverse migration is harder.

4. **Cost control.** Starting with `llm` and manual invocation lets you gauge actual API costs before wiring external models into automated workflows. Gemini's free tier (2.5 Flash at 1,500 RPD) is generous enough for experimentation. OpenAI requires a $5 minimum prepaid deposit.

**What NOT to do**: Do not start with the full RLabs Gemini MCP server (37 tools). It is overbuilt for "ask a model a question" and wastes subagent context on tool descriptions you will not use.

### Suggested next steps

1. **Set up API keys.** Go to aistudio.google.com to get a free Gemini API key. Go to platform.openai.com to create an API account and add $5-10 in credits. Store keys in environment variables (`OPENAI_API_KEY`, `LLM_GEMINI_KEY`).
2. **Install `llm`.** Run `uv tool install llm && llm install llm-gemini && llm keys set openai && llm keys set gemini`. Test with `llm -m gemini-2.5-flash "hello"` and `llm -m gpt-4o "hello"`.
3. **Write a proof-of-concept agent.** Create a simple `cross-model-reviewer.md` subagent that takes code via its prompt and shells out to `llm` to get a second opinion. Test it on a real diff.
4. **Decide on integration depth.** After the proof of concept works, decide whether to wire external models into existing skills (challenge, code-review) or keep them as a separate explicit workflow.

## Sources

- [Claude Code subagent docs -- mcpServers support](https://code.claude.com/docs/en/sub-agents)
- [Simon Willison's llm CLI](https://github.com/simonw/llm)
- [llm-gemini plugin](https://github.com/simonw/llm-gemini)
- [llm CLI usage docs](https://llm.datasette.io/en/stable/usage.html)
- [jsindy/mcp-openai MCP server](https://github.com/jsindy/mcp-openai)
- [RLabs gemini-mcp server](https://github.com/RLabs-Inc/gemini-mcp)
- [Gemini CLI headless mode](https://geminicli.com/docs/cli/headless/)
- [Gemini CLI authentication](https://geminicli.com/docs/get-started/authentication/)
- [OpenAI CLI docs](https://developers.openai.com/api/docs/libraries/openai-cli)
- [OpenAI API pricing](https://openai.com/api/pricing/)
- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Claude Forge multi-model workflows](https://medium.com/tr-labs-ml-engineering-blog/claude-forge-plan-supervised-multi-model-workflows-for-claude-code-725b5064241b)
- [Claude Code subagent MCP feature request #34935](https://github.com/anthropics/claude-code/issues/34935)
- [Gemini API free tier details](https://ai.google.dev/gemini-api/docs/billing)
- [OpenAI API billing setup](https://help.openai.com/en/articles/8264644-how-can-i-set-up-prepaid-billing)
