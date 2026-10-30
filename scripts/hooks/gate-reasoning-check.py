#!/usr/bin/env python3
"""PostToolUse/PostToolUseFailure hook (AskUserQuestion): when a sketch decision or
challenge finding question reached the user with no reasoning in message text,
tell the agent right away, so the next question has it.

The user sees message text and the question's short labels. Ledger edits, file
reads, and the findings file are not on their screen, so writing the reasoning
to any of those doesn't show it. Instructions alone haven't held this: the first
question in a run usually gets its context and later ones usually don't.

This can't refuse the question. In an interactive session the current response
isn't written to the transcript until PreToolUse returns, so a hook can't see the
text in front of the call until after it has been asked.

A run of text counts only if it was written since the previous question or the
user's last message, with no tool call inside it, so a pile of short status
lines doesn't pass, and a batched call needs enough for each of its questions.
Anything this hook can't determine stays silent.
"""

import json
import logging
import logging.handlers
import re
import sys
import time
from pathlib import Path

# These match the question wording in mine-sketch and mine-challenge; the tests tie the two together.
GATE_QUESTION = re.compile(r"\bDecision \d+\b|\bFinding \d+\b|\b\d+ rare-case finding")
GATE_HEADER = re.compile(r"^D\d+$")
# Below a collapsed decision: its situation, deciding factor, recommendation, and "pick X instead if".
MIN_REASONING_CHARS = 200
# The call can land on disk slightly after the hook starts.
FLUSH_TIMEOUT_SECONDS = 3.0
FLUSH_POLL_SECONDS = 0.1
LOG_PATH = Path.home() / ".local" / "share" / "claudefiles" / "gate-reasoning-check.log"
LOG_MAX_BYTES = 1_000_000

REMINDER = (
    "The question you just asked reached the user with no reasoning: tool calls, ledger edits, and the "
    "findings file aren't on their screen. Before the next decision or finding question, write it as "
    "message text: what exists today and what goes wrong in plain language, with no bare D<n> or finding "
    "numbers, then the deciding factor, options table, recommendation, and when to pick otherwise. For a "
    "rare-case batch, list each finding. If the user's answer was a question, or they couldn't choose, "
    "answer in message text with new information before asking again; rewording the options doesn't answer it."
)

log = logging.getLogger("gate-reasoning-check")


def gate_question_count(tool_input: dict) -> int:
    return sum(
        bool(
            GATE_QUESTION.search(q.get("question", ""))
            or GATE_HEADER.match(q.get("header", ""))
        )
        for q in tool_input.get("questions", [])
    )


def read_events(path: str) -> list[tuple[str, dict]]:
    """Every content block in the main thread, in order, as (record type, block)."""
    events = []
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if record.get("type") not in ("assistant", "user") or record.get(
                "isSidechain"
            ):
                continue
            message = record.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, str):
                content = [{"type": "text", "text": content}]
            if isinstance(content, list):
                events += [(record["type"], b) for b in content if isinstance(b, dict)]
    return events


def events_before_call(path: str, tool_use_id: str) -> list[tuple[str, dict]] | None:
    """Everything before this call, or None if it never reaches the transcript."""
    deadline = time.monotonic() + FLUSH_TIMEOUT_SECONDS
    while True:
        events = read_events(path)
        for i, (_, block) in enumerate(events):
            if block.get("type") == "tool_use" and block.get("id") == tool_use_id:
                return events[:i]
        if time.monotonic() >= deadline:
            return None
        time.sleep(FLUSH_POLL_SECONDS)


def longest_text_run(events: list[tuple[str, dict]]) -> int:
    """Longest unbroken text since the previous question or the user's last message."""
    best = run = 0
    for record_type, block in events:
        kind = block.get("type")
        if record_type == "assistant" and kind == "text":
            run += len(block.get("text", "").strip())
        elif (kind == "tool_use" and block.get("name") == "AskUserQuestion") or (
            record_type == "user" and kind == "text"
        ):
            best = run = 0
        elif kind in ("tool_use", "tool_result"):
            best = max(best, run)
            run = 0
    return max(best, run)


def setup_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        LOG_PATH, maxBytes=LOG_MAX_BYTES, backupCount=1
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)


def main() -> None:
    payload = json.load(sys.stdin)
    gates = gate_question_count(payload.get("tool_input", {}))
    if not gates:
        return
    setup_logging()
    session = payload.get("session_id")
    try:
        events = events_before_call(payload["transcript_path"], payload["tool_use_id"])
    except (KeyError, OSError):
        log.exception("could not read the transcript session=%s", session)
        return
    if events is None:
        log.warning(
            "call not in transcript after %.1fs session=%s",
            FLUSH_TIMEOUT_SECONDS,
            session,
        )
        return
    chars = longest_text_run(events)
    if chars >= MIN_REASONING_CHARS * gates:
        log.info("shown chars=%d session=%s", chars, session)
        return
    log.warning("not shown chars=%d session=%s", chars, session)
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": payload.get("hook_event_name"),
                "additionalContext": REMINDER,
            }
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
