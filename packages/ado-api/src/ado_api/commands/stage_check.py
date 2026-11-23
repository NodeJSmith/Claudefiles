"""Check whether each release build's change has passed a Databricks stage run.

"Passed in stage" means a run of the pipeline's stage job (``<job> - stage``, in the dev
workspace) succeeded on a commit that contains the build's commit. The CI stage deploy
doesn't count: a deploy only proves the code was installed, not that it ran against data.

Each run's code is identified by its job-cluster ``build_id`` tag, and that build's commit
is checked against the release build's with ADO's merge-bases API, so no local clone is
needed. This is the one ado-api command that reads Databricks: it shells out to the
``databricks`` CLI's ``dev`` profile rather than taking a Databricks SDK dependency, since
the answer it gives is about an ADO build.

Statuses, per build, judged only over runs whose code contains the change: ``passed`` (one
succeeded), ``running`` (none succeeded, one is in progress), ``failed`` (all that finished
failed), ``no_run`` (none has tried it yet; skipped and canceled runs don't count), and
``error`` (the build couldn't be checked; the reason is in ``error``). Runs since the
commit are read newest first, in batches of ``_RUN_BATCH_SIZE``, stopping after the batch
that holds the first pass.
"""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from whenever import Instant

from ado_api.az_client import ADO_API_VERSION, AdoApiError, AdoContext, call_ado_api
from ado_api.commands.approve import _get_builds_by_id
from ado_api.commands.builds import SHORT_SHA_LEN
from ado_api.commands.superseded import AncestryCheck, BuildCommit, ado_is_ancestor
from ado_api.exit_codes import EXIT_API_ERROR, EXIT_FAILURE, combined_exit_code
from ado_api.formatting import Record, format_local_time, json_output, parse_ado_timestamp, print_table

# Stage jobs live in the dev workspace.
STAGE_JOB_PROFILE = "dev"
DATABRICKS_TIMEOUT_SECONDS = 120
# Runs fetched at once; also the thread-pool size. A pass ends the search after its batch.
_RUN_BATCH_SIZE = 8
_SUCCESS = "SUCCESS"
_ACTIVE_STATES = {"PENDING", "QUEUED", "RUNNING", "TERMINATING", "BLOCKED"}
# A real attempt that didn't pass. Anything else that isn't SUCCESS or active (SKIPPED, CANCELED,
# MAXIMUM_CONCURRENT_RUNS_REACHED, EXCLUDED, ...) never tried the change, so it doesn't count.
_FAILED_STATES = {"FAILED", "INTERNAL_ERROR", "TIMEDOUT", "SUCCESS_WITH_FAILURES", "UPSTREAM_FAILED"}
# A run in any of these states tried the change; the rest never ran it.
_ATTEMPT_STATES = {_SUCCESS} | _ACTIVE_STATES | _FAILED_STATES
_HEADERS = ("BUILD", "PIPELINE", "COMMIT", "STATUS", "RUNS_WITH_CHANGE", "LATEST")
_LATEST_COL = _HEADERS.index("LATEST")

StageStatus = Literal["passed", "running", "failed", "no_run", "error"]


class DatabricksCliError(Exception):
    """Raised when a ``databricks`` CLI call fails, times out, isn't installed, or returns an unexpected shape."""


class StageRun(Record):
    """One stage-job run that tried the build's change: its code contains the commit, and it ran."""

    run_id: int
    started: str | None
    state: str
    build_id: int
    url: str


class StageCheck(Record):
    """The stage verdict for one release build.

    *runs* holds the runs that tried the change (see :class:`StageRun`), newest first. *untagged* counts
    inspected runs with no ``build_id`` cluster tag, whose code can't be identified.
    """

    build_id: int
    status: StageStatus
    pipeline_name: str = ""
    commit: str = ""
    stage_job: str = ""
    runs: list[StageRun] = []
    inspected: int = 0
    total_since_commit: int = 0
    untagged: int = 0
    error: str | None = None


class RawRun(Record):
    """A stage-job run as read from Databricks, before its code is matched to the change."""

    run_id: int
    started: str | None
    state: str
    build_id: int | None
    url: str


class BatchMatch(Record):
    """What one batch of runs says about a change: the runs containing it, and the runs it couldn't judge."""

    matching: list[StageRun]
    untagged: int
    problems: list[str]


def stage_job_name(pipeline: str):
    """ADO pipeline ``mono-dbx-pipeline-dbt`` -> Databricks job ``dbx_pipeline_dbt - stage``."""
    return f"{pipeline.removeprefix('mono-').replace('-', '_')} - stage"


