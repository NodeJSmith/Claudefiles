# Codebase Exploration Protocol

**Use Glob, Grep, and Read only — no Bash for exploration.**

Ground the tasks in reality before writing:

1. **Find exact file paths** — for every module, class, or function named in the design, run Glob to get the real path. Record each one.

2. **Locate test infrastructure**
   - Test directories: `Glob: tests/**/*.py` or equivalent
   - Fixtures: `Grep: conftest.py`
   - CI test command: read `.github/workflows/*.yml`, `noxfile.py`, `tox.ini`, or `Makefile` (whichever applies)

3. **Find existing patterns to follow**
   - Naming conventions (read 2–3 similar files)
   - Module structure (read `__init__.py` or index files)
   - Abstractions already in use

4. **Note gotchas**
   - Shared state or global singletons
   - Circular import risks
   - Files imported by many modules (high blast radius)

5. **Reverse-dependency gap check** — search the full codebase for files that depend on what's changing but aren't listed in the design doc's Impact section. This catches dependencies the design doc missed entirely. Skip this step if the design doc has neither an Impact section nor an Architecture / Proposed Approach section.

   **Identify what's changing**: Read the design doc's Architecture section (or Proposed Approach — whichever heading is used). For each sentence that describes adding, modifying, removing, or renaming something, extract the specific identifier — function name, class name, type name, API endpoint, database table, config key, or component name.

   **Search**: Grep the codebase for each identifier. Filter out files already listed in the Impact section — those are known. For each match outside the Impact list, assess whether it represents a genuine dependency that would break or need updating. Classify each gap:
   - **Tests** — test files that assert on changed behavior, UI structure, or API responses
   - **Callers** — code that calls functions/methods whose signatures are changing
   - **Validators/guards** — validation logic or type guards referencing changed values
   - **CSS/layout** — stylesheets that assume the affected component's DOM structure
   - **Documentation** — docs or docstrings describing the behavior being changed
   - **Real-time paths** — WebSocket handlers, event listeners, or polling loops that reference changed modules
   - **Generated code** — TypeScript types, OpenAPI schemas, or codegen artifacts derived from changed files
   - **Type aliases** — discriminated unions, re-exports, or barrel files referencing changed types
   - **SQL views/indexes** — views or indexes on columns being changed
   - **Data structures** — code assuming the shape of data produced by changed modules

   Skip categories that don't apply to the project (e.g., SQL for a frontend-only repo, CSS for a backend service). Note which categories were searched and which were skipped.

   Record each gap found with: the category, the file path and line, what it depends on, and what would break.

## Present gap-check results

After step 5, if gaps were found, present them grouped by category. Include all gaps in tasks by default — add Focus items to address each one (update the test, fix the caller, regenerate the types, etc.). After Phase 3, update the design.md Impact section with a gap-check comment listing each gap and which task addresses it: `<!-- Gap check [date]: N gaps included — gap1 (file:line) → T02 Focus item 3, gap2 → T03 Focus item 5, ... -->`.

Then briefly summarize what was included so the user can push back on any false positives before committing.

If no gaps were found, report: "Gap check clean — no unlisted dependencies found." Proceed to Phase 3.

Do NOT guess file paths. If Glob returns no match, note it explicitly.
