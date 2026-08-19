"""Detect builds that deployed to stage but never made it to prod.

Relies on Rhyme's build-tag conventions (``stage=<timestamp>``,
``prod=<timestamp>``, plus the legacy hyphenated ``stage-<ts>``/``prod-<ts>``
format for builds tagged before the migration — see ``ado_api.tags``). A
build is "missed" if it has a stage tag but no prod tag. At an organization
whose pipelines tag builds differently, this command is inert: it finds
nothing rather than erroring, and prints a warning to that effect.

Missed builds are classified as:
- **ACTIONABLE** — no later build for the same pipeline reached prod,
  so the latest stage-deployed code is NOT in production.
- **superseded** — a later build for the same pipeline did reach prod,
  so the missed build's changes are already in production via that later build.
"""

import sys
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

from ado_api.az_client import ADO_API_VERSION, AdoApiError, AdoContext, call_ado_api
from ado_api.commands.builds import _get_default_branch
from ado_api.formatting import aligned_table, json_output, truncate
from ado_api.tags import DEPLOYMENT_TAG_PREFIXES, TAG_PR_RE, TAG_PROD_RE, TAG_STAGE_RE

_HEADERS = (
    "STATUS",
    "PIPELINE",
    "BUILD",
    "STAGE_DEPLOYED",
    "PR",
    "DESCRIPTION",
    "COMMIT",
)

_DEFAULT_DAYS = 14
_DEFAULT_TOP = 500


_MAX_DESCRIPTION_LEN = 60


def _builds_url(
    ctx: AdoContext,
    *,
    min_time: str,
    branch: str = "refs/heads/master",
    top: int = _DEFAULT_TOP,
) -> str:
    """Build the builds-list query URL.

    Unlike sibling modules, *branch* here already carries the ``refs/heads/``
    prefix (see the default above) -- it is not prepended separately.
    """
    return (
        f"{ctx.config.base_url}/_apis/build/builds"
        f"?api-version={ADO_API_VERSION}"
        f"&branchName={quote(branch, safe='/')}"
        f"&statusFilter=completed"
        f"&$top={top}"
        f"&minTime={min_time}"
    )


def _parse_tags(tags: list[str]) -> dict[str, str | None]:
    """Extract stage/prod timestamps and PR ID from build tags."""
    result: dict[str, str | None] = {
        "stage_time": None,
        "prod_time": None,
        "pr_id": None,
    }
    for tag in tags:
        if m := TAG_STAGE_RE.match(tag):
            result["stage_time"] = m.group(1)
        elif m := TAG_PROD_RE.match(tag):
            result["prod_time"] = m.group(1)
        elif m := TAG_PR_RE.match(tag):
            result["pr_id"] = m.group(1)
    return result


