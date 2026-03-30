# LSP Tools

Prefer `LSP` over `Grep` for symbol-level navigation in Python files. It's faster, more accurate, and uses less context. LSP requires a Grep-first step to locate the file and line, then navigates from that position.

**Supported languages:** Python (via pyright). Shell, Markdown, YAML, and JSON have no LSP server — use Grep for those.

## When to Use LSP

| Task | LSP operation | Notes |
|------|--------------|-------|
| Find where a function/class/variable is defined | `goToDefinition` | |
| Find all call sites / usages | `findReferences` | |
| Get type signature or docstring | `hover` | |
| List all functions/classes in a file | `documentSymbol` | No prior Grep needed — works with any position in the file |
| See what calls a function | `incomingCalls` | |
| See what a function calls | `outgoingCalls` | |

**Not reliable with pyright:** `workspaceSymbol` (returns empty results) and `goToImplementation` (throws an error — Python lacks formal interfaces). Use Grep for project-wide symbol search instead.

## When Grep Is Still Appropriate

- Searching for **string literals**, comments, or patterns (not symbols)
- Non-Python files (shell, markdown, YAML, JSON — no LSP server configured)
- You need context lines around a match (`-C` flag)
- If LSP returns an error (no server for this file type), fall back to Grep immediately

## Usage Pattern

LSP requires a file path + line + character position. All three are required for every operation.

1. `Grep` to find the file and line where the symbol appears
2. `Read` the line to find the character offset — count to the start of the symbol name (1-based)
3. `LSP` from that position to navigate or inspect

```
# Example: find definition of `process_document`
Grep → finds it at src/pipeline.py:42
Read line 42 → "    result = process_document(data)"
Count to 'p' in process_document → character=14
LSP goToDefinition → filePath=/absolute/path/to/src/pipeline.py, line=42, character=14
```

For `documentSymbol` (listing all symbols in a file), use `line=1, character=1` — the position doesn't matter for this operation.

Always use **absolute file paths** — relative paths fail in worktrees and subagent contexts.
