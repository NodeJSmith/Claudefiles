# Prior Art: Lightweight, Long-Context, Local-ONNX Text Embedding Models (2025–2026)

Research target: replace **bge-m3** (1024-dim, ~558MB int8 ONNX, 8192-token ctx) for local
semantic search over conversation-branch summaries (~3–4k tokens) in sqlite-vec.
Decision axes: download footprint, retrieval quality, context length (must handle 3–4k tokens),
embedding dimension (sqlite-vec storage), ease of local ONNX inference. Latency not a concern.

## Sources Found

### The Best Open-Source Embedding Models in 2026 (BentoML)
- **URL**: https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models
- **Type**: blog post / survey
- **Key takeaway**: Surveys the 2026 open-source field (Qwen3, BGE, GTE, Arctic, Nomic, EmbeddingGemma). Frames the size-vs-quality tradeoff for self-hosted embedding.
- **Relevance**: Establishes the candidate set and which models are considered "lightweight" in 2026.

### Best Embedding Models for Local RAG in 2026 (Tested on Real Documents) — PromptQuorum
- **URL**: https://www.promptquorum.com/power-local-llm/best-embedding-models-local-rag-2026
- **Type**: blog post / benchmark (6 models on real docs)
- **Key takeaway**: For local-first RAG, recommends **jina-embeddings-v3** overall (1024-dim, Matryoshka 768/512/256, ~2.0GB) and **nomic-embed-text-v2** as the CPU throughput champion (768-dim, 580 chunks/sec). Names **snowflake-arctic-embed-l-v2.0** explicitly the "long-document specialist" (1024-dim, native 8192-token chunks). bge-large-en-v1.5 best English-only (no Matryoshka).
- **Relevance**: Directly on-point — a local-first benchmark that crowns arctic-embed-l-v2.0 for the long-document case this tool needs.

### Best Embedding Model for RAG 2026: 10 Models Compared (Milvus)
- **URL**: https://milvus.io/blog/choose-embedding-model-rag-2026.md
- **Type**: blog post / comparison
- **Key takeaway**: Compares 10 models across quality/size/context for RAG selection.
- **Relevance**: Cross-check on context-length and dimension claims.

### EmbeddingGemma: Powerful and Lightweight Text Representations (arXiv 2509.20354)
- **URL**: https://arxiv.org/pdf/2509.20354
- **Type**: paper
- **Key takeaway**: Google's EmbeddingGemma (308M params, 768-dim, Matryoshka to 128) is best-in-class MTEB **among models under 500M params**, but context caps at **2048 tokens**.
- **Relevance**: Strong small model — but 2048-token ceiling is a hard disqualifier for 3–4k-token summaries (would truncate).

### Introducing EmbeddingGemma (Google Developers Blog) / MarkTechPost coverage
- **URL**: https://developers.googleblog.com/en/introducing-embeddinggemma/
- **URL**: https://www.marktechpost.com/2025/09/04/google-ai-releases-embeddinggemma-a-308m-parameter-on-device-embedding-model-with-state-of-the-art-mteb-results/
- **Type**: vendor blog / news
- **Key takeaway**: EmbeddingGemma MTEB mean ~61.15 vs bge-m3 ~68.37; download ~622MB vs bge-m3 ~1.2GB (full precision). 768-dim, 2048-token max sequence, Matryoshka to 512/256/128.
- **Relevance**: Footprint/quality data point; confirms the 2048 context ceiling.

### Nomic Embed: Training a Reproducible Long Context Text Embedder (arXiv 2402.01613)
- **URL**: https://arxiv.org/pdf/2402.01613
- **Type**: paper
- **Key takeaway**: nomic-embed-text-v1 — 137M params, 768-dim, **8192-token** context, beats OpenAI ada-002 / text-embedding-3-small on short AND long context.
- **Relevance**: Foundational long-context small model; the lineage arctic-embed-m-long descends from.

### nomic-embed-text-v1.5 model card (Hugging Face)
- **URL**: https://huggingface.co/nomic-ai/nomic-embed-text-v1.5
- **Type**: documentation / model card
- **Key takeaway**: 0.1B params, 768-dim native, **8192-token** context, Matryoshka dims {768,512,256,128,64} (64-dim = 56.10 MTEB vs 62.28 full). ONNX library tag present (ONNX files ship).
- **Relevance**: Prime candidate — long context + Matryoshka footprint lever + ONNX, ~0.52GB in fastembed.

