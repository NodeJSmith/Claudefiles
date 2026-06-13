# Changelog

## Unreleased

### Added

- Local semantic search fused with FTS via Reciprocal Rank Fusion (RRF). Search results from `cm-search-conversations` now combine keyword ranking (FTS5/FTS4/LIKE) with vector KNN from a locally-running bge-m3 (int8 ONNX) model. Degrades automatically to keyword-only when the model or sqlite-vec extension is unavailable.
- New runtime dependencies: `sqlite-vec` (vector KNN), `onnxruntime` (ONNX inference), `tokenizers` (text tokenization), `numpy` (vector math).
- `cm-backfill-embeddings` command: embeds all un-embedded branches using bge-m3. Run once after first install; subsequent runs only process new branches.
- `cm-search-conversations --keyword-only`: skip embedding, use keyword search only.
- `cm-search-conversations --status`: print diagnostic info (vec extension loaded, model path, embedded/total branch count) and exit 0.
- `branch_vec` vec0 virtual table in `conversations.db` storing per-branch 1024-dim embeddings.
