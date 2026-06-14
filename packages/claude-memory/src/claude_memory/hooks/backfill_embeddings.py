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

Built to run unattended (systemd timer): `--status [--json]` reports progress
without embedding, progress lines carry elapsed/ETA, and abort paths exit
non-zero so the scheduler sees the failure.
"""

import argparse
import json
import os
import sys
import time

from claude_memory.db import (
    CONTENT_ERROR_VERSION,
    DEFAULT_DB_PATH,
    EMBEDDABLE_BRANCH_FILTER,
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
DEFAULT_PROGRESS_EVERY = BATCH_SIZE

EXIT_OK = 0
EXIT_ABORT = 1

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
    where = f"""
        WHERE {EMBEDDABLE_BRANCH_FILTER}
          AND embedding_version IS NOT {CONTENT_ERROR_VERSION}
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


def count_status(cursor, days: int | None) -> dict[str, int]:
    """Count backfill progress without doing any work.

    universe = active leaves with a non-empty summary (the embeddable set).
    eligible = need an embedding now (shares build_selection()'s predicate, so
               status and the run agree on what "remaining" means).
    errored  = marked with the content-error sentinel.
    done     = universe - eligible - errored (derived, not queried). The three
               counted sets partition the universe: build_selection excludes the
               sentinel, so eligible and errored are disjoint.
    The optional --days recency bound is applied consistently to the three
    counted queries.
    """
    recency = ""
    recency_params: list = []
    if days is not None:
        recency = " AND ended_at > datetime('now', ?)"
        recency_params = [f"-{days} days"]

    cursor.execute(
        f"SELECT COUNT(*) FROM branches WHERE {EMBEDDABLE_BRANCH_FILTER}{recency}",
        recency_params,
    )
    universe = cursor.fetchone()[0]

    cursor.execute(
        f"SELECT COUNT(*) FROM branches WHERE {EMBEDDABLE_BRANCH_FILTER}"
        f" AND embedding_version IS {CONTENT_ERROR_VERSION}{recency}",
        recency_params,
    )
    errored = cursor.fetchone()[0]

    where, params = build_selection(days)
    cursor.execute(f"SELECT COUNT(*) FROM branches {where}", params)
    eligible = cursor.fetchone()[0]

    # max(0, ...) guards the one case the partition can't: the three counts are
    # separate statements, so an embed-on-write commit landing mid-read could
    # shrink `eligible` after `universe` was sampled, nudging the difference
    # negative. Clamp rather than report a nonsense negative "done".
    done = max(0, universe - eligible - errored)
    return {
        "universe": universe,
        "done": done,
        "eligible": eligible,
        "errored": errored,
    }


def format_duration(seconds: float) -> str:
    """Compact human duration: '45s', '12m03s', '1h07m'."""
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


def run_status(args, settings, logger) -> int:
    """Report done/eligible/errored/total without embedding anything (read-only)."""
    try:
        conn = get_db_connection(settings, load_vec=True)
    except Exception as e:
        logger.error(f"Backfill status: failed to connect to DB: {e}")
        print(f"cm-backfill-embeddings: failed to connect to DB: {e}", file=sys.stderr)
        return EXIT_ABORT

    if not branch_vec_queryable(conn):
        print("cm-backfill-embeddings: sqlite-vec unavailable", file=sys.stderr)
        conn.close()
        return EXIT_ABORT

    try:
        counts = count_status(conn.cursor(), args.days)
    finally:
        conn.close()

    if args.json:
        print(json.dumps({**counts, "days": args.days}))
        return EXIT_OK

    universe = counts["universe"]
    done = counts["done"]
    pct = (done / universe * 100) if universe else 0.0
    scope = f" (last {args.days}d)" if args.days is not None else ""
    print(f"cm-backfill-embeddings status{scope}:")
    print(f"  embedded:  {done} / {universe}  ({pct:.0f}%)")
    print(f"  remaining: {counts['eligible']}")
    if counts["errored"]:
        print(f"  errored:   {counts['errored']}  (content errors, won't retry)")
    return EXIT_OK


