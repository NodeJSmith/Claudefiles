"""Regenerate the help golden files: ``uv run python tests/regen_golden.py`` from packages/ado-api."""

from pathlib import Path

from test_cli import render_help

GOLDEN_DIR = Path(__file__).parent / "golden"
GOLDENS = {
    "help_root.txt": [],
    "help_builds.txt": ["builds"],
    "help_logs.txt": ["logs"],
    "help_pr.txt": ["pr"],
    "help_work_item.txt": ["work-item"],
    "help_pipeline.txt": ["pipeline"],
}

if __name__ == "__main__":
    for name, path in GOLDENS.items():
        (GOLDEN_DIR / name).write_text(render_help(path) + "\n")
        print(f"wrote {name}")
