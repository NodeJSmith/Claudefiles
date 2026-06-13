#!/usr/bin/env python3
"""
Backfill embeddings for existing branches.

Runs as a background process spawned by memory_setup.py on SessionStart.
Processes branches in batches, commits between batches, and marks per-row
content errors with embedding_version = -1 to avoid infinite retry.

Two-level failure distinction:
  - Model/session failure: abort the whole run, mark NOTHING.
  - Per-row content error (tokenizer overflow, malformed summary): mark that
    row embedding_version = -1 and continue.
"""

import sys
import time

from claude_memory.db import (
    DEFAULT_DB_PATH,
    get_db_connection,
    load_settings,
    setup_logging,
    write_branch_embedding,
)
from claude_memory.embeddings import (
    EMBEDDING_MODEL,
    EMBEDDING_VERSION,
    embed_text,
    model_available,
)
from claude_memory.summarizer import SUMMARY_VERSION

BATCH_SIZE = 20
BACKFILL_BATCH_DELAY_SECONDS = 0.05

_PID_FILE = DEFAULT_DB_PATH.parent / ".pid-cm-backfill-embeddings"


def main():
    try:
        _main()
    finally:
        try:
            _PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass


def _main():
    settings = load_settings()
    logger = setup_logging(settings)

    # FR#14 ABORT level: check model availability before touching any rows.
    # model_available() warms the singleton session on success — no extra cost.
    if not model_available():
        logger.error(
            "Backfill embeddings: model not available, aborting (no rows marked)"
        )
        print(
            "cm-backfill-embeddings: model not available, aborting (no rows marked)",
            file=sys.stderr,
        )
        return

    try:
        conn = get_db_connection(settings, load_vec=True)
    except Exception as e:
        logger.error(f"Backfill embeddings: failed to connect to DB: {e}")
        print(
            f"cm-backfill-embeddings: failed to connect to DB: {e}",
            file=sys.stderr,
        )
        return

    cursor = conn.cursor()
    total_updated = 0
    last_batch_ids: list[int] | None = None

    # Compute total-eligible count once (Fix 3: avoid per-batch full COUNT).
    cursor.execute(
        """
        SELECT COUNT(*) FROM branches
        WHERE context_summary IS NOT NULL
          AND context_summary != ''
          AND embedding_version IS NOT -1
          AND (
            embedding_version IS NULL
            OR embedding_version < ?
            OR embedding_model IS NOT ?
            OR summary_version_at_embed IS NOT ?
            OR NOT EXISTS (SELECT 1 FROM branch_vec WHERE branch_id = branches.id)
          )
        """,
        (EMBEDDING_VERSION, EMBEDDING_MODEL, SUMMARY_VERSION),
    )
    total_eligible = cursor.fetchone()[0]

    while True:
        # Selection predicate:
        #   - non-empty context_summary
        #   - NOT the error sentinel (-1)
        #   - needs embedding: NULL, old version, wrong model, summary changed, or
        #     version columns say "done" but branch_vec row is missing (heal clause)
        # IS NOT / IS DISTINCT FROM used throughout so NULL comparisons are correct.
        cursor.execute(
            """
            SELECT id, context_summary FROM branches
            WHERE context_summary IS NOT NULL
              AND context_summary != ''
              AND embedding_version IS NOT -1
              AND (
                embedding_version IS NULL
                OR embedding_version < ?
                OR embedding_model IS NOT ?
                OR summary_version_at_embed IS NOT ?
                OR NOT EXISTS (SELECT 1 FROM branch_vec WHERE branch_id = branches.id)
              )
            LIMIT ?
            """,
            (EMBEDDING_VERSION, EMBEDDING_MODEL, SUMMARY_VERSION, BATCH_SIZE),
        )
        rows = cursor.fetchall()

        if not rows:
            break

        current_ids = [r[0] for r in rows]
        if current_ids == last_batch_ids:
            logger.error(
                "Backfill embeddings: no progress — same batch re-selected; aborting to avoid infinite loop"
            )
            print(
                "cm-backfill-embeddings: no progress — same batch re-selected, aborting",
                file=sys.stderr,
            )
            break
        last_batch_ids = current_ids

        try:
            for branch_id, summary in rows:
                cursor.execute("SAVEPOINT row")
                try:
                    vec = embed_text(summary)
                    # Order invariant: vec upsert FIRST, then version columns.
                    # A failed upsert leaves embedding_version unchanged.
                    write_branch_embedding(cursor, branch_id, vec, SUMMARY_VERSION)
                    cursor.execute("RELEASE SAVEPOINT row")
                    total_updated += 1
                except (ValueError, OverflowError, UnicodeError) as e:
                    cursor.execute("ROLLBACK TO SAVEPOINT row")
                    cursor.execute("RELEASE SAVEPOINT row")
                    # Per-row content error: mark sentinel so this row is skipped next run.
                    cursor.execute(
                        "UPDATE branches SET embedding_version = -1 WHERE id = ?",
                        (branch_id,),
                    )
                    logger.error(f"Backfill embeddings: branch {branch_id} failed: {e}")
        except Exception as e:
            # Infra/session failure (e.g. ONNX session crash, OOM): abort without
            # marking any further rows — they stay eligible for the next run.
            logger.error(f"Backfill embeddings: session failure, aborting: {e}")
            conn.commit()
            return

        conn.commit()

        # Progress logging (FR#8): use Python arithmetic instead of a second COUNT.
        remaining = max(0, total_eligible - total_updated)
        logger.info(
            f"Backfill embeddings: processed {total_updated} so far, {remaining} remaining"
        )
        print(
            f"cm-backfill-embeddings: {total_updated} embedded, {remaining} remaining",
            file=sys.stderr,
        )

        time.sleep(BACKFILL_BATCH_DELAY_SECONDS)

    conn.close()
    logger.info(f"Backfill embeddings complete: {total_updated} branches embedded")
    print(
        f"cm-backfill-embeddings: complete: {total_updated} branches embedded",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
