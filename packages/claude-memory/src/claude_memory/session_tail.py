#!/usr/bin/env python3
"""Recover a prior session's tail for fast resume.

Powers two things:
  - the ``cm-session-tail`` CLI (invoked by the mine-resume skill), and
  - the SessionStart context injection's "unresolved decision" warning
    (``memory_context.py``).

The one thing on-disk artifacts can never tell you is whether the prior session
stopped on a decision the user never made — an AskUserQuestion that was rejected,
interrupted, or simply left open. Reading git/task state and assuming "done" is
how a session ships work the user was still deciding about. This module reads the
raw transcript JSONL to recover exactly that signal.

Why a raw-cwd slug instead of ``get_project_key``: Claude Code writes each
session's transcript into ``~/.claude/projects/<slug>/`` where the slug is the
RAW cwd (``/`` ``.`` ``:`` → ``-``), INCLUDING any ``/.claude/worktrees/<name>``
segment. ``get_project_key`` deliberately normalizes that suffix away so worktree
sessions share a DB project key with the base repo — correct for the DB, wrong
for locating files. So we encode the raw cwd here.
"""

import argparse
import os
import sys
from collections import deque
from pathlib import Path

from claude_memory.content import (
    extract_text_content,
    is_task_notification,
    is_teammate_message,
    is_tool_result,
)
from claude_memory.db import DEFAULT_PROJECTS_DIR
from claude_memory.parsing import (
    extract_session_metadata,
    parse_all_with_uuids,
    parse_lines_with_uuids,
)

# A genuinely answered AskUserQuestion produces a tool_result whose text begins
# "Your questions have been answered: …"; we match the stable substring. A
# rejection ("The user doesn't want to proceed…"), an interrupt, or no result at
# all all lack it, and all mean the decision is still open. Kept lowercase — the
# call site lowercases the result text before matching.
ANSWER_MARK = "have been answered"

# Harness-injected user content that isn't a typed instruction. command/channel
# wrappers, task-notifications, and <local-command-caveat> blocks are already
# handled by extract_text_content / is_task_notification / the "<local-command-"
# prefix below; these are the remainder.
_NOISE_PREFIXES = (
    "<system-reminder>",
    "<local-command-",
    "base directory for this skill:",
)
_TEXT_CLIP = 600
# Lines of transcript tail the SessionStart hook parses — enough to catch the
# trailing AskUserQuestion + its result without reading a multi-MB file in full.
_HOOK_TAIL_LINES = 400
_DEFAULT_TAIL_EVENTS = 8  # CLI -n default


def transcript_dir(cwd: str, projects_dir: Path = DEFAULT_PROJECTS_DIR) -> Path:
    """Directory holding this cwd's transcripts (raw slug — see module docstring)."""
    slug = cwd.replace("\\", "/").replace("/", "-").replace(":", "-").replace(".", "-")
    return projects_dir / slug


def transcript_for_uuid(
    uuid: str, cwd: str | None = None, projects_dir: Path = DEFAULT_PROJECTS_DIR
) -> Path | None:
    """Locate a session's transcript file by its session id (filename stem).

    Tries the cwd's project dir first (the common case), then falls back to a
    global glob since session ids are unique.
    """
    if cwd:
        direct = transcript_dir(cwd, projects_dir) / f"{uuid}.jsonl"
        if direct.is_file():
            return direct
    matches = sorted(projects_dir.glob(f"*/{uuid}.jsonl"))
    return matches[0] if matches else None


def load_entries(path: Path) -> list[dict]:
    return list(parse_all_with_uuids(path))


def load_tail_entries(path: Path, tail_lines: int = _HOOK_TAIL_LINES) -> list[dict]:
    """Parse only the last ``tail_lines`` lines into entries with uuids.

    Sufficient for pending-question detection (a session that stalls on a question
    stalls at its end) and bounds the SessionStart hook, which would otherwise
    parse multi-MB transcripts in full on every startup. Not for the CLI tail
    view, which needs a possibly-early last instruction — use load_entries there.
    """
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = deque(fh, maxlen=tail_lines)
    return list(parse_lines_with_uuids(lines))


def clip(text: str, limit: int = _TEXT_CLIP) -> str:
    """Collapse whitespace to one line and truncate — for compact tail display;
    this deliberately flattens code blocks and lists."""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + " […]"


