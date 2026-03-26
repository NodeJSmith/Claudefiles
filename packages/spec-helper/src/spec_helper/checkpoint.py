"""Checkpoint file I/O for the orchestrate skill.

Reads and writes the `.orchestrate-state.md` file with validated schema.
The checkpoint uses a markdown format with a key-value header and
append-only verdict blocks.

Format:
    # Orchestration State

    feature_dir: design/specs/008-foo
    tmpdir: /tmp/claude-mine-orchestrate-abc123
    visual_skip: false
    dev_server_url: http://localhost:3000
    warn_counter: 0
    last_completed_wp: WP02
    started_at: 2026-03-25T14:30:00
    base_commit: a1b2c3d

    ## Verdicts

    ### WP01 — Set up data model
    verdict: PASS
    commit: d4e5f6a

    ### WP02 — Implement service layer
    verdict: WARN
    commit: b7c8d9e
    notes: test coverage low
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

CHECKPOINT_FILENAME = ".orchestrate-state.md"
CHECKPOINT_VERSION = 1

REQUIRED_HEADER_FIELDS = frozenset(
    {
        "feature_dir",
        "tmpdir",
        "visual_skip",
        "dev_server_url",
        "warn_counter",
        "last_completed_wp",
        "started_at",
        "base_commit",
    }
)

OPTIONAL_HEADER_FIELDS = frozenset(
    {
        "version",
        "current_wp",
        "current_wp_status",
    }
)

ALL_HEADER_FIELDS = REQUIRED_HEADER_FIELDS | OPTIONAL_HEADER_FIELDS

VALID_VERDICTS = frozenset({"PASS", "WARN", "FAIL", "BLOCKED"})
VALID_CURRENT_WP_STATUSES = frozenset({"retry_pending", "blocked", "stopped"})

BOOL_MAP = {"true": True, "false": False}


@dataclass(frozen=True)
class Verdict:
    wp_id: str
    title: str
    verdict: str
    commit: str
    notes: str = ""


@dataclass(frozen=True)
class CheckpointState:
    feature_dir: str
    tmpdir: str
    visual_skip: bool
    dev_server_url: str
    warn_counter: int
    last_completed_wp: str
    started_at: str
    base_commit: str
    version: int = CHECKPOINT_VERSION
    current_wp: str = ""
    current_wp_status: str = ""
    verdicts: tuple[Verdict, ...] = ()


def checkpoint_path(feature_dir: Path) -> Path:
    """Return the checkpoint file path for a feature directory."""
    return feature_dir / "tasks" / CHECKPOINT_FILENAME


def read_checkpoint(path: Path) -> CheckpointState:
    """Read and validate a checkpoint file. Raises ValueError on invalid format."""
    if not path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {path}")

    text = path.read_text()
    header, verdicts = _parse_checkpoint(text)
    _validate_header(header)

    return CheckpointState(
        feature_dir=header["feature_dir"],
        tmpdir=header["tmpdir"],
        visual_skip=_parse_bool(header["visual_skip"]),
        dev_server_url=header["dev_server_url"],
        warn_counter=_parse_int(header["warn_counter"], "warn_counter"),
        last_completed_wp=header["last_completed_wp"],
        started_at=header["started_at"],
        base_commit=header["base_commit"],
        version=_parse_int(header.get("version", str(CHECKPOINT_VERSION)), "version"),
        current_wp=header.get("current_wp", ""),
        current_wp_status=header.get("current_wp_status", ""),
        verdicts=tuple(verdicts),
    )


def write_checkpoint(state: CheckpointState, path: Path) -> None:
    """Write a full checkpoint file atomically."""
    text = _render_checkpoint(state)
    _atomic_write_text(text, path)


def add_verdict(path: Path, verdict: Verdict) -> None:
    """Add a verdict to an existing checkpoint file.

    Reads the full checkpoint, adds the verdict, and rewrites atomically.
    This avoids format drift from mixed append/rewrite strategies.
    """
    _validate_verdict(verdict)
    if not path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {path}")

    state = read_checkpoint(path)
    state = replace(state, verdicts=(*state.verdicts, verdict))
    write_checkpoint(state, path)


def update_header(path: Path, **updates: Any) -> None:
    """Update specific header fields in an existing checkpoint file.

    Rewrites the header with updated values, preserves verdicts section.
    """
    if not path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {path}")

    state = read_checkpoint(path)

    replacements: dict[str, Any] = {}
    for key, value in updates.items():
        if key not in ALL_HEADER_FIELDS:
            raise ValueError(
                f"Cannot update field '{key}' via update_header. "
                f"Updatable fields: {', '.join(sorted(ALL_HEADER_FIELDS))}"
            )
        replacements[key] = value

    state = replace(state, **replacements)

    write_checkpoint(state, path)


def delete_checkpoint(path: Path) -> bool:
    """Delete checkpoint file if it exists. Returns True if deleted."""
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def state_to_dict(state: CheckpointState) -> dict[str, Any]:
    """Convert checkpoint state to a JSON-serializable dict."""
    return {
        "version": state.version,
        "feature_dir": state.feature_dir,
        "tmpdir": state.tmpdir,
        "visual_skip": state.visual_skip,
        "dev_server_url": state.dev_server_url,
        "warn_counter": state.warn_counter,
        "last_completed_wp": state.last_completed_wp,
        "started_at": state.started_at,
        "base_commit": state.base_commit,
        "current_wp": state.current_wp,
        "current_wp_status": state.current_wp_status,
        "verdicts": [
            {
                "wp_id": v.wp_id,
                "title": v.title,
                "verdict": v.verdict,
                "commit": v.commit,
                "notes": v.notes,
            }
            for v in state.verdicts
        ],
    }


# --- Internal helpers ---


def _parse_checkpoint(text: str) -> tuple[dict[str, str], list[Verdict]]:
    """Parse checkpoint text into header dict and verdict list."""
    header: dict[str, str] = {}
    verdicts: list[Verdict] = []

    # Split on ## Verdicts
    parts = re.split(r"^## Verdicts\s*$", text, maxsplit=1, flags=re.MULTILINE)
    header_text = parts[0]
    verdicts_text = parts[1] if len(parts) > 1 else ""

    # Parse header key-value pairs
    for line in header_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if match:
            header[match.group(1)] = match.group(2).strip()

    # Parse verdict blocks
    verdict_blocks = re.split(r"^### ", verdicts_text, flags=re.MULTILINE)
    for block in verdict_blocks:
        block = block.strip()
        if not block:
            continue

        # First line: "WP01 — Set up data model"
        lines = block.splitlines()
        title_match = re.match(r"^(WP\d+)\s*[—–-]\s*(.+)$", lines[0])
        if not title_match:
            continue

        wp_id = title_match.group(1)
        title = title_match.group(2).strip()
        fields: dict[str, str] = {}

        for line in lines[1:]:
            kv = re.match(r"^([a-z_]+):\s*(.*)$", line.strip())
            if kv:
                fields[kv.group(1)] = kv.group(2).strip()

        verdict_val = fields.get("verdict", "")
        commit_val = fields.get("commit", "")

        if not verdict_val or verdict_val not in VALID_VERDICTS:
            raise ValueError(
                f"Malformed verdict block for {wp_id}: "
                f"invalid verdict '{verdict_val}' "
                f"(expected one of: {', '.join(sorted(VALID_VERDICTS))})"
            )
        if not commit_val:
            raise ValueError(
                f"Malformed verdict block for {wp_id}: missing commit field"
            )

        verdicts.append(
            Verdict(
                wp_id=wp_id,
                title=title,
                verdict=verdict_val,
                commit=commit_val,
                notes=fields.get("notes", ""),
            )
        )

    return header, verdicts


def _validate_header(header: dict[str, str]) -> None:
    """Validate required header fields are present."""
    missing = REQUIRED_HEADER_FIELDS - set(header.keys())
    if missing:
        raise ValueError(
            f"Checkpoint missing required fields: {', '.join(sorted(missing))}"
        )

    unknown = set(header.keys()) - ALL_HEADER_FIELDS
    if unknown:
        import sys

        print(
            f"warning: checkpoint has unknown fields: {', '.join(sorted(unknown))} "
            f"(may be from a newer version — ignoring)",
            file=sys.stderr,
        )

    status = header.get("current_wp_status", "")
    if status and status not in VALID_CURRENT_WP_STATUSES:
        raise ValueError(
            f"Invalid current_wp_status: '{status}'. "
            f"Must be one of: {', '.join(sorted(VALID_CURRENT_WP_STATUSES))}"
        )

    version = header.get("version")
    if version and _parse_int(version, "version") > CHECKPOINT_VERSION:
        raise ValueError(
            f"Checkpoint version {version} is newer than supported version {CHECKPOINT_VERSION}"
        )


def _validate_verdict(verdict: Verdict) -> None:
    """Validate a verdict before appending."""
    if verdict.verdict not in VALID_VERDICTS:
        raise ValueError(
            f"Invalid verdict '{verdict.verdict}'. Must be one of: {', '.join(sorted(VALID_VERDICTS))}"
        )
    if not re.match(r"^WP\d+$", verdict.wp_id):
        raise ValueError(f"Invalid WP ID: '{verdict.wp_id}'")


def _parse_bool(value: str) -> bool:
    lower = value.lower()
    if lower not in BOOL_MAP:
        raise ValueError(f"Invalid boolean value: '{value}' (expected true/false)")
    return BOOL_MAP[lower]


def _parse_int(value: str, field_name: str) -> int:
    try:
        return int(value)
    except ValueError as e:
        raise ValueError(f"Invalid integer for {field_name}: '{value}'") from e


def _render_checkpoint(state: CheckpointState) -> str:
    """Render a full checkpoint file from state."""
    lines = [
        "# Orchestration State",
        "",
        f"version: {state.version}",
        f"feature_dir: {state.feature_dir}",
        f"tmpdir: {state.tmpdir}",
        f"visual_skip: {'true' if state.visual_skip else 'false'}",
        f"dev_server_url: {state.dev_server_url}",
        f"warn_counter: {state.warn_counter}",
        f"last_completed_wp: {state.last_completed_wp}",
        f"started_at: {state.started_at}",
        f"base_commit: {state.base_commit}",
    ]

    if state.current_wp:
        lines.append(f"current_wp: {state.current_wp}")
        lines.append(f"current_wp_status: {state.current_wp_status}")

    lines.append("")
    lines.append("## Verdicts")

    for verdict in state.verdicts:
        lines.append(_render_verdict_block(verdict).rstrip())

    return "\n".join(lines) + "\n"


def _render_verdict_block(verdict: Verdict) -> str:
    """Render a single verdict block."""
    lines = [
        "",
        f"### {verdict.wp_id} — {verdict.title}",
        f"verdict: {verdict.verdict}",
        f"commit: {verdict.commit}",
    ]
    if verdict.notes:
        lines.append(f"notes: {verdict.notes}")
    return "\n".join(lines) + "\n"


def _atomic_write_text(text: str, target: Path) -> None:
    """Write text to a file atomically via temp file + os.replace.

    Note: filesystem.py has atomic_write for frontmatter.Post objects.
    This variant handles plain text, keeping the same safety pattern.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=target.parent, delete=False, suffix=".md"
        ) as tmp:
            tmp.write(text)
            tmp_path = tmp.name
        os.replace(tmp_path, target)
    except Exception:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