def _classify_builds(
    builds: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find builds with stage but no prod, classified as actionable or superseded."""
    parsed = []
    for b in builds:
        tags = b.get("tags", [])
        tag_info = _parse_tags(tags)
        definition = b.get("definition", {})
        parsed.append(
            {
                "build_id": b.get("id"),
                "build_number": b.get("buildNumber"),
                "pipeline_name": definition.get("name", ""),
                "pipeline_id": definition.get("id"),
                "source_version": (b.get("sourceVersion") or "")[:8],
                "finish_time": b.get("finishTime"),
                **tag_info,
            }
        )

    # Group by pipeline
    pipelines: dict[int, list[dict[str, Any]]] = {}
    skipped_no_pid = 0
    for p in parsed:
        pid = p["pipeline_id"]
        if pid is not None:
            pipelines.setdefault(pid, []).append(p)
        else:
            skipped_no_pid += 1

    if skipped_no_pid:
        print(
            f"Warning: {skipped_no_pid} build(s) skipped (missing pipeline ID)",
            file=sys.stderr,
        )

    missed: list[dict[str, Any]] = []
    for pipeline_builds in pipelines.values():
        # Sort by build_id ascending (oldest first)
        pipeline_builds.sort(key=lambda x: x["build_id"])

        # Collect builds that reached stage but not prod
        stage_no_prod = [
            pb
            for pb in pipeline_builds
            if pb["stage_time"] is not None and pb["prod_time"] is None
        ]
        if not stage_no_prod:
            continue

        # Find the latest build that reached prod (if any)
        latest_prod_build_id = max(
            (pb["build_id"] for pb in pipeline_builds if pb["prod_time"] is not None),
            default=0,
        )

        # Only the latest stage-no-prod build *after* the last prod build is actionable.
        # Everything else is superseded (by a prod build or by a newer stage build).
        latest = stage_no_prod[-1]
        for pb in stage_no_prod:
            status = (
                "ACTIONABLE"
                if pb is latest and pb["build_id"] > latest_prod_build_id
                else "superseded"
            )
            missed.append({**pb, "status": status})

    # Actionable first, then by pipeline name, then build id
    missed.sort(
        key=lambda x: (x["status"] != "ACTIONABLE", x["pipeline_name"], x["build_id"])
    )
    return missed


def _fetch_pr_titles(
    ctx: AdoContext,
    pr_ids: set[str],
) -> dict[str, str]:
    """Fetch PR titles for a set of PR IDs (serial API calls).

    ADO's Git API doesn't support batch fetch by ID, so this makes
    one API call per PR. Failed lookups are logged to stderr.
    """
    if not pr_ids or not ctx.repo:
        return {}

    titles: dict[str, str] = {}
    total = len(pr_ids)
    for idx, pr_id in enumerate(sorted(pr_ids), start=1):
        url = (
            f"{ctx.config.base_url}/_apis/git/repositories/{quote(ctx.repo, safe='')}"
            f"/pullrequests/{pr_id}?api-version={ADO_API_VERSION}"
        )
        try:
            data = call_ado_api("GET", url, pat=ctx.pat)
            title = data.get("title", "")
            titles[pr_id] = title
        except AdoApiError as exc:
            print(f"Warning: Failed to fetch PR {pr_id}: {exc}", file=sys.stderr)
        if total > 10 and idx % 10 == 0:
            print(f"Fetched {idx}/{total} PR titles...", file=sys.stderr)
    return titles


def cmd_builds_missed_prod(
    ctx: AdoContext,
    *,
    days: int = _DEFAULT_DAYS,
    top: int = _DEFAULT_TOP,
    pipeline: str | None = None,
    branch: str | None = None,
    as_json: bool = False,
) -> None:
    """Find builds that deployed to stage but not prod."""
    resolved_branch = (
        f"refs/heads/{branch}" if branch else f"refs/heads/{_get_default_branch()}"
    )
    min_time = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = _builds_url(ctx, min_time=min_time, branch=resolved_branch, top=top)
    data = call_ado_api("GET", url, pat=ctx.pat)
    builds: list[dict[str, Any]] = data.get("value", [])

    if len(builds) == top:
        print(
            f"Warning: retrieved {top} builds (API limit). Results may be incomplete."
            f" Use --top to increase or narrow --days.",
            file=sys.stderr,
        )

    # Sanity check: warn if builds exist but none have stage/prod tags
    if builds and not any(
        tag.startswith(DEPLOYMENT_TAG_PREFIXES)
        for b in builds
        for tag in b.get("tags", [])
    ):
        print(
            "Warning: no builds have stage/prod tags. This command depends on Rhyme's"
            " `stage=`/`prod=` build-tag convention — it will find nothing at an org"
            " that tags builds differently.",
            file=sys.stderr,
        )

    missed = _classify_builds(builds)

    # Optional pipeline name filter
    if pipeline:
        pipeline_lower = pipeline.lower()
        missed = [m for m in missed if pipeline_lower in m["pipeline_name"].lower()]

    # Warn early if repo is missing (before fetch attempt)
    if not ctx.repo and any(m["pr_id"] for m in missed):
        print(
            "Note: PR links and descriptions unavailable (not in a git repository). "
            "Run from a repo directory to enable.",
            file=sys.stderr,
        )

    # Fetch PR titles for missed builds
    pr_ids = {m["pr_id"] for m in missed if m["pr_id"]}
    pr_titles: dict[str, str] = {}
    if pr_ids:
        print(f"Fetching PR titles for {len(pr_ids)} PR(s)...", file=sys.stderr)
        pr_titles = _fetch_pr_titles(ctx, pr_ids)

    # Inject pr_title into each missed build for JSON output
    for m in missed:
        m["pr_title"] = pr_titles.get(m["pr_id"], "") if m["pr_id"] else ""

    if as_json:
        json_output(missed)
        return

    if not missed:
        print(f"No missed prod releases found in the last {days} days.")
        return

    actionable = [m for m in missed if m["status"] == "ACTIONABLE"]
    superseded = [m for m in missed if m["status"] == "superseded"]

    rows: list[tuple[str, ...]] = []
    links: list[dict[int, str]] = []
    for m in missed:
        pr_label = f"PR-{m['pr_id']}" if m["pr_id"] else "-"
        description = (
            truncate(m["pr_title"], _MAX_DESCRIPTION_LEN) if m["pr_title"] else "-"
        )
        rows.append(
            (
                m["status"],
                m["pipeline_name"],
                str(m["build_id"]),
                m["stage_time"] or "-",
                pr_label,
                description,
                m["source_version"] or "-",
            )
        )
        row_links: dict[int, str] = {
            # PIPELINE → build results page
            1: f"{ctx.config.base_url}/_build/results?buildId={m['build_id']}",
        }
        if m["pr_id"] and ctx.repo:
            row_links[4] = (
                f"{ctx.config.base_url}/_git/{quote(ctx.repo, safe='')}/pullrequest/{m['pr_id']}"
            )
        links.append(row_links)

    aligned_table(rows, headers=_HEADERS, links=links)
    print(
        f"\n{len(actionable)} actionable, {len(superseded)} superseded (last {days} days)"
    )
