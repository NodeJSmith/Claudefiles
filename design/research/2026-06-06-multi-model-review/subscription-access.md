---
proposal: "Use existing ChatGPT Plus and Google One AI Premium consumer subscriptions for programmatic/CLI access to OpenAI and Gemini models, avoiding separate API billing."
date: 2026-06-06
status: Draft
flexibility: Exploring
motivation: "Already paying $40/month for two consumer AI subscriptions. Wants to use those subscriptions for programmatic multi-model review calls from scripts/CLI tools rather than adding separate API billing."
constraints: "Must use existing consumer subscriptions, not separate API credit accounts. Use case is ~5-15 cross-model review calls per day, each ~2-5K input tokens + ~1-2K output tokens."
non-goals: "Not looking to replace Claude Code. Not building a product. Just personal CLI scripting and code review tooling."
depth: deep
---

# Research Brief: Programmatic Access via Consumer AI Subscriptions

**Initiated by**: Can I use my ChatGPT Plus and Google One AI Premium subscriptions from scripts and CLI tools instead of paying for separate API accounts?

## Context

### What prompted this

Two consumer AI subscriptions are already being paid for monthly ($20/month each). The question is whether those subscriptions can double as programmatic access for lightweight scripting -- specifically cross-model code review calls. The alternative is paying for API credits on top of the subscriptions, which feels like paying twice.

### The landscape as of June 2026

Both OpenAI and Google maintain a hard separation between consumer subscriptions and developer API access. This is a deliberate business decision, not a technical limitation. However, recent developments have created legitimate and semi-legitimate bridges between the two worlds, with very different risk profiles on each side.

## Findings

### 1. OpenAI / ChatGPT Plus: The Codex Backdoor

**Status: Viable via llm-openai-via-codex, with caveats**

ChatGPT Plus does NOT include any API credits or direct API access. The consumer subscription and the API platform are entirely separate billing systems. This has not changed in 2025 or 2026.

However, OpenAI's **Codex CLI** (their official coding agent) authenticates via ChatGPT subscription, not API keys. This creates a programmatic bridge:

1. Install the Codex CLI and authenticate with your ChatGPT Plus login
2. Codex stores credentials in `~/.codex/auth.json`
3. Simon Willison's **[llm-openai-via-codex](https://github.com/simonw/llm-openai-via-codex)** plugin reads those credentials and routes arbitrary `llm` prompts through the Codex backend (`chatgpt.com/backend-api/codex`)

**OpenAI's stated position is supportive.** Romain Huet from OpenAI said publicly: "We want people to be able to use Codex, and their ChatGPT subscription, wherever they like!" This is not a formal guarantee, but it is a public statement from an OpenAI employee, not a wink-and-nod from the community.

**Available models** (via Codex/subscription): GPT-5.5 (flagship), GPT-5.4, GPT-5.4-mini, GPT-5.3-Codex. The older GPT-4o and GPT-4.1 models are being retired from ChatGPT, so they may not be available through this path long-term.

**Rate limits**: ChatGPT Plus gets 10-60 cloud tasks per 5-hour rolling window. "Cloud tasks" in Codex are multi-step agent runs, not raw API calls. The llm plugin makes simpler calls, so the exact mapping is unclear. For 5-15 review calls per day, this should be well within limits.

**Risk level: LOW-MEDIUM.** The Codex CLI itself is official. The plugin uses the same auth and endpoint the CLI uses. OpenAI has publicly endorsed the usage pattern. The risk is that the backend endpoint is undocumented and can change without notice, breaking the plugin.

### 2. Google / Gemini: Two Paths, One Minefield

#### Path A: Gemini CLI with Google Account Login (Official, sunsetting June 18)

**Status: Works today, being killed in 12 days**

Gemini CLI supports Google account login as a first-class auth method. If you log in with an account that has Google AI Pro (formerly Gemini Advanced), you get **1,500 requests/day** at no additional cost. The free tier gets 1,000/day.

The CLI has a headless mode (`-p` / `--prompt` flag) that works for scripting -- pipe stdin, get stdout, supports JSON output format. Google account credentials are cached after initial browser login, so subsequent headless invocations reuse them.