def run_databricks(*args: str):
    """Run a ``databricks`` CLI command against the dev profile and return its parsed JSON.

    ``DATABRICKS_*`` variables are dropped from the environment, because an exported
    ``DATABRICKS_HOST`` overrides ``--profile`` and would point the call at another workspace.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("DATABRICKS_")}
    cmd = ["databricks", *args, "--profile", STAGE_JOB_PROFILE, "-o", "json"]
    label = f"databricks {' '.join(args[:2])}"
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, env=env, check=False, timeout=DATABRICKS_TIMEOUT_SECONDS
        )
    except FileNotFoundError:
        msg = "databricks CLI not found"
        raise DatabricksCliError(msg) from None
    except subprocess.TimeoutExpired:
        msg = f"{label} timed out after {DATABRICKS_TIMEOUT_SECONDS}s"
        raise DatabricksCliError(msg) from None
    if proc.returncode != 0:
        msg = f"{label} exited {proc.returncode}: {proc.stderr.strip()[:300]}"
        raise DatabricksCliError(msg)
    try:
        return json.loads(proc.stdout or "null")
    except json.JSONDecodeError:
        msg = f"{label} returned non-JSON output: {proc.stdout.strip()[:200]}"
        raise DatabricksCliError(msg) from None


def as_list(value: object, label: str):
    """*value* as a list; a CLI that answers with any other shape is an error, not an empty result."""
    if value is None:
        return []
    if not isinstance(value, list):
        msg = f"{label} returned {type(value).__name__}, not a list"
        raise DatabricksCliError(msg)
    return value


def fetch_build_commits(ctx: AdoContext, build_ids: list[int]):
    """The given builds by ID; IDs ADO doesn't return are absent."""
    return {b.build_id: b for b in map(BuildCommit.from_api, _get_builds_by_id(ctx, build_ids))}


def commit_time_ms(ctx: AdoContext, repository_id: str, commit: str):
    """The commit's committer date in epoch milliseconds; no stage run before it can contain the commit."""
    url = f"{ctx.config.base_url}/_apis/git/repositories/{repository_id}/commits/{commit}?api-version={ADO_API_VERSION}"
    data = call_ado_api("GET", url, pat=ctx.pat) or {}
    date = (data.get("committer") or {}).get("date")
    if not date:
        msg = f"commit {commit[:SHORT_SHA_LEN]} has no committer date"
        raise AdoApiError(msg)
    return int(parse_ado_timestamp(date).timestamp() * 1000)


def fetch_run(run_id: int):
    """Read one run. A stage job deploys one build, so the first cluster with a ``build_id`` tag names its code."""
    d = run_databricks("jobs", "get-run", str(run_id))
    if not isinstance(d, dict):
        msg = f"databricks jobs get-run {run_id} returned {type(d).__name__}, not an object"
        raise DatabricksCliError(msg)
    tags = [(c.get("new_cluster") or {}).get("custom_tags") or {} for c in d.get("job_clusters") or []]
    build_id = next((t["build_id"] for t in tags if str(t.get("build_id", "")).isdigit()), None)
    state = d.get("state") or {}
    start_ms = d.get("start_time")
    started = Instant.from_timestamp(start_ms, unit="millisecond").format_iso(unit="second") if start_ms else None
    return RawRun(
        run_id=run_id,
        started=started,
        state=state.get("result_state") or state.get("life_cycle_state") or "UNKNOWN",
        build_id=int(build_id) if build_id else None,
        url=d.get("run_page_url") or "",
    )


def stage_status(runs: list[StageRun]):
    """Rank passed > running > failed > no_run over runs whose code contains the change."""
    states = {r.state for r in runs}
    if _SUCCESS in states:
        return "passed"
    if states & _ACTIVE_STATES:
        return "running"
    if states & _FAILED_STATES:
        return "failed"
    return "no_run"


def match_runs(ctx: AdoContext, build: BuildCommit, batch: list[RawRun], is_ancestor: AncestryCheck):
    """Sort *batch* into runs that tried *build*'s change, untagged runs, and runs that can't be judged.

    A run tried the change when its code contains *build*'s commit and it actually ran: skipped
    and canceled runs are left out, so they can't show up as the latest run.

    A run can't be judged when ADO doesn't return its build or can't answer the ancestry
    question. Those are reported rather than guessed, and the caller decides whether they matter.
    """
    tagged = [(r, r.build_id) for r in batch if r.build_id is not None]
    run_builds = fetch_build_commits(ctx, [bid for _, bid in tagged])
    matching: list[StageRun] = []
    problems: list[str] = []
    for r, bid in tagged:
        run_build = run_builds.get(bid)
        if run_build is None:
            problems.append(f"run {r.run_id} is tagged with build {bid}, which ADO doesn't return")
            continue
        contains = is_ancestor(build.repository_id, build.source_version, run_build.source_version)
        if contains is None:
            short = build.source_version[:SHORT_SHA_LEN]
            problems.append(f"can't tell whether run {r.run_id} (build {bid}) contains {short}")
        elif contains and r.state in _ATTEMPT_STATES:
            matching.append(StageRun(run_id=r.run_id, started=r.started, state=r.state, build_id=bid, url=r.url))
    return BatchMatch(matching=matching, untagged=len(batch) - len(tagged), problems=problems)


