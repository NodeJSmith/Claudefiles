"""Tests for bin/gh-pr-threads: the known-noise denylist and cursor draining."""

import runpy
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "bin" / "gh-pr-threads"
# The script has no .py extension and isn't a package module, so load its namespace via runpy.
MODULE = runpy.run_path(str(SCRIPT))
noise_reason = MODULE["noise_reason"]
split_noise = MODULE["split_noise"]
drain = MODULE["drain"]

CODEX = "chatgpt-codex-connector"
CODEX_BOILERPLATE = """
### 💡 Codex Review

Here are some automated review suggestions for this pull request.

**Reviewed commit:** `1abafaf1c4`


<details> <summary>ℹ️ About Codex in GitHub</summary>
<br/>

[Your team has set up Codex to review pull requests in this repo](https://chatgpt.com/codex/cloud/settings/general). Reviews are triggered when you
- Open a pull request for review
- Mark a draft as ready
- Comment "@codex review".

If Codex has suggestions, it will comment; otherwise it will react with 👍.

</details>
"""


def node(login: str, body: str, url: str = "u") -> dict:
    return {"author": {"login": login}, "body": body, "url": url}


@pytest.mark.parametrize(
    ("login", "body", "reason"),
    [
        (
            "codecov",
            "## [Codecov](https://app.codecov.io/gh/x/y/pull/1) Report",
            "Codecov coverage report",
        ),
        (
            CODEX,
            "<!-- codex-pull-request-review-summary -->\n## Codex Review Summary",
            "Codex review status table",
        ),
        (
            CODEX,
            CODEX_BOILERPLATE,
            "Codex review boilerplate (its findings are inline threads)",
        ),
        (
            "read-the-docs-community",
            "<!-- readthedocs-1166495 -->\nDocs preview",
            "ReadTheDocs build preview",
        ),
        ("NodeJSmith", "@coderabbitai review", "review trigger command"),
        ("NodeJSmith", "  @CodeRabbitAI full review\n", "review trigger command"),
        ("NodeJSmith", "@codex security review", "review trigger command"),
        (
            "coderabbitai",
            (
                "<!-- This is an auto-generated reply by CodeRabbit -->\n"
                "<!-- CodeRabbit review command invocation: v2:ab30 -->\n<details><summary>✅ Action performed</summary>"
            ),
            "CodeRabbit review-command acknowledgement",
        ),
    ],
)
def test_known_noise_is_excluded_with_reason(
    login: str, body: str, reason: str
) -> None:
    assert noise_reason(node(login, body)) == reason


@pytest.mark.parametrize(
    ("login", "body"),
    [
        # A known bot adding real content must fall through to "kept".
        (CODEX, CODEX_BOILERPLATE + "\n**P1** `foo.py:12` drops the error"),
        (
            CODEX,
            CODEX_BOILERPLATE.replace(
                "</details>",
                "</details>\n<details><summary>P1</summary>finding</details>",
            ),
        ),
        (CODEX, "**P1** `foo.py:12` drops the error"),
        # CodeRabbit walkthrough: its pre-merge checks can report failures.
        (
            "coderabbitai",
            "<!-- This is an auto-generated comment: summarize by coderabbit.ai -->\n### ❌ Failed checks",
        ),
        (
            "coderabbitai",
            "**Actionable comments posted: 1**\n<details><summary>⚠️ Outside diff range comments (1)",
        ),
        (
            "copilot-pull-request-reviewer",
            "Copilot was unable to review this pull request because of quota.",
        ),
        # A trigger with anything else in it is a real message.
        (
            "NodeJSmith",
            "@coderabbitai review — and please look at the cache invalidation",
        ),
        # Unknown bots and formats are kept by default.
        ("some-new-bot", "<!-- some-new-bot -->\nFound 3 issues"),
    ],
)
def test_anything_not_on_the_denylist_is_kept(login: str, body: str) -> None:
    assert noise_reason(node(login, body)) is None


def test_split_noise_skips_empty_bodies_and_records_exclusions() -> None:
    nodes = [
        node("NodeJSmith", "   "),
        node("NodeJSmith", "real comment", "a"),
        node("codecov", "report", "b"),
    ]

    kept, excluded = split_noise(nodes, "issueComments")

    assert [n["url"] for n in kept] == ["a"]
    assert excluded == [
        {
            "surface": "issueComments",
            "author": "codecov",
            "url": "b",
            "reason": "Codecov coverage report",
        }
    ]


def test_drain_follows_cursor_to_the_last_page() -> None:
    pages = {
        "c1": {"nodes": [2], "pageInfo": {"hasNextPage": True, "endCursor": "c2"}},
        "c2": {"nodes": [3], "pageInfo": {"hasNextPage": False, "endCursor": "c3"}},
    }
    first = {"nodes": [1], "pageInfo": {"hasNextPage": True, "endCursor": "c1"}}

    assert drain(first, pages.__getitem__) == [1, 2, 3]


def test_drain_single_page_makes_no_fetch() -> None:
    first = {"nodes": [1], "pageInfo": {"hasNextPage": False, "endCursor": None}}

    assert drain(first, lambda _cursor: pytest.fail("fetched past the last page")) == [
        1
    ]
