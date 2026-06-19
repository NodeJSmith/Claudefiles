---
topic: "embeddings-model recall eval — results and how to finish"
date: 2026-06-19
status: In progress (baseline done, candidates pending)
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
  live); candidates run through fastembed.
- **Caveat:** a handful of fixture queries sit close to their conversation's opening line,
  slightly inflating *absolute* recall — but uniformly across all dense models, so the
  *relative* ranking (the decision) holds.

## Results so far

| Model | recall@1 | recall@5 | recall@10 | MRR | nDCG@10 | median rank |
|---|---|---|---|---|---|---|
| **bge-m3** (baseline) | 0.540 | 0.727 | 0.767 | 0.626 | 0.655 | 1 |
| jina-v2-small-en (0.12 GB, 512d) | _pending_ | | | | | |
| nomic-v1.5-Q (0.13 GB, 768d int8) | _pending_ | | | | | |
| nomic-v1.5 (0.52 GB, 768d) | _pending_ | | | | | |

The decision rule (from the research brief): install ergonomics (fastembed auto-download, no
PyTorch) is the headline win; a candidate only has to show it doesn't *lose materially* to
bge-m3 on retrieval over our data to justify the switch.

## Why the candidates aren't done yet (the VPS lesson)

Embedding the 1988-doc corpus on the VPS thrashed/hung the box **three times**: (1) unbounded
overnight run swap-spiraled for hours (load 95); (2) a niced full run spiked load to 63 —
fastembed lets onnxruntime grab every core, and `nice` lowers priority but not thread count;
(3) even thread-capped to 1, the run hung on the already-slammed morning box (7h headless
Chrome + multiple Claude sessions + services) and had to be killed. The VPS (15 GB, shared,
always-on) is the wrong place for a parallel embedding bake-off. **Lesson: heavy embedding
jobs go on a workstation, never backgrounded unattended on the VPS.**

## How to finish (gaming rig)

A portable bundle was tarred to `smithfamily:/tmp/embedding-eval-bundle.tar.gz` (also in
`scripts/embedding_eval/`): `recall_harness.py`, `corpus.json`, `fixture.json`,
`results.json` (carries the bge-m3 baseline), `README.md`. No DB / ccrecall / sqlite-vec
needed — just `fastembed` + `numpy`.

On the gaming rig:

```bash
scp smithfamily:/tmp/embedding-eval-bundle.tar.gz .
tar xzf embedding-eval-bundle.tar.gz && cd embedding_eval
uv run --with fastembed --with numpy python recall_harness.py \
    --models jina-v2-small-en,nomic-v1.5-Q,nomic-v1.5 --corpus-file corpus.json
```

Copy the resulting `results.json` back, fill the table above, and write the recommendation.