### Nomic Embed Matryoshka announcement (Nomic)
- **URL**: https://www.nomic.ai/news/nomic-embed-matryoshka
- **Type**: vendor blog
- **Key takeaway**: v1.5 trained with MRL; recommended truncation sizes 768/512/256/128/64; supports binary embeddings.
- **Relevance**: Confirms dimension-truncation footprint lever for sqlite-vec storage.

### ollama nomic-embed-text library page
- **URL**: https://ollama.com/library/nomic-embed-text
- **Type**: registry / documentation
- **Key takeaway**: "large context length text encoder that surpasses OpenAI ada-002 and text-embedding-3-small"; the de-facto Ollama default embedder; ~274MB GGUF.
- **Relevance**: Establishes nomic-embed-text as the local-first community default.

### Embedding models · Ollama Blog
- **URL**: https://ollama.com/blog/embedding-models
- **Type**: vendor blog
- **Key takeaway**: Ollama's embedding lineup leans on nomic-embed-text, mxbai-embed-large, all-minilm as the local defaults.
- **Relevance**: Shows what the largest local-LLM runtime ships as default embedders.

### Snowflake/snowflake-arctic-embed-m-long (Hugging Face)
- **URL**: https://huggingface.co/Snowflake/snowflake-arctic-embed-m-long
- **Type**: model card
- **Key takeaway**: 137M params, 768-dim, built on nomic-embed-text-v1-unsupervised; supports up to 2048 natively / **8192 via RoPE**.
- **Relevance**: Mid-size long-context option, ONNX-friendly, smaller than bge-m3.

### Snowflake/snowflake-arctic-embed-m-v1.5 (Hugging Face)
- **URL**: https://huggingface.co/Snowflake/snowflake-arctic-embed-m-v1.5
- **Type**: model card
- **Key takeaway**: 768-dim with MRL — compresses to 256 dims / 128 bytes per vector (24x compression vs 768-dim float32) with renormalization.
- **Relevance**: Demonstrates the Matryoshka + quantization compression lever in the arctic line.

### Snowflake/snowflake-arctic-embed-l-v2.0 (Hugging Face) + Snowflake engineering blog
- **URL**: https://huggingface.co/Snowflake/snowflake-arctic-embed-l-v2.0
- **URL**: https://www.snowflake.com/en/engineering-blog/snowflake-arctic-embed-2-multilingual/
- **Type**: model card / vendor blog
- **Key takeaway**: 568M params (303M non-embedding), 1024-dim, **8192-token via RoPE**, base = xlm-roberta / BAAI bge-m3-retromae lineage; MRL (256-dim) + quantization-aware (128 bytes/vector via 4-bit). 74 languages. **ONNX + Safetensors provided.** Reported to consistently outperform BGE-M3 across English (MTEB) and multilingual (MIRACL/CLEF); the CLEF gap suggests bge-m3 may overfit MIRACL/Wikipedia.
- **Relevance**: Strongest direct bge-m3 successor — same base architecture & context, claims better retrieval, adds Matryoshka. The "drop-in upgrade" candidate.

### snowflake-arctic-embed-l-v2.0 (PromptLayer / aimodels.fyi mirrors)
- **URL**: https://www.promptlayer.com/models/snowflake-arctic-embed-l-v20
- **URL**: https://www.aimodels.fyi/models/huggingFace/snowflake-arctic-embed-l-v2.0-snowflake
- **Type**: model registry
- **Key takeaway**: Confirms 1024-dim, 8192 context, MRL, Apache-2.0.
- **Relevance**: Secondary confirmation of spec.

### Alibaba-NLP/gte-large-en-v1.5 (Hugging Face) + GTE topic survey
- **URL**: https://huggingface.co/Alibaba-NLP/gte-large-en-v1.5
- **URL**: https://www.emergentmind.com/topics/generalist-text-embedding-model-gte
- **Type**: model card / survey
- **Key takeaway**: gte-base-en-v1.5 = 137M params/768-dim; gte-large-en-v1.5 = 409M/1024-dim; both **8192-token** context. English-only (v1.5 line). gte-multilingual-base also exists for RAG.
- **Relevance**: Long-context small/mid English option; no native Matryoshka in v1.5 line, English-only.

