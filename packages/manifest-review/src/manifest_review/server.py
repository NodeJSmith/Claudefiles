"""MCP server spike: validate sequential elicitation with progress heartbeat.

Tests whether Claude Code can handle N sequential elicitation calls within a
single tool invocation without timing out. Uses progress notifications as a
keepalive between user interactions.
"""

import logging
import os
import sys
import traceback

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ElicitResult

logging.basicConfig(
    stream=sys.stderr,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("manifest-review")

mcp = FastMCP("manifest-review")

VERB_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "verb": {
            "type": "string",
            "enum": ["fix", "file", "defer", "skip"],
            "enumNames": ["Fix now", "File an issue", "Defer for later", "Skip"],
            "title": "Action",
            "description": "What to do with this finding",
        },
    },
    "required": ["verb"],
}

FAKE_FINDINGS = [
    {
        "id": "F1",
        "title": "Acceptance criterion is untestable",
        "severity": "HIGH",
        "problem": 'AC-4 says "respond quickly" with no measurable threshold.',
    },
    {
        "id": "F2",
        "title": "Missing error handling requirement",
        "severity": "MEDIUM",
        "problem": "No requirement specifies behavior on upstream timeout.",
    },
    {
        "id": "F3",
        "title": "Conflicting performance targets",
        "severity": "TENSION",
        "problem": 'NFR-1 says "sub-100ms p99" but AC-7 implies complex aggregation.',
    },
]


async def _elicit_verb(ctx: Context, message: str) -> ElicitResult:
    """Bypass FastMCP's validator and call session.elicit_form() directly."""
    return await ctx.request_context.session.elicit_form(
        message=message,
        requestedSchema=VERB_SCHEMA,
        related_request_id=ctx.request_id,
    )


@mcp.tool()
async def spike_review(ctx: Context) -> str:
    """Spike: present 3 fake findings sequentially via elicitation.

    Tests dropdown rendering via raw JSON Schema enum bypass.
    """
    logger.info(
        "spike_review called — starting review of %d findings", len(FAKE_FINDINGS)
    )
    results: dict[str, str] = {}

    try:
        for i, finding in enumerate(FAKE_FINDINGS):
            logger.debug(
                "presenting finding %d/%d: %s", i + 1, len(FAKE_FINDINGS), finding["id"]
            )

            await ctx.report_progress(
                progress=i,
                total=len(FAKE_FINDINGS),
                message=f"Reviewing finding {i + 1}/{len(FAKE_FINDINGS)}",
            )

            result = await _elicit_verb(
                ctx,
                message=(
                    f"{finding['id']}: {finding['title']} ({finding['severity']})\n\n"
                    f"{finding['problem']}\n\n"
                    f"Finding {i + 1} of {len(FAKE_FINDINGS)}"
                ),
            )

            logger.debug(
                "elicit result: action=%s content=%s", result.action, result.content
            )

            if result.action == "accept" and result.content:
                results[finding["id"]] = str(result.content.get("verb", "???"))
            elif result.action == "decline":
                results[finding["id"]] = "skip"
            else:
                logger.info("review cancelled at %s", finding["id"])
                return (
                    f"Review cancelled at {finding['id']}. Resolved so far: {results}"
                )

        await ctx.report_progress(
            progress=len(FAKE_FINDINGS),
            total=len(FAKE_FINDINGS),
            message="All findings reviewed",
        )

        summary = "\n".join(f"  {fid}: {verb}" for fid, verb in results.items())
        logger.info("review complete: %s", results)
        return f"Review complete. Resolutions:\n{summary}"

    except Exception:
        logger.error("spike_review crashed:\n%s", traceback.format_exc())
        raise


def main():
    logger.info("manifest-review server starting (pid=%d)", os.getpid())
    try:
        mcp.run()
        logger.info("mcp.run() returned normally (stdin EOF likely)")
    except Exception:
        logger.error("server exited with error:\n%s", traceback.format_exc())
        raise
    finally:
        logger.info("manifest-review server exiting")


if __name__ == "__main__":
    main()
