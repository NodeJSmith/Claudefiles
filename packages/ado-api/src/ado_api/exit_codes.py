"""Exit codes every ado-api command uses.

1 means bad usage, or the command ran and the outcome was a no: a declined prompt, a
refused approval, a build that failed. 5 means an ADO call failed, including one item of
a batch, so a script can tell "retry later" from "this didn't pass". 130 is Ctrl-C.
"""

EXIT_FAILURE = 1
EXIT_CONFIG = 2
EXIT_AUTH = 3
EXIT_INTERNAL = 4
EXIT_API_ERROR = 5
EXIT_INTERRUPTED = 130


def combined_exit_code(*codes: int) -> int:
    """The code for a command that made several checks: an ADO failure (5) outranks any other."""
    if EXIT_API_ERROR in codes:
        return EXIT_API_ERROR
    return max(codes, default=0)
