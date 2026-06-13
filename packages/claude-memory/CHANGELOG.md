# Changelog

## Unreleased

### Added

- Local semantic search fused with FTS via Reciprocal Rank Fusion (RRF). Search results from `cm-search-conversations` now combine keyword ranking (FTS5/FTS4/LIKE) with vector KNN from a locally-running bge-m3 (int8 ONNX) model. Degrades automatically to keyword-only when the model or sqlite-vec extension is unavailable.
- New runtime dependencies: `sqlite-vec` (vector KNN), `onnxruntime` (ONNX inference), `tokenizers` (text tokenization), `numpy` (vector math).
- `cm-backfill-embeddings` command: **opt-in** seeding of embeddings for historical active-leaf branches using bge-m3 (int8 ONNX). Not auto-spawned — bge-m3 inference is CPU-heavy (~4–5s/summary), so historical seeding only runs when you invoke it. Supports `--days N` (recency window), `--limit N` (cap per run), and `--threads N` (inference threads); resumable. New sessions are covered automatically by embed-on-write.
- Embedding scoped to **active-leaf branches only** (`is_active = 1`): the search path only returns active leaves, so inactive forks/retries are no longer embedded — ~6.6× less work and a leaner KNN index, with no recall change.
- Embedding throttle: inference runs at one onnxruntime thread by default (raise with `cm-backfill-embeddings --threads N`) and the backfill runs at lowered scheduling priority (`nice`), so it never saturates the machine.
- `cm-search-conversations --keyword-only`: skip embedding, use keyword search only.
- `cm-search-conversations --status`: print diagnostic info (vec extension loaded, model path, embedded/total branch count) and exit 0.
- `branch_vec` vec0 virtual table in `conversations.db` storing per-branch 1024-dim embeddings.
