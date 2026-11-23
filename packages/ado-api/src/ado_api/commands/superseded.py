"""Detect builds waiting at a stage gate that a newer build of the same pipeline supersedes.

A build deploys its whole pipeline at its commit, so when several master merges queue
builds of one pipeline, only the newest is worth approving: approving an older one after
it rolls the stage back. "Newer" is by commit ancestry (its commit contains the other's),
asked of ADO for the build's own repository. A group ancestry can't order (a commit ADO
can't resolve, or diverged history) is reported as unordered and supersedes nothing:
queue time is no substitute, since re-running an old build queues it after newer ones.
Builds are only compared within one (pipeline definition, source branch) group.

What prod runs now is the build with the latest ``prod=<timestamp>`` tag, which the deploy
job sets as its first step (in New York wall-clock time).
"""

import sys
from collections.abc import Callable
from datetime import datetime
from functools import cache
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from ado_api.tags import TAG_PROD_RE

from ado_api.az_client import ADO_API_VERSION, AdoApiError, AdoContext, call_ado_api
from ado_api.commands.builds import SHORT_SHA_LEN, fetch_timeline

# tag_pipeline_run.py writes prod= tags in New York wall-clock time, with no offset.
_TAG_TIMEZONE = ZoneInfo("America/New_York")

# (repository ID, commit, descendant) -> whether commit is an ancestor of descendant, or None when unknown.
AncestryCheck = Callable[[str, str, str], bool | None]


class BuildCommit(BaseModel):
    """A build reduced to what ordering it by commit needs: its pipeline, branch, repository and commit."""

    build_id: int
    pipeline_id: int
    pipeline_name: str
    repository_id: str
    source_branch: str
    source_version: str
    queue_time: str

    @classmethod
    def from_api(cls, build: dict[str, Any]) -> "BuildCommit":
        definition = build.get("definition") or {}
        return cls(
            build_id=int(build["id"]),
            pipeline_id=int(definition.get("id", 0)),
            pipeline_name=str(definition.get("name", "")),
            repository_id=str((build.get("repository") or {}).get("id", "")),
            source_branch=str(build.get("sourceBranch", "")),
            source_version=str(build.get("sourceVersion") or ""),
            queue_time=str(build.get("queueTime") or ""),
        )


class Supersession(BaseModel):
    """Which pending builds a newer one supersedes, which couldn't be ordered, and which weren't checked.

    *unchecked* holds builds left out because their gate lookup failed.
    """

    superseded: dict[int, int]
    unordered: list[int]
    unchecked: list[int] = []


def ado_is_ancestor(ctx: AdoContext) -> AncestryCheck:
    """An ancestry check backed by ADO's merge-bases API; each commit pair is asked once."""

    @cache
    def check(repository_id: str, commit: str, descendant: str) -> bool | None:
        url = (
            f"{ctx.config.base_url}/_apis/git/repositories/{repository_id}/commits/{descendant}"
            f"/mergebases?otherCommitId={commit}&api-version={ADO_API_VERSION}"
        )
        pair = f"{commit[:SHORT_SHA_LEN]} and {descendant[:SHORT_SHA_LEN]}"
        try:
            data = call_ado_api("GET", url, pat=ctx.pat)
        except AdoApiError as exc:
            print(f"Warning: can't order {pair} by ancestry: {exc}", file=sys.stderr)
            return None
        if data is None:
            print(f"Warning: can't order {pair} by ancestry: empty response", file=sys.stderr)
            return None
        bases = {str(c.get("commitId", "")).lower() for c in data.get("value", [])}
        return commit.lower() in bases

    return check


def _newest(group: list[BuildCommit], is_ancestor: AncestryCheck) -> BuildCommit | None:
    """The build whose commit contains every other build's commit, or None if no commit does."""
    for candidate in group:
        if all(
            other is candidate
            or other.source_version == candidate.source_version
            or is_ancestor(candidate.repository_id, other.source_version, candidate.source_version) is True
            for other in group
        ):
            # Same-commit rebuilds tie on ancestry; the latest queued of them wins.
            tied = [b for b in group if b.source_version == candidate.source_version]
            return max(tied, key=lambda b: b.queue_time)
    return None


def find_superseded(builds: list[BuildCommit], is_ancestor: AncestryCheck) -> Supersession:
    """Map each superseded build ID to the newest build in its group; list groups ancestry couldn't order."""
    groups: dict[tuple[int, str], list[BuildCommit]] = {}
    for build in builds:
        groups.setdefault((build.pipeline_id, build.source_branch), []).append(build)

    superseded: dict[int, int] = {}
    unordered: list[int] = []
    for group in groups.values():
        if len(group) < 2:
            continue
        newest = _newest(group, is_ancestor)
        if newest is None:
            unordered.extend(b.build_id for b in group)
            continue
        superseded |= {b.build_id: newest.build_id for b in group if b is not newest}
    return Supersession(superseded=superseded, unordered=sorted(unordered))


def _prod_deploy_time(build: dict[str, Any]) -> datetime | None:
    """When the build deployed to prod, from its ``prod=`` tag; an untimezoned tag is New York wall clock."""
    for tag in build.get("tags") or []:
        if m := TAG_PROD_RE.match(tag):
            deployed = datetime.fromisoformat(m.group(1))
            return deployed if deployed.tzinfo else deployed.replace(tzinfo=_TAG_TIMEZONE)
    return None


def latest_prod_deploy(builds: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The build among *builds* that deployed to prod most recently, by its ``prod=`` tag."""
    deployed = [(when, b) for b in builds if (when := _prod_deploy_time(b)) is not None]
    return max(deployed, key=lambda pair: pair[0])[1] if deployed else None


def pending_gate_stage(ctx: AdoContext, build_id: int) -> str | None:
    """Return the identifier of the stage whose approval gate this build is waiting on, if any."""
    return waiting_stage(fetch_timeline(ctx, build_id))


def waiting_stage(records: list[dict[str, Any]]) -> str | None:
    """The identifier of the stage whose approval gate these timeline *records* are waiting on, if any."""
    by_id = {r.get("id"): r for r in records}
    for record in records:
        if record.get("type") != "Checkpoint.Approval" or record.get("state") == "completed":
            continue
        parent = by_id.get(record.get("parentId"))
        while parent is not None and parent.get("type") != "Stage":
            parent = by_id.get(parent.get("parentId"))
        if parent is not None:
            return parent.get("identifier") or parent.get("name") or None
    return None
