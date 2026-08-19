"""ADO build tag format — one specific organization's build-tag conventions.

These constants encode Rhyme's build-tag format (`key=value` pairs, with a handful
of legacy hyphenated formats still recognized for older builds). `builds
missed-prod`, `builds retry-stage`, and `builds approve`'s PR-tag lookup all
depend on these conventions to find the builds they operate on.

At an organization whose pipelines tag builds differently, those three commands
will find nothing — they are not broken, they simply have no matching tags to
match against. This is expected and is not a bug to report; making the tag
format configurable is deferred until a non-Rhyme org is known to need it.
"""

import re

__all__ = [
    "DEPLOYMENT_TAG_PREFIXES",
    "TAG_COMMIT_RE",
    "TAG_PROD_RE",
    "TAG_PR_RE",
    "TAG_STAGE_RE",
    "TIMESTAMP_RE",
    "format_commit_tag",
    "format_pr_tag",
    "parse_tags_to_dict",
    "pr_tag_variants",
]

TIMESTAMP_RE = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"
TAG_STAGE_RE = re.compile(rf"^stage[-=]({TIMESTAMP_RE})$")
TAG_PROD_RE = re.compile(rf"^prod[-=]({TIMESTAMP_RE})$")
TAG_PR_RE = re.compile(r"^(?:PR-|pr=)(\d+)$")
TAG_COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")

DEPLOYMENT_TAG_PREFIXES = ("stage-", "prod-", "stage=", "prod=")

_KNOWN_LEGACY_ENV_PREFIXES = ("dev-", "stage-", "prod-")


def pr_tag_variants(pr_id: str | int) -> list[str]:
    """Return every tag spelling a PR's builds may carry, newest format first.

    Builds are tagged ``pr=<id>`` today, but builds from before the migration use
    ``PR-<id>``. A lookup that queries only one format silently misses the other,
    so callers should query both and de-duplicate by build ID.

    Accepts a bare ID or either prefixed form, in any case, so a value taken
    straight from a CLI flag can be passed through without pre-cleaning.
    """
    raw = str(pr_id).strip()
    for prefix in ("PR-", "pr="):
        if raw.lower().startswith(prefix.lower()):
            raw = raw[len(prefix) :]
            break
    return [f"pr={raw}", f"PR-{raw}"]


def format_commit_tag(commit_sha: str) -> str:
    """Build the tag a Rhyme pipeline run writes for a commit, e.g. "commit=a1b2c3d4"."""
    return f"commit={commit_sha}"


def format_pr_tag(pr_id: str | int) -> str:
    """Build the tag a Rhyme pipeline run writes for a PR, e.g. "pr=49846"."""
    return f"pr={pr_id}"


def parse_tags_to_dict(tags: list[str]) -> dict[str, str]:
    """Parse all build tags into a key=value dict.

    Handles both new format (all key=value) and legacy formats:
    - "key=value" → {"key": "value"}
    - "PR-49730" → {"pr": "49730"}
    - "dev-2026-..." → {"dev": "2026-..."}
    - "27eba981" (bare hex) → {"commit": "27eba981"}
    """
    result: dict[str, str] = {}
    for tag in tags:
        if "=" in tag:
            key, _, value = tag.partition("=")
            result[key.lower()] = value
        elif tag.startswith("PR-"):
            result["pr"] = tag.removeprefix("PR-")
        elif any(tag.startswith(p) for p in _KNOWN_LEGACY_ENV_PREFIXES):
            key, _, value = tag.partition("-")
            result[key] = value
        elif TAG_COMMIT_RE.match(tag):
            result["commit"] = tag
    return result