def _is_main_chain(entry: dict) -> bool:
    return not entry.get("isSidechain", False)


def typed_instruction(entry: dict) -> str | None:
    """Return the user's typed text, or None if this 'user' entry isn't a real instruction.

    Filters tool-result echoes, task-notifications, teammate messages, and
    harness-injected noise (interrupt markers, system reminders, skill bodies)
    so the recovered "last instruction" is what the user actually typed.
    """
    if entry.get("type") != "user":
        return None
    content = entry.get("message", {}).get("content")
    if (
        is_tool_result(content)
        or is_task_notification(content)
        or is_teammate_message(content)
    ):
        return None
    text, _, _, _ = extract_text_content(content)
    if not text:
        return None
    low = text.lstrip().lower()
    if "request interrupted" in low or low.startswith(_NOISE_PREFIXES):
        return None
    return text


def find_pending_question(entries: list[dict]) -> dict | None:
    """The last main-chain AskUserQuestion with no genuine answer, or None.

    Returns the tool_use ``input`` payload (``{"questions": [...]}``) when the
    prior session ended on a decision the user never resolved.
    """
    # Map every tool_use_id to its result *text*, to distinguish a real answer
    # from a rejection / interrupt / missing result. We scan all entries (sidechain
    # included) here — a tool_result resolves its id wherever it lives — but only
    # main-chain questions are considered below. extract_text_content unwraps both
    # string and list-of-blocks bodies (str(body) would match the marker only by
    # accident).
    results: dict[str, str] = {}
    for entry in entries:
        if entry.get("type") != "user":
            continue
        content = entry.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                text, _, _, _ = extract_text_content(block.get("content"))
                results[block.get("tool_use_id")] = text

    last = None
    for entry in entries:
        if not _is_main_chain(entry) or entry.get("type") != "assistant":
            continue
        content = entry.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_use"
                and block.get("name") == "AskUserQuestion"
            ):
                last = (block.get("id"), block.get("input", {}))

    if not last:
        return None
    tool_id, payload = last
    if ANSWER_MARK in results.get(tool_id, "").lower():
        return None
    return payload


def last_typed_instruction(entries: list[dict]) -> str | None:
    for entry in reversed(entries):
        text = typed_instruction(entry)
        if text:
            return text
    return None


def last_assistant_text(entries: list[dict]) -> str | None:
    for entry in reversed(entries):
        if entry.get("type") == "assistant":
            text, _, _, _ = extract_text_content(
                entry.get("message", {}).get("content")
            )
            if text:
                return text
    return None


def build_tail(entries: list[dict], k: int) -> list[tuple[str, str]]:
    """Last K main-chain events as (kind, body). One assistant entry can yield
    several events (its text plus each tool_use); K bounds the output, not input."""
    if k <= 0:
        return []
    events: list[tuple[str, str]] = []
    for entry in entries:
        if not _is_main_chain(entry):
            continue
        kind = entry.get("type")
        content = entry.get("message", {}).get("content")
        if kind == "user":
            text = typed_instruction(entry)
            if text:
                events.append(("user", clip(text)))
        elif kind == "assistant":
            text, _, _, _ = extract_text_content(content)
            if text:
                events.append(("assistant", clip(text)))
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        events.append(("tool", block.get("name", "?")))
    return events[-k:]


def format_pending_block(payload: dict, *, for_injection: bool = False) -> str:
    """Render a pending-question payload for the CLI (plain) or the hook (markdown)."""
    lines: list[str] = []
    if for_injection:
        lines.append("## ⚠ Unresolved Decision From Prior Session")
        lines.append(
            "The previous session stopped at an AskUserQuestion the user never answered "
            "(rejected, interrupted, or left open — not resolved). Surface it and let the "
            "user decide; do not act on the work it gates or answer it yourself."
        )
        for q in payload.get("questions", []):
            lines.append(f"- **Q:** {q.get('question', '')}")
            for opt in q.get("options", []):
                lines.append(
                    f"  - {opt.get('label', '')}: {clip(opt.get('description', ''), 160)}"
                )
    else:
        lines.append(
            "⚠ PENDING QUESTION — prior session stopped at an UNANSWERED AskUserQuestion."
        )
        lines.append(
            "  Surface this to the user. Do NOT answer it or act on it yourself."
        )
        for q in payload.get("questions", []):
            lines.append(f"  Q: {q.get('question', '')}")
            for i, opt in enumerate(q.get("options", []), 1):
                desc = clip(opt.get("description", ""), 140)
                lines.append(f"     {i}. {opt.get('label', '')} — {desc}")
    return "\n".join(lines)