### jina-embeddings-v3 (Jina AI / arXiv 2409.10173)
- **URL**: https://jina.ai/models/jina-embeddings-v3/
- **URL**: https://arxiv.org/abs/2409.10173
- **Type**: vendor page / paper
- **Key takeaway**: 570M params, 1024-dim default, **8192-token** context, Matryoshka down to 32 dims, task-specific LoRA adapters, multilingual. Guidance: best to keep inputs to 2048–4096 tokens for optimal quality.
- **Relevance**: Top local-RAG benchmark pick; but heavier (~2.0GB) and NOT in fastembed's mainline supported list (custom ONNX export needed).

### jina-embeddings-v2-base-en
- **URL**: (covered via fastembed list below)
- **Type**: model
- **Key takeaway**: 768-dim, 8192-token context, English; available in fastembed (~0.52GB).
- **Relevance**: Long-context, fastembed-supported, but older/English-only and no Matryoshka.

### FastEmbed Supported Models (Qdrant docs + DeepWiki)
- **URL**: https://qdrant.github.io/fastembed/examples/Supported_Models/
- **URL**: https://deepwiki.com/qdrant/fastembed/6-supported-models
- **URL**: https://github.com/qdrant/fastembed
- **Type**: documentation
- **Key takeaway**: Default = **BAAI/bge-small-en-v1.5** (384-dim, 0.067GB, has onnx-q quantized). All fastembed models are ONNX + quantized for CPU/Metal. Dense models include bge-small/base/large, snowflake-arctic-embed-m (768, 0.43GB), nomic-embed-text-v1.5 (768, 0.52GB), jina-embeddings-v2-base-en (768, 0.52GB), multilingual-e5-large (1024, 2.24GB, quantized), gte-base-en-v1.5, mxbai-embed-large-v1. **NOT in mainline list**: snowflake-arctic-embed-l-v2.0, jina-embeddings-v3, bge-m3.
- **Relevance**: Critical for the ONNX-ease axis. fastembed gives one-line torch-free local inference for nomic-v1.5, arctic-m, jina-v2, gte-base — but arctic-l-v2.0 / jina-v3 / bge-m3 require manual ONNX export or a non-fastembed runtime.

### Best Ollama Embedding Models 2026 (MorphLLM) — benchmark by MTEB/VRAM/dim
- **URL**: https://www.morphllm.com/ollama-embedding-models
- **Type**: blog / benchmark
- **Key takeaway**: Benchmarks nomic-embed-text, mxbai-embed-large, arctic, etc. by MTEB score, VRAM, dimensions for local deployment.
- **Relevance**: Local-deployment-oriented quality/size comparison.

### MTEB Leaderboard write-ups (Modal, AwesomeAgents Mar-2026, Ailog)
- **URL**: https://modal.com/blog/mteb-leaderboard-article
- **URL**: https://awesomeagents.ai/leaderboards/embedding-model-leaderboard-mteb-march-2026/
- **URL**: https://app.ailog.fr/en/blog/guides/choosing-embedding-models
- **URL**: https://huggingface.co/mteb
- **Type**: leaderboard / guide
- **Key takeaway**: 2025–26 top of MTEB is dominated by large instruct models (Qwen3-Embedding 0.6B/4B/8B, NVIDIA Llama-Embed-Nemotron-8B, gte-Qwen2). Among sub-500M, EmbeddingGemma leads MTEB mean; bge-m3 mean ~68. Retrieval nDCG@10 scales with size but small long-context models stay competitive on retrieval specifically.
- **Relevance**: Tempers "pick by MTEB rank" — the leaderboard top is too heavy (multi-GB, often torch-only) for this footprint budget.

### "Lightweight models drop to 0.4–0.6 at 4K chars" (search synthesis, BentoML/Milvus context)
- **URL**: https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models
- **Type**: blog observation
- **Key takeaway**: 512-token models (e.g. mxbai-embed-large at 512 ctx, bge-large at 512) degrade sharply on 4K-char inputs because truncation drops most of the document.
- **Relevance**: Direct evidence that 512-token models are wrong for 3–4k-token summaries — the central anti-pattern to avoid.

## Patterns Found

### Pattern 1: snowflake-arctic-embed-l-v2.0 (direct bge-m3 successor)
**Used by**: Local-RAG benchmarks position it as the "long-document specialist" (PromptQuorum); Snowflake production.
**How it works**: 568M params, **1024-dim**, **8192-token** context via RoPE, base xlm-roberta / bge-m3-retromae lineage. Matryoshka to 256 dims + quantization-aware (128 bytes/vector at 4-bit). ONNX + Safetensors on HF. Multilingual (74 lang). Apache-2.0.
**Strengths**: Same dim/context as current bge-m3 (no sqlite-vec schema change at 1024-dim), claims to beat bge-m3 on MTEB retrieval and CLEF; adds Matryoshka to shrink storage later.
**Weaknesses**: ~similar or slightly larger footprint than bge-m3; NOT in fastembed mainline (manual ONNX export / onnxruntime wiring needed); 1024-dim is the heaviest storage option.
**Example**: https://huggingface.co/Snowflake/snowflake-arctic-embed-l-v2.0

