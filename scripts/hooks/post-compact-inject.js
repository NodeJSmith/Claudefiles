#!/usr/bin/env node
/**
 * SessionStart Hook - Inject saved context after compaction
 *
 * Reads the context snapshot saved by pre-compact-save.js and re-injects
 * it as additionalContext so critical information survives compaction.
 */

const fs = require("fs");

async function main() {
  let data = "";

  process.stdin.setEncoding("utf8");
  await new Promise((resolve) => {
    process.stdin.on("data", (chunk) => { data += chunk; });
    process.stdin.on("end", resolve);
  });

  let hookInput;
  try {
    hookInput = JSON.parse(data);
  } catch {
    process.exit(0);
  }

  const sessionId = hookInput.session_id;
  if (!sessionId) {
    process.exit(0);
  }

  const contextFile = `/tmp/claude-precompact-${sessionId}.md`;
  if (!fs.existsSync(contextFile)) {
    process.exit(0);
  }

  const context = fs.readFileSync(contextFile, "utf8");

  const preamble = [
    "## Post-Compaction Context Restored",
    "",
    "The pre-compaction hook saved context from your previous session state.",
    "IMPORTANT: Briefly tell the user that pre-compaction context was restored and summarize what was preserved (files, tasks, errors) in 1-2 sentences.",
    "",
  ].join("\n");

  console.log(JSON.stringify({
    hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext: preamble + context,
    },
  }));

  fs.unlinkSync(contextFile);
}

main().catch(() => process.exit(0));