def check_build(ctx: AdoContext, build: BuildCommit, pool: ThreadPoolExecutor, is_ancestor: AncestryCheck):
    """The stage verdict for *build*. A run that can't be judged is an error unless a pass was found anyway."""
    stage_job = stage_job_name(build.pipeline_name)
    jobs = as_list(run_databricks("jobs", "list", "--name", stage_job), "databricks jobs list")
    if not jobs or not isinstance(jobs[0], dict) or "job_id" not in jobs[0]:
        msg = f"no Databricks job named {stage_job!r}"
        raise DatabricksCliError(msg)
    since = commit_time_ms(ctx, build.repository_id, build.source_version)
    listed = run_databricks("jobs", "list-runs", "--job-id", str(jobs[0]["job_id"]), "--start-time-from", str(since))
    listed_runs = as_list(listed, "databricks jobs list-runs")
    run_ids = [r["run_id"] for r in listed_runs if isinstance(r, dict) and "run_id" in r]
    runs: list[StageRun] = []
    problems: list[str] = []
    inspected = untagged = 0
    for i in range(0, len(run_ids), _RUN_BATCH_SIZE):
        batch = list(pool.map(fetch_run, run_ids[i : i + _RUN_BATCH_SIZE]))
        result = match_runs(ctx, build, batch, is_ancestor)
        inspected += len(batch)
        untagged += result.untagged
        runs += result.matching
        problems += result.problems
        if any(r.state == _SUCCESS for r in runs):
            break
    status = stage_status(runs)
    if problems and status != "passed":
        raise AdoApiError("; ".join(problems))
    for problem in problems:
        print(f"Warning: build {build.build_id}: {problem} (it passed regardless)", file=sys.stderr)
    return StageCheck(
        build_id=build.build_id,
        status=status,
        pipeline_name=build.pipeline_name,
        commit=build.source_version,
        stage_job=stage_job,
        runs=runs,
        inspected=inspected,
        total_since_commit=len(run_ids),
        untagged=untagged,
    )


def status_exit_code(status: StageStatus):
    if status == "error":
        return EXIT_API_ERROR
    if status == "passed":
        return 0
    return EXIT_FAILURE


def stage_check_exit_code(checks: list[StageCheck]):
    """5 if any build couldn't be checked, 1 if any hasn't passed in stage, else 0."""
    return combined_exit_code(*(status_exit_code(c.status) for c in checks))


def print_stage_checks(checks: list[StageCheck]):
    rows = []
    links = []
    for c in checks:
        latest = c.runs[0] if c.runs else None
        detail = f"{latest.state} {format_local_time(latest.started)}" if latest else (c.error or "-")
        rows.append((str(c.build_id), c.pipeline_name, c.commit[:SHORT_SHA_LEN], c.status, str(len(c.runs)), detail))
        links.append({_LATEST_COL: latest.url} if latest and latest.url else {})
    print_table(rows, headers=_HEADERS, links=links)
    for c in checks:
        if c.untagged:
            print(f"Note: {c.build_id}: {c.untagged} run(s) had no build_id tag and were skipped", file=sys.stderr)
        if c.status == "failed":
            print(f"{c.build_id} failed runs (errors: dbx-api run-output <run-id> --env dev):", file=sys.stderr)
            for r in c.runs:
                print(f"  {r.run_id} {format_local_time(r.started)} {r.state} {r.url}", file=sys.stderr)


def error_check(build_id: int, error: str, build: BuildCommit | None = None):
    print(f"Failed build {build_id}: {error}", file=sys.stderr)
    return StageCheck(
        build_id=build_id,
        status="error",
        pipeline_name=build.pipeline_name if build else "",
        commit=build.source_version if build else "",
        stage_job=stage_job_name(build.pipeline_name) if build else "",
        error=error,
    )


def cmd_builds_stage_check(ctx: AdoContext, build_ids: list[int], *, as_json: bool = False):
    """Report each build's stage verdict and return the exit code (see :func:`stage_check_exit_code`)."""
    unique_ids = list(dict.fromkeys(build_ids))
    found = fetch_build_commits(ctx, unique_ids)
    is_ancestor = ado_is_ancestor(ctx)
    checks: list[StageCheck] = []
    with ThreadPoolExecutor(_RUN_BATCH_SIZE) as pool:
        for build_id in unique_ids:
            build = found.get(build_id)
            if build is None:
                checks.append(error_check(build_id, "build not found"))
                continue
            try:
                checks.append(check_build(ctx, build, pool, is_ancestor))
            except (AdoApiError, DatabricksCliError) as exc:
                checks.append(error_check(build_id, str(exc), build))
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                # A response in a shape this code doesn't expect; report it for this build, keep checking the rest.
                checks.append(error_check(build_id, f"unexpected response shape: {type(exc).__name__}: {exc}", build))
    if as_json:
        json_output(checks)
    else:
        print_stage_checks(checks)
    return stage_check_exit_code(checks)
