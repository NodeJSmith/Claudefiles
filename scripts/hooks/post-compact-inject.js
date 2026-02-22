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

  console.log(JSON.stringify({
    hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext: context,
    },
  }));

  fs.unlinkSync(contextFile);
}

main().catch(() => process.exit(0));