def main():
    # Skip the PID cleanup for the read-only status path: it must never disturb
    # a concurrently-running backfill's PID marker. Detected straight from argv
    # because _main() owns the argparse pass; --status is a store_true flag, so
    # the `--status=x` forms argparse would reject can't reach here as a false
    # positive. On an unhandled exception _main() raises through the finally and
    # the traceback (non-zero exit) propagates — which is the right signal for a
    # timer — so sys.exit() below only runs on the normal integer-return paths.
    is_status = "--status" in sys.argv[1:]
    try:
        code = _main()
    finally:
        if not is_status:
            try:
                _PID_FILE.unlink(missing_ok=True)
            except OSError:
                pass
    sys.exit(code)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Embed active-leaf branch summaries (opt-in; not auto-spawned)."
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Report progress (embedded/remaining/errored/total) and exit without "
        "embedding. Read-only; safe to run while a backfill is in progress.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable result on stdout (status counts, or a "
        "final run summary); per-batch progress stays on stderr. On failure the "
        "exit code is non-zero and the reason is on stderr.",
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
        "--progress-every",
        type=int,
        default=DEFAULT_PROGRESS_EVERY,
        metavar="N",
        help="Print a progress line (with elapsed/ETA) once at least N more "
        "branches have embedded, checked at each batch commit (default: %(default)s)",
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

    if args.status:
        return run_status(args, settings, logger)

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
        return EXIT_ABORT

    try:
        conn = get_db_connection(settings, load_vec=True)
    except Exception as e:
        logger.error(f"Backfill embeddings: failed to connect to DB: {e}")
        print(
            f"cm-backfill-embeddings: failed to connect to DB: {e}",
            file=sys.stderr,
        )
        return EXIT_ABORT

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
        conn.close()
        return EXIT_ABORT

    total_updated = 0
    last_progress = 0
    last_batch_ids: list[int] | None = None
    started = time.monotonic()

    where, params = build_selection(args.days)

    # Compute total-eligible count once (Fix 3: avoid per-batch full COUNT).
    cursor.execute(f"SELECT COUNT(*) FROM branches {where}", params)
    total_eligible = cursor.fetchone()[0]
    if args.limit is not None:
        total_eligible = min(total_eligible, args.limit)

    logger.info(f"Backfill embeddings: starting, {total_eligible} branches to embed")
    print(
        f"cm-backfill-embeddings: starting, {total_eligible} to embed",
        file=sys.stderr,
    )

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
            conn.close()
            return EXIT_ABORT
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
            conn.close()
            return EXIT_ABORT

        conn.commit()

        # Progress (FR#8): cadence-gated, with elapsed + ETA for unattended runs.
        # Python arithmetic instead of a second COUNT.
        if total_updated - last_progress >= args.progress_every:
            elapsed = time.monotonic() - started
            remaining = max(0, total_eligible - total_updated)
            rate = total_updated / elapsed if elapsed > 0 else 0.0
            eta = format_duration(remaining / rate) if rate > 0 else "?"
            msg = (
                f"{total_updated}/{total_eligible} embedded, {remaining} left, "
                f"{format_duration(elapsed)} elapsed, ETA {eta}"
            )
            logger.info(f"Backfill embeddings: {msg}")
            print(f"cm-backfill-embeddings: {msg}", file=sys.stderr)
            last_progress = total_updated

        time.sleep(BACKFILL_BATCH_DELAY_SECONDS)

    conn.close()
    elapsed = time.monotonic() - started
    remaining = max(0, total_eligible - total_updated)
    logger.info(
        f"Backfill embeddings complete: {total_updated} branches embedded "
        f"in {format_duration(elapsed)}"
    )
    if args.json:
        print(
            json.dumps(
                {
                    "status": "complete",
                    "embedded": total_updated,
                    "remaining": remaining,
                    "elapsed_seconds": round(elapsed, 1),
                }
            )
        )
    else:
        print(
            f"cm-backfill-embeddings: complete — {total_updated} embedded "
            f"in {format_duration(elapsed)}",
            file=sys.stderr,
        )
    return EXIT_OK


if __name__ == "__main__":
    main()
