---
topic: "lightweight long-context local embedding models for ccrecall"
date: 2026-06-18
status: Draft
---

# Prior Art: Lightweight Long-Context Local Embedding Models (for ccrecall)

> **Catalog-verified correction (2026-06-18).** This brief was drafted from vendor blogs and
> aggregators ("_URLs were not live-verified_"). The fastembed catalog has since been queried
> directly (`TextEmbedding.list_supported_models()` on the installed package). It **refutes the
> central "Relevance to Us" premise** that viable long-context models are all ≈ bge-m3's size —
> see [Catalog Verification](#catalog-verification-verified-against-installed-fastembed) below,
> which supersedes the original Relevance/Recommendation framing.

## The Problem

ccrecall does local semantic search over Claude Code conversation-branch summaries using
**bge-m3** (1024-dim, ~558MB int8 ONNX, 8192-ctx). bge-m3 was chosen only because another
tool (memsearch) had already downloaded it — a rationale that evaporates now that ccrecall is
a standalone plugin others install (a fresh user has no such cache). Question: is there a
lighter or better model that preserves retrieval quality?

## How We Do It Today (codebase + real data)

Model constants are centralized in `embeddings.py:27-29` (`EMBEDDING_MODEL`,
`EMBEDDING_VERSION`, `EMBEDDING_DIM`). The model is loaded from the **HF cache**
(`gpahal/bge-m3-onnx-int8`) by scanning `~/.cache/huggingface/hub/` — i.e. it assumes the
weights are already present, which is true on the author's box but **not on a fresh install**.
A version-gated backfill (`backfill_embeddings.py`) cleanly re-embeds when `EMBEDDING_VERSION`
bumps. The embedded unit is the branch `context_summary`. **Dimension is baked into the
sqlite-vec DDL (`db.py:311`) with no auto-migration** — a dim change needs a manual schema
migration + full re-embed.

**Empirical reality of the embedded text (live DB, 2017 active summaries):** median ~560
tokens, p90 ~2040, p99 ~2620, max ~3050 (chars/4). **52% exceed 512 tokens; ~10% exceed 2048;
none exceed ~3100.** Zero `-1` (overflow-error) rows — bge-m3 handles the full distribution
today. **Conclusion: the real context requirement is ≥4k tokens (not 8192), and short-context
(512-token) models are disqualified — they would truncate the majority.**

## Patterns Found

### Pattern 1: snowflake-arctic-embed-l-v2.0 (direct bge-m3 successor)
**Used by**: Local-RAG benchmarks call it the "long-document specialist" (PromptQuorum); Snowflake prod.
**How it works**: 568M params, 1024-dim, 8192-ctx (RoPE), same xlm-roberta / bge-m3-retromae base as bge-m3; Matryoshka→256 + 4-bit quant; ONNX+Safetensors; Apache-2.0; 74 languages.
**Strengths**: Same dim/ctx as bge-m3 → **zero sqlite-vec schema change**; vendor+benchmark claims it beats bge-m3 on MTEB retrieval and CLEF; Matryoshka headroom.
**Weaknesses**: Footprint ≈ bge-m3 (no download win); **not in fastembed** → manual `optimum`/onnxruntime export (same install pain as today).
**Example**: https://huggingface.co/Snowflake/snowflake-arctic-embed-l-v2.0

### Pattern 2: nomic-embed-text-v1.5 (long-context, small, fastembed-native)
**Used by**: Ollama default embedder, Obsidian Smart Connections, common LlamaIndex/LangChain local default.
**How it works**: 137M params, 768-dim, 8192-ctx, Matryoshka {768…64}, ONNX ships; fastembed ~0.52GB.
**Strengths**: **fastembed one-line, torch-free, self-downloading** (solves the fresh-install problem); 768-dim halves vector storage; real 8192 ctx; Matryoshka lever.
**Weaknesses**: Requires `search_document:`/`search_query:` prefixes (silent-regression trap if missed); MTEB mean ~62 < bge-m3 ~68 (retrieval gap narrower than mean); 768-dim needs a schema migration.
**Example**: https://huggingface.co/nomic-ai/nomic-embed-text-v1.5

### Pattern 3: snowflake-arctic-embed-m / m-long (smallest credible long-context)
**Used by**: Snowflake; fastembed lists arctic-m at 0.43GB.
**How it works**: 137M, 768-dim, 2048 native / 8192 via RoPE; arctic-m-v1.5 adds Matryoshka→256.
**Strengths**: Smallest footprint of the viable set, fastembed-supported (arctic-m), strong retrieval-per-MB.
**Weaknesses**: m-long (RoPE) variant differs from the fastembed-listed arctic-m; English-focused; older than v2.0.
**Example**: https://huggingface.co/Snowflake/snowflake-arctic-embed-m-long

### Pattern 4: gte-large-en-v1.5 (clean long-context English baseline)
**Used by**: Alibaba; common RAG baseline.
**How it works**: 409M, 1024-dim, 8192-ctx, English-only, no native Matryoshka. (gte-base-en-v1.5 = 768-dim/137M, fastembed-supported.)
**Strengths**: 1024-dim (no schema change), true 8192 ctx, no prefix gymnastics.
**Weaknesses**: English-only; retrieval ≈ bge-class, not clearly better; no Matryoshka.
**Example**: https://huggingface.co/Alibaba-NLP/gte-large-en-v1.5

### Pattern 5: jina-embeddings-v3 (quality ceiling, but heavy + license risk)
**How it works**: 570M, 1024-dim, 8192-ctx, Matryoshka→32, multilingual.
**Strengths**: Highest measured local-RAG retrieval in one benchmark.
**Weaknesses**: ~2.0GB; **CC-BY-NC (non-commercial)** — a real risk for an installable plugin; not in fastembed.
**Example**: https://jina.ai/models/jina-embeddings-v3/

## Anti-Patterns

- **512-token model for ~3k-token summaries** — mxbai-embed-large, bge-large-en-v1.5 (both 512), all-MiniLM (256) truncate; confirmed here that 52% of summaries exceed 512 tokens.
- **Pick by MTEB *mean* rank** — leaderboard top (Qwen3-Embedding, Nemotron-8B) is multi-GB/torch-only; mean under-weights retrieval and bge-m3's mean partly reflects MIRACL/Wikipedia overfit.
- **Assume "HF has ONNX" == "fastembed-easy"** — arctic-l-v2.0, jina-v3, bge-m3 all need manual export; only nomic-v1.5/arctic-m/gte-base/bge-* get one-line inference.
- **Ignore task prefixes** (nomic/e5) — silent retrieval degradation a smoke test won't catch.

## Emerging Trends

- **Matryoshka (MRL)** as the footprint lever (nomic, arctic m/l, jina, EmbeddingGemma) — store 256/512 dims, widen later without re-embedding the model.
- **Sub-500M on-device class** (EmbeddingGemma-308M, nomic-137M, arctic-m-137M) closing the MTEB gap — but **EmbeddingGemma caps at 2048 ctx**, which truncates ~10% of these summaries.

## Catalog Verification (verified against installed fastembed)

Queried `TextEmbedding.list_supported_models()` on the installed fastembed package (not a blog).
Filtering to models that clear the real ≥4k-context requirement:

| Model | Dim | Size | Context | In fastembed? |
|---|---|---|---|---|
| `jinaai/jina-embeddings-v2-small-en` | 512 | **0.12 GB** | 8192 | yes |
| `nomic-ai/nomic-embed-text-v1.5-Q` (int8) | 768 | **0.13 GB** | 8192 | yes |
| `nomic-ai/nomic-embed-text-v1.5` | 768 | 0.52 GB | 8192 | yes |
| `jinaai/jina-embeddings-v2-base-en` | 768 | 0.52 GB | 8192 | yes |
| `snowflake/arctic-embed-m-long` | 768 | 0.54 GB | 2048 | yes (excluded: truncates ~10%) |
| `snowflake/arctic-embed-l-v2.0` | 1024 | ~0.57 GB | 8192 | **no** (manual export) |
| `Alibaba-NLP/gte-large-en-v1.5` | 1024 | ~1.2 GB | 8192 | **no** |
| bge-m3 (`gpahal/bge-m3-onnx-int8`) | 1024 | 0.558 GB | 8192 | **no** (manual export) |

**Two corrections to the original brief:**

1. **The "all ~0.4–0.6 GB" premise is false.** Two 8192-context models ship at **~0.12–0.13 GB —
   roughly a quarter of bge-m3.** `jina-v2-small-en` also halves the vector dim (512 vs 1024),
   cutting sqlite-vec storage in half. The download win is real: **558 MB → ~125 MB.**
2. **The brief's "quality-first" pick `arctic-embed-l-v2.0` is _not_ in fastembed** (only the
   512-ctx v1 `arctic-embed-l` is). So it carries the same manual-export install pain as bge-m3 —
   it cannot be the fastembed-native bet. If we commit to the fastembed strategy (turnkey
   auto-download, no PyTorch), the realistic field is the jina/nomic family above.

