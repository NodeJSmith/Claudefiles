#!/usr/bin/env python3
"""PreToolUse hook (AskUserQuestion): deny a decision question whose reasoning
never reached the user's screen.

mine-sketch ("Decision N of M: ...") and mine-challenge ("Finding N/M: ...")
require the decision's reasoning as reply text before each question. That
reasoning also lives in a file (design.md, the findings file), and an agent that
just wrote or read it there tends to treat it as shown — but tool inputs and
results are collapsed in the terminal, so the user sees only the bare question.
This hook makes that check mechanical.

Trigger: a question matching one of QUESTION_KINDS. Every other AskUserQuestion
passes through untouched.

Requirement: the assistant `text` blocks between the last real user entry (a
prompt or a tool result) and this tool call contain every marker that kind
requires. Only `text` blocks count; tool inputs, tool results, and thinking do
not.

Transcript timing: when PreToolUse fires, the current turn's blocks are not yet
on disk — they land roughly 100ms later. Blocks are appended in order, so the
hook polls until its own `tool_use` block parses out of the transcript; every
block before it is then present. If that never happens within the deadline, the
hook allows the call and logs why rather than blocking on a timing failure.

Log: ~/.local/share/claudefiles/decision-context-check.log
"""

import json
import logging
import re
import sys
import time
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path


@dataclass(frozen=True)
class QuestionKind:
    name: str
    trigger: re.Pattern[str]
    markers: dict[str, re.Pattern[str]]
    fix: str


DECIDING_FACTOR = re.compile(r"deciding[- ]factor:", re.IGNORECASE)

# Markers are a presence check, not a rubric validator: each kind requires the
# two labels most specific to its skill's rubric format, which only appear when
# the agent actually wrote the rubric out. Sketch's rubric (presenting-decisions.md)
# always has a Recommendation line; challenge's findings carry the recommendation
# on the option itself, so its distinctive label is Pick-instead-if.
QUESTION_KINDS = (
    QuestionKind(
        name="mine-sketch decision",
        trigger=re.compile(r"\bDecision \d+ of \d+"),
        markers={
            "Deciding factor": DECIDING_FACTOR,
            "Recommendation": re.compile(r"recommendation:", re.IGNORECASE),
        },
        fix="Write the deciding factor, criteria table, recommendation and 'Pick X instead if' "
        "(per presenting-decisions.md)",
    ),
    QuestionKind(
        name="mine-challenge finding",
        trigger=re.compile(r"\bFinding \d+/\d+"),
        markers={
            "Deciding-factor": DECIDING_FACTOR,
            "Pick-instead-if": re.compile(r"pick[- ]instead[- ]if", re.IGNORECASE),
        },
        fix="Write the finding's Deciding-factor, Criteria table and Pick-instead-if, copied from "
        "the findings file (per findings-protocol.md; mark a field the finding lacks as 'not recorded')",
    ),
)
POLL_DEADLINE_SECONDS = 3.0
POLL_INTERVAL_SECONDS = 0.05
LOG_PATH = (
    Path.home() / ".local" / "share" / "claudefiles" / "decision-context-check.log"
)

log = logging.getLogger("decision-context-check")


def setup_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOG_PATH, maxBytes=512_000, backupCount=1)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.handlers = [handler]
    log.setLevel(logging.INFO)


def question_kind(tool_input: dict) -> QuestionKind | None:
    questions = [q.get("question", "") for q in tool_input.get("questions", [])]
    return next(
        (k for k in QUESTION_KINDS if any(k.trigger.search(q) for q in questions)),
        None,
    )


def wait_for_reply_text(transcript: Path, tool_use_id: str) -> str | None:
    """Return the reply text before tool_use_id once its tool_use block is on disk.

    Returns None if the block doesn't parse out of the transcript before the deadline.
    """
    deadline = time.monotonic() + POLL_DEADLINE_SECONDS
    while time.monotonic() < deadline:
        entries = parse_lines(transcript.read_text(encoding="utf-8", errors="replace"))
        text = reply_text_before(entries, tool_use_id)
        if text is not None:
            return text
        time.sleep(POLL_INTERVAL_SECONDS)
    return None


def parse_lines(text: str) -> list[dict]:
    """Parse JSONL, skipping lines that don't parse; the last one may still be mid-write."""
    entries = []
    for line in text.splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def is_turn_boundary(entry: dict) -> bool:
    """A real user prompt or a tool result; meta entries (loaded skill text) are not."""
    return (
        entry.get("type") == "user"
        and not entry.get("isMeta")
        and not entry.get("isSidechain")
    )


def reply_text_before(entries: list[dict], tool_use_id: str) -> str | None:
    """Join the assistant text blocks between the last turn boundary and the tool_use.

    Returns None when no assistant entry carries tool_use_id as a tool_use block.
    """
    end = next(
        (
            i
            for i, entry in enumerate(entries)
            if entry.get("type") == "assistant"
            and any(block.get("id") == tool_use_id for block in content_blocks(entry))
        ),
        None,
    )
    if end is None:
        return None
    texts: list[str] = []
    for entry in reversed(entries[:end]):
        if is_turn_boundary(entry):
            break
        if entry.get("type") == "assistant" and not entry.get("isSidechain"):
            texts.extend(
                b.get("text", "")
                for b in content_blocks(entry)
                if b.get("type") == "text"
            )
    return "\n".join(reversed(texts))


def content_blocks(entry: dict) -> list[dict]:
    content = entry.get("message", {}).get("content")
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict)]


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def main() -> int:
    payload = json.load(sys.stdin)
    if payload.get("tool_name") != "AskUserQuestion":
        return 0
    kind = question_kind(payload.get("tool_input", {}))
    if kind is None:
        return 0

    setup_logging()
    tool_use_id = payload.get("tool_use_id", "")
    transcript = Path(payload.get("transcript_path", ""))
    text = None
    if tool_use_id and transcript.is_file():
        text = wait_for_reply_text(transcript, tool_use_id)
    if text is None:
        log.warning(
            "allowing: tool_use %r not found in transcript %s within %ss",
            tool_use_id,
            transcript,
            POLL_DEADLINE_SECONDS,
        )
        return 0

    missing = [
        name for name, pattern in kind.markers.items() if not pattern.search(text)
    ]
    if not missing:
        return 0

    log.info(
        "denied %s (%s): reply text missing %s",
        tool_use_id,
        kind.name,
        ", ".join(missing),
    )
    deny(
        f"The user can't see the reasoning for this {kind.name}. Your reply text since the last tool "
        f"result is missing: {', '.join(missing)}. {kind.fix} as plain reply text, then ask again. "
        "Text in a file, including one you just wrote or read, doesn't count; tool inputs and results "
        "aren't shown to the user."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
