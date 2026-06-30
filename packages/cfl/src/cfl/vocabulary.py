"""Shared verdict vocabulary for cfl.

Gate verdicts and task verdicts share a common base set today. When one set
needs to diverge (e.g., a gate-only "SCHEDULED_SKIP" verdict), extend the
relevant constant in gate.py or task.py explicitly against COMMON_VERDICTS —
the divergence becomes visible in code rather than a comment obligation.
"""

COMMON_VERDICTS: frozenset[str] = frozenset({"PASS", "WARN", "FAIL", "SKIPPED"})