Tradeoffs the eval must settle: the two lightweight models are English-only (bge-m3 is
multilingual — a non-loss for English Claude Code summaries) and lower generic MTEB, but the
corpus is short (median ~560 tokens), English, technical. nomic needs `search_document:` /
`search_query:` prefixes; any dim change from 1024 touches the sqlite-vec DDL (`db.py:311`).

## Relevance to Us

The framing "lighter model, same benefit" slightly misfires: **the viable long-context models
are all ~0.4–0.6GB, ≈ bge-m3's footprint — so switching buys little download savings.** The
real levers are: (1) **install ergonomics** — bge-m3 isn't in fastembed and the current code
scans the HF cache for a pre-exported model that a fresh user won't have; a fastembed-native
model (nomic-v1.5, arctic-m) gives one-line, torch-free, self-downloading inference, which is
the single biggest *product* win for a published plugin; (2) **retrieval quality** — only
arctic-l-v2.0 plausibly beats bge-m3, on vendor/benchmark claims that must be verified; (3)
**storage** — 768-dim halves vectors, but at ~2000 branches (~8MB) this is negligible.

Dimension choice splits the candidates by migration cost: **1024-dim (arctic-l-v2.0, gte-large)
= drop-in** (bump version, re-embed); **768-dim (nomic, arctic-m) = schema migration + re-embed**.

