"""The confirmation prompt every command that changes several things asks before acting."""

import sys

from ado_api.exit_codes import EXIT_FAILURE, EXIT_INTERRUPTED


def confirm_or_exit(question: str, *, yes: bool) -> None:
    """Return if *yes* (``--yes``) or the user answers ``y``; otherwise exit before anything changes.

    Any other answer, or a closed stdin (no terminal, no ``--yes``), exits 1; Ctrl-C exits 130.
    The prompt goes to stderr, and callers print a ``--json`` payload only after it, so a
    declined ``--json`` run leaves stdout empty.
    """
    if yes:
        return
    print(f"\n{question} [y/N] ", end="", file=sys.stderr, flush=True)
    try:
        answer = input()
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(EXIT_INTERRUPTED)
    except EOFError:
        answer = ""
    if answer.strip().lower() != "y":
        print("Aborted.", file=sys.stderr)
        sys.exit(EXIT_FAILURE)