def list_transcripts(pdir: Path) -> list[Path]:
    if not pdir.is_dir():
        return []
    files = [p for p in pdir.glob("*.jsonl") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def resolve_target(pdir: Path, selector: str | None) -> Path | None:
    """Pick the transcript to show.

    With a selector, match by session-id substring. Without one, assume this runs
    inside the live session (as the mine-resume skill does): the newest file by
    mtime is the current session, so the prior session is the second-newest.
    Invoked outside an active session this is off by one — pass a selector there.
    """
    sessions = list_transcripts(pdir)
    if not sessions:
        return None
    if selector:
        for p in sessions:
            if selector in p.stem:
                return p
        return None
    return sessions[1] if len(sessions) >= 2 else None


def first_typed_preview(path: Path) -> str:
    for entry in load_entries(path):
        text = typed_instruction(entry)
        if text:
            return clip(text, 90)
    return "(no user message)"


def emit(path: Path, k: int) -> int:
    entries = load_entries(path)
    if not entries:
        print(f"cm-session-tail: transcript is empty: {path}", file=sys.stderr)
        return 1
    meta = extract_session_metadata(entries)
    sid = next((e.get("sessionId") for e in entries if e.get("sessionId")), path.stem)

    print(f"RESUME — prior session {sid[:8]}")
    print(f"  transcript:  {path}")
    print(f"  last active: {meta.get('ended_at') or 'unknown'}")
    print(f"  branch:      {meta.get('git_branch') or 'unknown'}")
    print()

    pending = find_pending_question(entries)
    if pending:
        print(format_pending_block(pending))
        print()

    instr = last_typed_instruction(entries)
    if instr:
        print("LAST USER INSTRUCTION:")
        print(f"  {clip(instr)}")
        print()

    tail = build_tail(entries, k)
    if tail:
        print(f"TAIL (last {len(tail)} events):")
        tags = {"user": "user", "assistant": "asst", "tool": "tool"}
        for kind, body in tail:
            print(f"  [{tags[kind]}] {body}")
        print()

    if not pending:
        last = last_assistant_text(entries)
        if last:
            print("LAST ASSISTANT MESSAGE (excerpt):")
            print(f"  {clip(last)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="cm-session-tail",
        description="Print the tail of a prior session's transcript for fast resume.",
    )
    ap.add_argument("selector", nargs="?", help="session id or substring to target")
    ap.add_argument("--list", action="store_true", help="list sessions and exit")
    ap.add_argument(
        "--cwd", default=os.getcwd(), help="derive project dir from this path"
    )
    ap.add_argument(
        "-n",
        type=int,
        default=_DEFAULT_TAIL_EVENTS,
        help="number of tail events to show",
    )
    args = ap.parse_args()
    if args.n < 1:
        print("cm-session-tail: -n must be >= 1", file=sys.stderr)
        return 2

    pdir = transcript_dir(args.cwd)
    if not pdir.is_dir():
        print(
            f"cm-session-tail: no project dir for {args.cwd}\n  expected: {pdir}",
            file=sys.stderr,
        )
        return 2

    if args.list:
        sessions = list_transcripts(pdir)
        if not sessions:
            print("cm-session-tail: no sessions found", file=sys.stderr)
            return 2
        print(f"Sessions in {pdir.name} (newest first; newest is the current session):")
        for i, p in enumerate(sessions):
            marker = "  <- current" if i == 0 else ""
            print(f"  {p.stem[:8]}  {first_typed_preview(p)}{marker}")
        return 0

    target = resolve_target(pdir, args.selector)
    if target is None:
        if args.selector:
            print(
                f"cm-session-tail: no session matching '{args.selector}'",
                file=sys.stderr,
            )
        else:
            print(
                "cm-session-tail: no prior session found (only the current one exists)",
                file=sys.stderr,
            )
        return 2

    return emit(target, args.n)


if __name__ == "__main__":
    sys.exit(main())