## Recommendation

> **Superseded by catalog verification (2026-06-18).** The fastembed-native shortlist below
> replaces the original arctic-l-v2.0 + nomic pairing, because arctic-l-v2.0 is not in fastembed.
> Harness shortlist (recall@k / MRR / nDCG over the real corpus, bge-m3 as baseline-to-beat):
> 1. **`jina-embeddings-v2-small-en`** (0.12 GB, 512d) — aggressive lightweight bet (¼ size, ½ vectors).
> 2. **`nomic-embed-text-v1.5-Q`** (0.13 GB, 768d int8) — strong-retrieval lightweight bet (needs prefixes).
> 3. **`nomic-embed-text-v1.5`** (0.52 GB, 768d) — safe same-size fallback.
> 4. **bge-m3** — baseline.
>
> The decision logic is unchanged: install ergonomics (fastembed auto-download, no PyTorch) is
> the headline win; the harness only has to show a candidate doesn't *lose materially* on
> retrieval over our own data. Original reasoning retained below for the trail.

Run a **blind A/B** with bge-m3 as the control, testing the two competing theories:
- **arctic-embed-l-v2.0** — the *quality-first* bet (1024-dim drop-in, claims to beat bge-m3).
- **nomic-embed-text-v1.5** — the *install-first* bet (fastembed-native solves the fresh-install
  problem; 768-dim; accept the prefix requirement and a schema migration).

Optional thirds: **arctic-embed-m-long** (can we go smaller?) and **gte-large-en-v1.5** (clean
1024-dim English baseline). **Drop jina-v3** (2GB + non-commercial license).

The honest headline: the strongest reason to move off bge-m3 is **fresh-install ergonomics**
(fastembed), not footprint — so if the eval shows nomic ≈ bge-m3 on retrieval, the install win
likely settles it. Treat all "beats bge-m3" quality claims as hypotheses for the eval, since
they come from vendor blogs and aggregators, not raw MTEB.

## Sources

### Reference implementations / model cards
- https://huggingface.co/Snowflake/snowflake-arctic-embed-l-v2.0 — direct bge-m3 successor
- https://huggingface.co/nomic-ai/nomic-embed-text-v1.5 — long-context small, fastembed-native
- https://huggingface.co/Snowflake/snowflake-arctic-embed-m-long — smallest long-context
- https://huggingface.co/Alibaba-NLP/gte-large-en-v1.5 — long-context English baseline
- https://jina.ai/models/jina-embeddings-v3/ — quality ceiling (license risk)
- https://qdrant.github.io/fastembed/examples/Supported_Models/ — which models are fastembed-native

### Blog posts & benchmarks
- https://www.promptquorum.com/power-local-llm/best-embedding-models-local-rag-2026 — local-RAG benchmark; crowns arctic-l-v2.0 long-doc
- https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models — 2026 field survey; 512-ctx truncation evidence
- https://milvus.io/blog/choose-embedding-model-rag-2026.md — 10-model RAG comparison
- https://ollama.com/library/nomic-embed-text — nomic as local-first default
- https://www.morphllm.com/ollama-embedding-models — MTEB/VRAM/dim local benchmark

### Documentation & standards
- https://arxiv.org/pdf/2402.01613 — Nomic Embed (long-context training)
- https://arxiv.org/pdf/2509.20354 — EmbeddingGemma (2048-ctx cap)
- https://huggingface.co/mteb — MTEB leaderboard
- https://www.snowflake.com/en/engineering-blog/snowflake-arctic-embed-2-multilingual/ — arctic v2.0 claims

_URLs were not live-verified._