### Pattern 2: nomic-embed-text-v1.5 (long-context, small, fastembed-native)
**Used by**: Ollama default embedder, Obsidian Smart Connections, many LlamaIndex/LangChain local setups; fastembed-supported.
**How it works**: 137M params, **768-dim**, **8192-token** context, Matryoshka {768,512,256,128,64}. ONNX ships; fastembed package size ~0.52GB; ~274MB GGUF.
**Strengths**: Smaller than bge-m3, real 8192 context, torch-free one-line fastembed inference, Matryoshka footprint lever, the community local-first default. 768-dim halves sqlite-vec storage vs 1024-dim if migrating dims.
**Weaknesses**: Requires task prefixes (`search_document:` / `search_query:`) — easy to get wrong; English-leaning (v1.5); MTEB mean (~62) below bge-m3 (~68), though retrieval gap is narrower than the mean suggests.
**Example**: https://huggingface.co/nomic-ai/nomic-embed-text-v1.5

### Pattern 3: snowflake-arctic-embed-m-long (mid-size long-context, ONNX-friendly)
**Used by**: Snowflake; GGUF/ONNX community mirrors.
**How it works**: 137M params, **768-dim**, base nomic-embed-text-v1-unsupervised, 2048 native / **8192 via RoPE**. arctic-m-v1.5 variant adds MRL to 256-dim / 128 bytes.
**Strengths**: Small, long context, 768-dim, strong retrieval for size, ONNX-friendly (arctic-m is in fastembed at 0.43GB).
**Weaknesses**: m-long (RoPE) variant is separate from the fastembed-listed arctic-m; English-focused; older than v2.0.
**Example**: https://huggingface.co/Snowflake/snowflake-arctic-embed-m-long

### Pattern 4: jina-embeddings-v3 (top local-RAG quality, heavier)
**Used by**: PromptQuorum's overall local-RAG winner; Elastic, Zilliz integrations.
**How it works**: 570M params, **1024-dim** default, **8192-token** context, Matryoshka to 32, task LoRA adapters, multilingual.
**Strengths**: Best measured retrieval@10 in a local benchmark (92%), aggressive Matryoshka, multilingual.
**Weaknesses**: ~2.0GB footprint (largest of the shortlist), NOT in fastembed mainline (custom ONNX export), CC-BY-NC license restriction on v3 (non-commercial) — check before shipping in an installable plugin.
**Example**: https://jina.ai/models/jina-embeddings-v3/

### Pattern 5: EmbeddingGemma-308M (best small MTEB, but short context)
**Used by**: Google on-device push; 2026 small-model leaderboard top.
**How it works**: 308M params, **768-dim**, Matryoshka {768,512,256,128}, **2048-token max**, ~622MB.
**Strengths**: Best MTEB under 500M, Matryoshka, designed for on-device, ONNX/Transformers.js available.
**Weaknesses**: **2048-token ceiling truncates 3–4k-token summaries** — the disqualifier for this use case. Gemma license terms.
**Example**: https://developers.googleblog.com/en/introducing-embeddinggemma/

### Pattern 6: gte-large-en-v1.5 / gte-base-en-v1.5 (long-context English)
**Used by**: Alibaba; common RAG baseline.
**How it works**: base 137M/768-dim, large 409M/1024-dim, both **8192-token**. gte-base in fastembed.
**Strengths**: Real 8192 context, gte-base is small + fastembed-supported.
**Weaknesses**: English-only (v1.5 line), no native Matryoshka, retrieval roughly bge-class not clearly better.
**Example**: https://huggingface.co/Alibaba-NLP/gte-large-en-v1.5

## Anti-Patterns

