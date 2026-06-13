#!/usr/bin/env python3
"""
Backfill embeddings for existing active-leaf branches.

Opt-in: invoke manually via `cm-backfill-embeddings` to seed historical
embeddings. NOT auto-spawned on SessionStart (bge-m3 inference is CPU-heavy);
forward coverage comes from embed-on-write instead.
Processes branches in batches, commits between batches, and marks per-row
content errors with embedding_version = -1 to avoid infinite retry.

Two-level failure distinction:
  - Model/session failure: abort the whole run, mark NOTHING.
  - Per-row content error (tokenizer overflow, malformed summary): mark that
    row embedding_version = -1 and continue.
"""

import argparse
import os
import sys
import time

from claude_memory.db import (
    DEFAULT_DB_PATH,
    branch_vec_queryable,
    get_db_connection,
    load_settings,
    setup_logging,
    write_branch_embedding,
)
from claude_memory.embeddings import (
    DEFAULT_EMBED_THREADS,
    EMBEDDING_MODEL,
    EMBEDDING_VERSION,
    embed_text,
    model_available,
)
from claude_memory.summarizer import SUMMARY_VERSION

BATCH_SIZE = 20
BACKFILL_BATCH_DELAY_SECONDS = 0.05

_PID_FILE = DEFAULT_DB_PATH.parent / ".pid-cm-backfill-embeddings"


def build_selection(days: int | None) -> tuple[str, list]:
    """Return the shared WHERE clause + params for eligible-branch selection.

    Eligible = active leaf (is_active=1; the query path only ever returns active
    leaves, so embedding inactive forks would produce never-returnable vectors),
    non-empty summary, not the error sentinel (-1), and needing an embedding
    (missing/old version, wrong model, summary changed, or vector missing — the
    heal clause). Optional recency bound on ended_at via --days; note this
    excludes branches with a NULL ended_at (SQLite `NULL > x` is false).
    Uses SQL `IS NOT` (not `!=`) so NULL comparisons behave. Returns a SQL
    fragment meant to be interpolated as f"... FROM branches {where}".
    """
    where = """
        WHERE is_active = 1
          AND context_summary IS NOT NULL
          AND context_summary != ''
          AND embedding_version IS NOT -1
          AND (
            embedding_version IS NULL
            OR embedding_version < ?
            OR embedding_model IS NOT ?
            OR summary_version_at_embed IS NOT ?
            OR NOT EXISTS (SELECT 1 FROM branch_vec WHERE branch_id = branches.id)
          )
    """
    params: list = [EMBEDDING_VERSION, EMBEDDING_MODEL, SUMMARY_VERSION]
    if days is not None:
        where += "          AND ended_at > datetime('now', ?)\n"
        params.append(f"-{days} days")
    return where, params


def main():
    try:
        _main()
    finally:
        try:
            _PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass


def _main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(
        description="Embed active-leaf branch summaries (opt-in; not auto-spawned)."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Only embed branches ended within the last N days (default: all history; "
        "branches with no recorded end-time are excluded when this flag is used)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after embedding at most N branches this run",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=DEFAULT_EMBED_THREADS,
        help="onnxruntime inference threads (default: %(default)s). Raise it on "
        "an idle machine to finish faster; 1 keeps the box responsive.",
    )
    args = parser.parse_args(argv)

    settings = load_settings()
    logger = setup_logging(settings)

    # Background CPU job: lower scheduling priority so the bounded inference
    # threads yield to interactive work (machines.md thrash risk). Best-effort —
    # os.nice is POSIX-only and may be denied; either way the run proceeds.
    try:
        os.nice(10)
    except (AttributeError, OSError):
        pass

    # FR#14 ABORT level: check model availability before touching any rows.
    # model_available() warms the singleton session on success — no extra cost.
    # Pass --threads here since this is the call that constructs the session.
    if not model_available(threads=args.threads):
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

    # FR#14 ABORT level: vec must be queryable before any selection runs — the
    # eligibility WHERE references branch_vec, which get_db_connection only
    # creates when sqlite-vec loaded. Without this guard the COUNT below crashes
    # with "no such table: branch_vec" instead of exiting cleanly.
    if not branch_vec_queryable(conn):
        logger.error(
            "Backfill embeddings: sqlite-vec unavailable, aborting (no rows marked)"
        )
        print(
            "cm-backfill-embeddings: sqlite-vec unavailable, aborting (no rows marked)",
            file=sys.stderr,
        )
        return

    total_updated = 0
    last_batch_ids: list[int] | None = None

    where, params = build_selection(args.days)

    # Compute total-eligible count once (Fix 3: avoid per-batch full COUNT).
    cursor.execute(f"SELECT COUNT(*) FROM branches {where}", params)
    total_eligible = cursor.fetchone()[0]
    if args.limit is not None:
        total_eligible = min(total_eligible, args.limit)

    while True:
        if args.limit is not None and total_updated >= args.limit:
            break

        # ORDER BY id keeps batch order deterministic: the no-progress guard
        # below compares current_ids to last_batch_ids, which is only meaningful
        # if re-selection returns rows in a stable order.
        cursor.execute(
            f"SELECT id, context_summary FROM branches {where} ORDER BY id LIMIT ?",
            (*params, BATCH_SIZE),
        )
        rows = cursor.fetchall()

        if not rows:
            break

        # Honor --limit precisely even though batches are BATCH_SIZE-wide.
        if args.limit is not None:
            rows = rows[: args.limit - total_updated]

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
