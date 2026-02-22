#!/usr/bin/env node
/**
 * PreCompact Hook - Save context before compaction
 *
 * Reads the session transcript JSONL and saves structured context
 * (file paths, task state, error tracking) to a temp file. The companion
 * SessionStart 'compact' hook (post-compact-inject.js) re-injects this
 * context after compaction.
 */

const fs = require("fs");

function extractContext(transcriptPath, sessionId, cwd) {
  if (!fs.existsSync(transcriptPath)) {
    return "";
  }

  const fileOps = new Map(); // path -> last operation (Map preserves insertion order)
  const taskCreates = [];
  const taskUpdates = {}; // taskId -> latest fields

  const lines = fs.readFileSync(transcriptPath, "utf8").split("\n");
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;

    let entry;
    try {
      entry = JSON.parse(line);
    } catch {
      continue;
    }

    if (entry.type !== "assistant") continue;

    const content = entry.message?.content;
    if (!Array.isArray(content)) continue;

    for (const block of content) {
      if (block.type !== "tool_use") continue;

      const name = block.name || "";
      const inp = block.input || {};

      // File operations
      if (["Write", "Edit", "Read"].includes(name) && inp.file_path) {
        const filePath = inp.file_path;
        if (!filePath.startsWith("/tmp/") && !filePath.includes("/.claude/")) {
          fileOps.set(filePath, name.toLowerCase());
        }
      }

      // Task tracking
      if (name === "TaskCreate") {
        taskCreates.push({
          subject: inp.subject || "",
          description: inp.description || "",
        });
      } else if (name === "TaskUpdate" && inp.taskId) {
        if (!taskUpdates[inp.taskId]) {
          taskUpdates[inp.taskId] = {};
        }
        for (const key of ["status", "subject", "description"]) {
          if (inp[key] !== undefined) {
            taskUpdates[inp.taskId][key] = inp[key];
          }
        }
      }
    }
  }

  return buildOutput(fileOps, taskCreates, taskUpdates, sessionId, cwd);
}

function buildOutput(fileOps, taskCreates, taskUpdates, sessionId, cwd) {
  const sections = [
    "# Pre-Compaction Context Snapshot",
    "",
    `**Working directory**: \`${cwd}\``,
    "",
  ];

  // Files referenced (last 20)
  if (fileOps.size > 0) {
    sections.push("## Files Referenced");
    const entries = [...fileOps.entries()].slice(-20);
    for (const [filePath, op] of entries) {
      sections.push(`- \`${filePath}\` (${op})`);
    }
    sections.push("");
  }

  // Active tasks
  const activeTasks = resolveTasks(taskCreates, taskUpdates);
  if (activeTasks.length > 0) {
    sections.push("## Active Tasks");
    for (const task of activeTasks) {
      sections.push(`- [${task.status}] ${task.subject}`);
      if (task.description) {
        sections.push(`  ${task.description.slice(0, 200)}`);
      }
    }
    sections.push("");
  }

  // Error tracking file (last 50 lines)
  const errorFile = `/tmp/claude-errors-${sessionId}.md`;
  if (fs.existsSync(errorFile)) {
    const errorLines = fs.readFileSync(errorFile, "utf8").trim().split("\n");
    const errorContent = errorLines.slice(-50).join("\n");
    if (errorContent) {
      sections.push("## Error Tracking");
      sections.push(errorContent);
      sections.push("");
    }
  }

  // Compaction guidance
  sections.push(
    "## Compaction Guidance",
    "",
    "**PRESERVE** (carry forward verbatim):",
    "- Final decisions and their rationale",
    "- Implementation plan or approach for the next phase",
    "- File paths and locations relevant to ongoing work (see above)",
    "- Architectural constraints or patterns established",
    "- Active task items and their status (see above)",
    "- Gotchas, edge cases, or warnings discovered",
    "- Test results or build state that affects next steps",
    "",
    "**SUMMARIZE** (compress to one line each):",
    "- Exploration and research that led to decisions",
    "- Failed approaches (just the lesson, not the journey)",
    "- Debugging sessions (just root cause and fix)",
    "",
    "**DROP** (do not carry forward):",
    "- Tool output from reads/greps that informed decisions already made",
    "- Intermediate draft code that was superseded",
    "- Back-and-forth clarification that reached a conclusion",
    "- Verbose error messages that were already resolved",
    "",
  );

  return sections.join("\n");
}

function resolveTasks(creates, updates) {
  const tasks = [];

  for (let i = 0; i < creates.length; i++) {
    const tid = String(i + 1); // Task IDs are 1-indexed
    const task = {
      subject: creates[i].subject,
      description: creates[i].description || "",
      status: "pending",
    };
    if (updates[tid]) {
      Object.assign(task, updates[tid]);
    }
    if (task.status !== "completed" && task.status !== "deleted") {
      tasks.push(task);
    }
  }

  return tasks;
}

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

  const { session_id: sessionId, transcript_path: transcriptPath } = hookInput;
  if (!sessionId || !transcriptPath) {
    process.exit(0);
  }

  const cwd = hookInput.cwd || "";
  const context = extractContext(transcriptPath, sessionId, cwd);

  if (!context.trim()) {
    process.exit(0);
  }

  const savePath = `/tmp/claude-precompact-${sessionId}.md`;
  fs.writeFileSync(savePath, context);
  process.exit(0);
}

main().catch(() => process.exit(0));