- **Picking a 512-token model for 3–4k-token docs.** mxbai-embed-large (512 ctx), bge-large-en-v1.5 (512 ctx), all-MiniLM (256) silently truncate; benchmarks show lightweight 512-ctx models drop to 0.4–0.6 retrieval at ~4K chars. Excludes mxbai/bge-large/MiniLM despite good short-text MTEB. (https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models)
- **Picking by MTEB mean rank alone.** The 2025–26 leaderboard top (Qwen3-Embedding, Nemotron-8B, gte-Qwen2) is multi-GB and frequently torch-only — wrong footprint class. MTEB mean also under-weights retrieval; bge-m3's high mean partly reflects MIRACL/Wikipedia overfit per the Arctic CLEF comparison. Filter to retrieval nDCG@10 within the <600M / ONNX-available band.
- **Ignoring task-prefix requirements.** nomic and e5 families require `search_query:`/`search_document:` (or `query:`/`passage:`) prefixes; omitting them silently degrades retrieval and isn't caught by a smoke test.
- **Assuming HF ONNX == fastembed-easy.** arctic-l-v2.0, jina-v3, and bge-m3 are NOT in fastembed's mainline model list — they need manual `optimum`/onnxruntime export. Only nomic-v1.5, arctic-m, jina-v2, gte-base, bge-* get one-line torch-free inference.

## Emerging Trends

- **Matryoshka (MRL) as the footprint lever.** nomic-v1.5, arctic-m-v1.5/l-v2.0, mxbai, jina-v3, EmbeddingGemma all support dimension truncation with graceful degradation — store 256 or 512 dims in sqlite-vec, keep the option to widen later without re-embedding the model. arctic-l-v2.0 reaches 128 bytes/vector (24x compression) via MRL-256 + 4-bit quantization.
- **Quantization-aware training** (arctic v2.0) makes int8/4-bit retrieval lossless-ish — relevant since the current bge-m3 is already int8 ONNX.
- **Multilingual-by-default convergence** (arctic v2.0, jina-v3, bge-m3, gte-multilingual) vs English-only v1.5 lines (nomic-v1.5, gte-en-v1.5). For English conversation summaries, English-only models are viable and often smaller/sharper.
- **Sub-500M "on-device" class** (EmbeddingGemma, nomic-137M, arctic-m-137M) closing the MTEB gap to 1B+ models — but context length, not size, is the binding constraint here.

## Ranked Shortlist (for blind A/B vs bge-m3)

Filter applied: ≥4k usable context, ONNX-runnable without torch where possible, footprint ≤ bge-m3 class, dim ≤ 1024.

1. **snowflake-arctic-embed-l-v2.0** — 1024-dim / 8192 ctx / ~0.5–0.6GB ONNX class.
   *Why*: Direct bge-m3 successor on the same base architecture and dimension (zero sqlite-vec schema change), independent benchmarks claim it beats bge-m3 on retrieval (MTEB + CLEF), adds Matryoshka. The strongest "is the newer model actually better?" comparison. Cost: manual ONNX export (not in fastembed).

2. **nomic-embed-text-v1.5** — 768-dim / 8192 ctx / ~0.52GB (fastembed int8 smaller).
   *Why*: Genuinely smaller footprint than bge-m3, halves sqlite-vec storage at 768-dim, real 8192 context, fastembed one-line torch-free inference, Matryoshka to shrink further. The community local-first default. Watch the `search_document:`/`search_query:` prefix requirement in the eval harness.

3. **snowflake-arctic-embed-m-long** (or arctic-m-v1.5) — 768-dim / 8192-via-RoPE / ~0.43GB.
   *Why*: Smallest credible long-context option, strong retrieval-per-MB, ONNX-friendly, 768-dim storage win. A "can we go smaller without regressing?" probe against nomic-v1.5.

4. **gte-large-en-v1.5** — 1024-dim / 8192 ctx / ~0.4–0.7GB.
   *Why*: 1024-dim like bge-m3, true 8192 context, English-only (fine for English summaries), no prefix gymnastics. A clean baseline alternative to arctic-l. (gte-base-en-v1.5 at 768-dim/137M is the lighter fastembed-supported variant if footprint dominates.)

5. **jina-embeddings-v3** — 1024-dim / 8192 ctx / ~2.0GB.
   *Why*: Highest measured local-RAG retrieval quality and aggressive Matryoshka — the "quality ceiling" reference point. Include ONLY if the ~2GB footprint and CC-BY-NC (non-commercial) license are acceptable for an installable plugin; otherwise drop it.

**Excluded and why**: EmbeddingGemma-308M (2048-token ceiling truncates 3–4k summaries), mxbai-embed-large / bge-large-en-v1.5 / all-MiniLM (512 or 256-token context — truncate and regress), Qwen3-Embedding / Nemotron-8B (multi-GB, torch-heavy — wrong footprint class).
