#!/usr/bin/env node
/**
 * PreToolUse Hook - Block git -C usage
 *
 * Blocks any Bash command using `git -C`, which breaks permission patterns
 * and is unnecessary since Claude should run git from the working directory.
 *
 * Exits with code 2 to block the tool call.
 */

async function main() {
  let data = '';

  process.stdin.setEncoding('utf8');
  await new Promise((resolve) => {
    process.stdin.on('data', chunk => { data += chunk; });
    process.stdin.on('end', resolve);
  });

  const input = JSON.parse(data);
  const cmd = input.tool_input?.command || '';

  // Strip heredocs (<<'EOF'...EOF, <<EOF...EOF, <<"EOF"...EOF)
  // so we don't match git -C inside commit messages or PR bodies
  const stripped = cmd
    .replace(/<<-?\s*'(\w+)'[\s\S]*?^\1$/gm, '')
    .replace(/<<-?\s*"(\w+)"[\s\S]*?^\1$/gm, '')
    .replace(/<<-?\s*(\w+)[\s\S]*?^\1$/gm, '')
    // Strip double-quoted strings (handles escaped quotes)
    .replace(/"(?:[^"\\]|\\.)*"/g, '')
    // Strip single-quoted strings
    .replace(/'[^']*'/g, '');

  if (/git\s+-C\b/.test(stripped)) {
    console.error('[Hook] BLOCKED: Do not use git -C. Run git commands directly from the working directory.');
    process.exit(2);
  }
}

main().catch(() => process.exit(0));