**The catch**: Google announced at I/O 2026 that Gemini CLI is being **replaced by Antigravity CLI on June 18, 2026** -- 12 days from now. After that date, Gemini CLI stops serving requests for individual subscribers.

Antigravity CLI is the replacement, but it has a critical bug: the `-p` (print/headless) flag **silently drops stdout when run from a non-TTY context** (pipes, subprocess, redirects). This means it cannot be used programmatically right now. The issue is tracked at [google-antigravity/antigravity-cli#76](https://github.com/google-antigravity/antigravity-cli/issues/76).

**Risk level for Gemini CLI: DEAD END.** Do not invest in this path -- it has 12 days left.

**Risk level for Antigravity CLI: BLOCKED.** The headless piping bug makes it unusable for scripting until fixed. Monitor the issue.

#### Path B: llm-gemini-code-assist Plugin (Community, risky)

**Status: Works but carries real account suspension risk**

The [llm-gemini-code-assist](https://pypi.org/project/llm-gemini-code-assist/) plugin uses the Gemini CLI's OAuth client ID to authenticate via Google account and access Gemini models through the Code Assist API. It uses your subscription quota (not API billing).

**Rate limit**: ~3 requests/minute through the Code Assist API. This is tight for batch usage but fine for 5-15 calls spread across a day.

**The danger**: In February 2026, Google mass-banned users of OpenClaw (a similar tool that proxied Google subscription OAuth tokens). Bans were **permanent, with no refunds for prepaid annual plans, no warnings, and no appeals**. Some users lost access to Gmail and Workspace tied to the same Google account. Google's updated ToS (February 18, 2026) explicitly prohibits using Gemini/Antigravity with third-party products.

The `llm-gemini-code-assist` plugin uses the same OAuth approach that got OpenClaw users banned. Google has not specifically targeted this plugin (it is much smaller and lower-profile), but the enforcement precedent is harsh.

**Risk level: HIGH.** If Google's automated systems flag the traffic, you could lose your entire Google account, not just the AI subscription.

### 3. Simon Willison's `llm` Tool

The `llm` CLI is the best integration point for both paths:

| Plugin | Auth method | Subscription-based? | Status |
|--------|------------|---------------------|--------|
| `llm-openai-via-codex` | Codex CLI auth.json | Yes (ChatGPT Plus) | Working, semi-official |
| `llm-gemini-code-assist` | Gemini CLI OAuth | Yes (Google AI Pro) | Working, risky |
| `llm-gemini` (standard) | API key | No (separate billing) | Stable, recommended |

The `llm` tool does NOT natively support OAuth/browser auth for any provider. All subscription-based access comes through community plugins that borrow credentials from the providers' own CLI tools.

### 4. Cost Comparison: Subscription vs. API

**Your stated usage**: ~5-15 calls/day, ~2-5K input tokens, ~1-2K output tokens per call.

**Worst-case daily usage**: 15 calls x (5K input + 2K output) = 75K input + 30K output tokens/day.
**Monthly (30 days)**: 2.25M input + 900K output tokens/month.

| Model | Input cost/1M | Output cost/1M | Monthly input | Monthly output | **Total/month** |
|-------|--------------|----------------|---------------|----------------|-----------------|
| GPT-4o | $2.50 | $10.00 | $5.63 | $9.00 | **$14.63** |
| GPT-5.5 | (subscription only, no API pricing yet) | -- | -- | -- | **N/A** |
| GPT-5.4-mini | ~$0.15 | ~$0.60 | $0.34 | $0.54 | **$0.88** |
| Gemini 2.5 Pro | $1.25 | $10.00 | $2.81 | $9.00 | **$11.81** |
| Gemini 2.5 Flash | $0.30 | $2.50 | $0.68 | $2.25 | **$2.93** |

**Key insight**: At this usage level, API costs range from **$0.88 to $14.63/month** depending on model choice. This is well below what either subscription costs ($20/month each).

**Practical interpretation**: If you use Gemini 2.5 Flash ($2.93/month) for reviews and GPT-4o ($14.63/month) for a second opinion, the combined API cost is ~$17.56/month. That is less than one subscription. If you use Flash + GPT-5.4-mini, it drops to ~$3.81/month.

The subscriptions are not cost-effective for this use case. They provide value for interactive chat, deep research, and Workspace integration -- not for lightweight programmatic calls.

## Options

### Option A: Use Codex auth for OpenAI + Gemini API key for Google

**How it works**: Install Codex CLI, authenticate with ChatGPT Plus credentials. Install `llm-openai-via-codex` to route OpenAI calls through your subscription. For Google, use a standard Gemini API key with the free tier (or pay-as-you-go) via `llm-gemini`.

This is the pragmatic hybrid: use the subscription bridge where it is safe (OpenAI, with their public endorsement) and use cheap API access where the subscription path is dangerous (Google).

**Pros**:
- OpenAI side is semi-officially endorsed
- Google side uses the stable, recommended API path
- Gemini free tier gives 100 requests/day with 2.5 Flash at no cost
- Single tool (`llm`) for both providers
- No risk to your Google account

**Cons**:
- OpenAI's Codex backend is undocumented; the plugin can break without notice
- Gemini free tier rate limits may be tight (15 RPM for Flash free tier)
- You are still paying for Google AI Pro without using it programmatically

**Effort estimate**: Small -- install two plugins, authenticate once with each provider.

**Dependencies**: `llm`, `llm-openai-via-codex`, `llm-gemini`, Codex CLI

### Option B: Pure API keys for both providers

**How it works**: Get API keys from both OpenAI and Google. Use `llm` with `llm-openai` and `llm-gemini` plugins. Pay per token.

**Pros**:
- Most stable and supported path
- No risk of account bans or auth breakage
- Full model selection on both sides
- Rate limits are generous on paid tiers

**Cons**:
- Adds API billing on top of existing subscriptions
- At your usage level, this costs $3-18/month depending on model choices
- Feels like paying twice (but the math says it is cheaper than the subscriptions)

**Effort estimate**: Small -- create accounts, set API keys, install plugins.

**Dependencies**: `llm`, `llm-openai`, `llm-gemini`

### Option C: Drop the subscriptions, go API-only

**How it works**: Cancel ChatGPT Plus and Google AI Pro. Use API keys for programmatic access. Use free tiers of ChatGPT and Gemini for occasional interactive chat.

**Pros**:
- Saves $40/month in subscriptions
- API costs at your usage level are $3-18/month
- Net savings of $22-37/month
- Cleanest, most reliable setup

**Cons**:
- Lose ChatGPT Plus benefits (higher chat limits, priority access, early model access)
- Lose Google AI Pro benefits (Gemini Advanced in Workspace, 2TB storage, Deep Research)
- Lose access to subscription-only models (GPT-5.5 is currently subscription-only)
- The 2TB Google One storage might be in use

**Effort estimate**: Small technically, but requires evaluating which subscription benefits you actually use beyond programmatic access.

## Concerns

### Technical risks

- **Codex backend stability**: The `llm-openai-via-codex` plugin hits an undocumented endpoint. OpenAI has endorsed the usage pattern but not the endpoint. It could change or be rate-limited differently without notice.
- **Antigravity CLI headless bug**: The replacement for Gemini CLI cannot pipe output in non-TTY contexts. Until this is fixed, Google's subscription-based CLI path is unusable for scripting. No timeline for a fix.
- **revChatGPT and similar reverse proxies**: These are dead ends. OpenAI actively fights reverse-engineered clients, the projects are abandoned or unreliable, and using them risks account bans.

### Account risks

- **Google OAuth in third-party tools**: Google has demonstrated zero-tolerance enforcement. The February 2026 OpenClaw bans affected paying subscribers with no recourse. Using `llm-gemini-code-assist` or similar OAuth-proxying tools carries a real risk of losing your Google account. Do not use this path.
- **OpenAI is more permissive**: OpenAI's public statements support using Codex auth from third-party tools. No known enforcement actions against `llm-openai-via-codex` users. The risk profile is meaningfully different from Google's.

### The subscription value question

The cost analysis reveals an uncomfortable truth: at your usage level, API access costs $3-18/month. Both subscriptions cost $20/month each. Unless you are using the subscriptions heavily for interactive chat, Workspace integration, or the 2TB storage, the subscriptions themselves may not be the best value for programmatic access.

## Open Questions

- [ ] How heavily do you use ChatGPT Plus for interactive chat? If rarely, Option C (drop subscriptions) saves the most money.
- [ ] Is the 2TB Google One storage actively in use? That alone might justify the Google subscription regardless of AI access.
- [ ] Do you need GPT-5.5 specifically? It is currently subscription-only. If GPT-5.4 or GPT-4o is sufficient for reviews, API access covers it.
- [ ] How important is Gemini Advanced in Workspace (Gmail, Docs, Sheets)? That is a Google AI Pro benefit that has no API equivalent.

## Recommendation

**Option A (Codex auth for OpenAI + Gemini API key for Google) is the practical starting point.** It extracts programmatic value from the ChatGPT Plus subscription you are already paying for, uses the safe API path for Google, and can be set up in under an hour.

But the real finding here is the cost math. At 5-15 review calls per day, API access is cheap -- $3-18/month depending on models. The subscriptions are not a cost-effective way to get programmatic access; they are paying for interactive chat, early model access, and bundled services. If the interactive benefits are not being used, dropping one or both subscriptions and going API-only (Option C) saves $22-37/month while being the most stable technical path.

### Suggested next steps

1. **Install `llm` + `llm-openai-via-codex`** now. Authenticate via Codex CLI. Test a few review calls against your codebase. This validates the OpenAI subscription path with near-zero risk.
2. **Get a Gemini API key** from Google AI Studio. The free tier (100 req/day for 2.5 Flash) may be sufficient for your usage. Install `llm-gemini` and test.
3. **Evaluate subscription value**: Separately from the programmatic access question, audit whether the $40/month in subscriptions is justified by the interactive/Workspace benefits. The programmatic use case does not justify them.

## Sources

- [ChatGPT Plus API access guide (AIonX)](https://aionx.co/chatgpt-reviews/chatgpt-plus-api-access/)
- [OpenAI API Pricing](https://openai.com/api/pricing/)
- [Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini CLI Quotas and Pricing](https://geminicli.com/docs/resources/quota-and-pricing/)
- [Gemini CLI Authentication Setup](https://google-gemini.github.io/gemini-cli/docs/get-started/authentication.html)
- [Gemini CLI Headless Mode](https://google-gemini.github.io/gemini-cli/docs/cli/headless.html)
- [Simon Willison: GPT-5.5 via Codex](https://simonwillison.net/2026/Apr/23/gpt-5-5/)
- [llm-openai-via-codex (GitHub)](https://github.com/simonw/llm-openai-via-codex)
- [llm-gemini-code-assist (PyPI)](https://pypi.org/project/llm-gemini-code-assist/)
- [llm-gemini (GitHub)](https://github.com/simonw/llm-gemini)
- [Google bans OpenClaw users (WinBuzzer)](https://winbuzzer.com/2026/02/23/google-bans-ai-subscribers-openclaw-no-refunds-xcxwbn/)
- [Google restricts AI Ultra accounts over OpenClaw OAuth (Implicator)](https://www.implicator.ai/google-restricts-ai-ultra-subscribers-over-openclaw-oauth-days-after-anthropic-ban/)
- [Transitioning Gemini CLI to Antigravity CLI (Google Developers Blog)](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/)
- [Antigravity CLI stdout bug (GitHub #76)](https://github.com/google-antigravity/antigravity-cli/issues/76)
- [Codex Pricing](https://developers.openai.com/codex/pricing)
- [Codex Models](https://developers.openai.com/codex/models)
- [Google One AI Plans](https://one.google.com/about/google-ai-plans/)
- [Gemini API Rate Limits](https://ai.google.dev/gemini-api/docs/rate-limits)
