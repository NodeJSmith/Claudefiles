---
topic: "embeddings-model recall eval — results and recommendation"
date: 2026-06-19
status: Complete — recommend jina-v2-small-en
---

# Embeddings-Model Recall Eval

Empirical follow-up to `embeddings-model-research.md`: does a lighter, fastembed-native
model preserve retrieval quality on our own corpus? Decided by a recall@k harness over the
real ccrecall corpus, not by MTEB.

## Method

- **Corpus:** 1988 active branch summaries from the live VPS DB (`~/.claude-memory/conversations.db`).
- **Fixture (label-free, realistic):** for 150 sampled branches, the query is a held-out *user
  utterance* from that conversation (not the topic, which leaks verbatim into the summary), and
  the correct target is that branch's summary. Mirrors the real recall task — "user types a
  natural question, find the right past conversation."
- **Metrics:** recall@1/5/10, MRR, nDCG@10, median rank. Single relevant doc per query.
- **Harness:** `~/source/claude-code-recall/scripts/embedding_eval/recall_harness.py`. bge-m3
  baseline reuses the doc vectors already stored in `branch_vec` (only the 150 queries embed
  live); candidates run through fastembed. Candidates embedded on the gaming rig's GPU.
- **Caveat:** a handful of fixture queries sit close to their conversation's opening line,
  slightly inflating *absolute* recall — but uniformly across all dense models, so the
  *relative* ranking (the decision) holds.

## Results

| Model | recall@1 | recall@5 | recall@10 | MRR | nDCG@10 | median rank |
|---|---|---|---|---|---|---|
| **bge-m3** (baseline, 1024d) | 0.540 | 0.727 | 0.767 | 0.626 | 0.655 | 1 |
| **jina-v2-small-en** (512d) | 0.533 | **0.747** | **0.800** | 0.625 | **0.662** | 1 |
| nomic-v1.5 (768d) | 0.540 | 0.720 | 0.753 | 0.621 | 0.650 | 1 |
| nomic-v1.5-Q (768d int8) | _not run — see below_ | | | | | |

## Recommendation: switch to jina-v2-small-en

The research brief set a low bar — a candidate only had to *not lose materially* to bge-m3 to
justify the switch, since fastembed-native install ergonomics (auto-download, no PyTorch) are
the headline win. jina clears it outright by **winning** on the metrics that matter for retrieval:

- recall@5 +0.020, recall@10 +0.033, nDCG@10 +0.007 over bge-m3; ties on recall@1 and MRR.
- **Half the vector dimension** (512 vs 1024) → smaller `branch_vec` index, faster ANN search,
  less storage — a real operational win on top of the quality.
- fastembed-native, so the install story is simpler than bge-m3's.

**nomic-v1.5** lands ≈ bge-m3 (marginally lower across the board) — no reason to switch to it.

**nomic-v1.5-Q** was skipped: its quality ceiling is the full nomic-v1.5, which already lost to
both bge-m3 and jina, so the quantized variant cannot change the decision. (It is also the one
model that does not GPU-accelerate — see below.)

## Why the corpus wasn't embedded on the VPS

Embedding the 1988-doc corpus on the VPS thrashed/hung the box **three times** (unbounded
overnight swap-spiral at load 95; a niced run still spiking load to 63; even thread-capped it
hung on the already-slammed morning box). The VPS (15 GB, shared, always-on) is the wrong place
for a parallel embedding bake-off. **Heavy embedding jobs go on a workstation, never
backgrounded unattended on the VPS.**

## Gaming-rig lessons (the candidates' actual run)

"Just run the CPU bundle on the rig" hit its own walls — the rig's WSL2 is *also* 15 GB (host
has 32 GB, but WSL defaults to ~half; raised to 24 GB via `.wslconfig memory=` for future runs):

- **Batch size is a seq² memory bomb.** fastembed's default batch=256 tried a 73 GB attention
  buffer (summaries run to ~3000 tokens; attention scales batch·heads·seq²). Even batch=4
  OOM-killed the heavier nomic models past 12 GB. CPU-safe batch is 2.
- **CPU is FLOP-bound and slow.** nomic on CPU ≈ 1 doc/s → ~30 min/model. Larger batches don't
  help wall-time (cores already saturated), only raise the memory peak.
- **GPU is the real lever.** The rig has an RTX 3060 Ti (8 GB). With `fastembed-gpu` + the
  CUDA-12 onnxruntime stack, jina and nomic-v1.5 embedded in ~10 min total on VRAM. batch=4
  fits the 8 GB card; batch=8 OOMs VRAM on the long docs.
- **Quantized models don't GPU-accelerate.** nomic-v1.5-Q's int8 ops have no CUDA kernels, so
  onnxruntime falls back to CPU with constant host↔device memcpy — slower than plain CPU. Run
  quantized variants on CPU only.
- **Guard the box structurally.** Runs went under a systemd `--scope` with `MemoryMax` +
  `MemorySwapMax=0`, so a blowup OOM-kills the *job* cleanly instead of swap-freezing the
  machine. Note: `cmd | tee` masks the real exit code — check `systemctl --user show <unit>
  -p Result` and `results.json`, not the pipe's exit status.

## Reproduce

The harness embeds one or more models and merges into `results.json` (so models can be run
one at a time). On a CUDA GPU, enable GPU mode with batch 4 (fits an 8 GB card; non-quantized
models only). On CPU, leave GPU off and use batch 2 — slow but memory-safe. See
`recall_harness.py --help` for the exact flags.
