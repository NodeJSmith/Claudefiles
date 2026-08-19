"""Shared test fixtures for ado-api."""

from typing import Any

from ado_api.az_client import AdoConfig, AdoContext

# Standard fake org/project/PAT for command-layer tests (test_builds, test_logs,
# test_pr, test_work_item). The project name deliberately contains a space so it
# exercises AdoConfig.project_encoded's %20 substitution for any test that happens
# to inspect a built URL.
FAKE_CONFIG = AdoConfig(
    organization="https://dev.azure.com/myorg", project="My Project"
)
FAKE_PAT = "fake-pat-token"
FAKE_CTX = AdoContext(config=FAKE_CONFIG, pat=FAKE_PAT)
FAKE_CTX_WITH_REPO = AdoContext(config=FAKE_CONFIG, pat=FAKE_PAT, repo="my-repo")

# Standard fake config for CLI-layer tests (test_cli, test_entrypoint_pin,
# test_file_args, test_parse_args) that only need an AdoConfig to stub
# get_ado_config — no PAT/context construction involved at this layer.
FAKE_CLI_CONFIG = AdoConfig(
    organization="https://dev.azure.com/testorg", project="TestProject"
)


def _make_timeline_record(
    *,
    order: int = 1,
    record_type: str = "Task",
    name: str = "Build",
    result: str = "succeeded",
    log_id: int | None = 10,
    error_count: int = 0,
    warning_count: int = 0,
    start_time: str | None = "2026-03-13T10:00:00Z",
    finish_time: str | None = "2026-03-13T10:01:30Z",
    issues: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "order": order,
        "type": record_type,
        "name": name,
        "result": result,
        "errorCount": error_count,
        "warningCount": warning_count,
        "startTime": start_time,
        "finishTime": finish_time,
    }
    if log_id is not None:
        record["log"] = {"id": log_id}
    if issues is not None:
        record["issues"] = issues
    return record


def _timeline_response(*records: dict[str, Any]) -> dict[str, Any]:
    return {"records": list(records)}


def _make_ctx() -> AdoContext:
    """Fake AdoContext (TestOrg/TestProject, no repo) shared by missed_prod and retry_stage tests."""
    return AdoContext(
        config=AdoConfig(
            organization="https://dev.azure.com/TestOrg", project="TestProject"
        ),
        pat="fake-pat",
    )
