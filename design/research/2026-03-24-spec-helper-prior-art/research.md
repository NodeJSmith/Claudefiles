# Research Brief: Prior Art and Best Practices for Spec-Driven Development CLI Tools

**Date**: 2026-03-24
**Status**: Ready for Decision
**Proposal**: Wide exploration of prior art and alternative architectures for redesigning `spec-helper`, a CLI tool that manages work package markdown files with YAML frontmatter in a spec-driven LLM orchestration pipeline.
**Initiated by**: User request for ideas they "aren't considering at all that may be better solutions"

## Context

### What prompted this

The `spec-helper` CLI has accumulated 10 challenge findings (6 CRITICAL, 4 MEDIUM) including split authority over WP creation, fragile bespoke YAML parsing, silent failures, and terminal-optimized output consumed primarily by LLMs. Rather than patching these issues incrementally, the user wants to explore fundamentally different approaches informed by prior art.

### Current state

The caliper v2 pipeline works like this:

1. **`mine.specify`** or **`mine.grill`** creates a feature directory via `spec-helper init <slug>` -- produces `design/specs/NNN-slug/` with a `spec.md` template
2. **`mine.design`** also calls `spec-helper init` if needed, writes `design.md`
3. **`mine.draft-plan`** reads `design.md` and writes `WP*.md` files directly (NOT via spec-helper) into `tasks/`
4. **`mine.orchestrate`** reads WP files, calls `spec-helper wp-move` for lane transitions, calls `spec-helper status` for display
5. **`mine.wp`** is a 104-line skill that exists solely to translate user intent into `spec-helper` CLI calls

The tool itself is 533 lines of Python with:
- A hand-rolled YAML parser (~50 lines) that handles only simple `key: "value"` and inline arrays
- 4 commands: `init`, `wp-move`, `status`, `next-number`
- `--json` flag for machine output (but human-readable is the default)
- A `WP_TEMPLATE` that no caller uses (draft-plan writes its own format)

Real schema drift exists: feature 001 WPs have `work_package_id`, `plan_section`, `depends_on` while feature 006 WPs have `issue`, `depends` (no `_on`, no `work_package_id`, no `plan_section`).

### Key constraints

- Primary consumers are LLM subagents (orchestrate, wp, status skills), not humans
- The tool is part of a personal productivity system, not a team product
- Python stdlib only (current), but adding dependencies is acceptable
- Must work with the existing `design/specs/NNN-slug/tasks/WP*.md` file structure (or propose a compelling replacement)
- The filesystem IS the API for LLM agents -- they Read/Write/Glob files directly

## Prior Art Catalog

### 1. Markdown + Frontmatter Management

| Tool | Type | Schema Enforcement | Content Creation | Validation | Querying |
|------|------|-------------------|------------------|------------|----------|
| **Hugo** | Static site CLI | Template-based (archetypes); no runtime validation | `hugo new content <path>` with archetype lookup chain | None beyond template structure | N/A (build-time) |
| **Astro Content Collections** | Build framework | Zod schemas in `content.config.ts`; compile-time errors | Manual file creation | Type-checked at build; generates TypeScript types | `getCollection()`, `getEntry()` with typed results |
| **Contentlayer** | Content SDK | TypeScript `defineDocumentType` with required/optional fields | Manual file creation | Build-time type validation; computed fields | Import typed objects directly in code |
| **Front Matter CMS** | VS Code extension | JSON schema in `frontmatter.json`; field types, conditions | GUI-driven creation with templates | Real-time in editor | Dashboard with filter/sort/group |
| **Obsidian Dataview** | Plugin | None (schema-free) | Manual | None | DQL query language: `LIST FROM #tag WHERE field = "value"` |
| **gray-matter** (npm) | Library | None | N/A (parsing only) | N/A | N/A |
| **python-frontmatter** | Library | None | N/A (parsing only) | N/A | N/A |

**Key insight**: The tools that handle schema enforcement well (Astro, Contentlayer) all define schemas in a separate configuration file, not inline. They validate at "build time" -- which for us would be at WP creation time or as a pre-commit check.

### 2. Spec-Driven / Document-Driven Development

| Tool/Process | Lifecycle States | Dependencies | Schema Enforcement | Notable Pattern |
|------|------|------|------|------|
| **adr-tools** | draft -> accepted -> superseded | Bidirectional supersedes links | Template-based only | `adr new -s 9` auto-updates ADR 9's status to "superseded" -- bidirectional state propagation |
| **log4brains** | proposed -> accepted -> deprecated -> superseded | Cross-package references | None ("free to write however you want") | Extracts metadata from git logs automatically -- no manual annotation |
| **MADR** | Via template sections (not frontmatter) | Manual cross-references | markdownlint rules | 4 template variants (full/minimal x explained/bare) for different needs |
| **Rust RFC process** | Draft -> FCP -> Merged/Closed/Postponed | Tracking issues link RFC to implementation | Template + review process | Each RFC gets a tracking issue for implementation -- separation of "what" from "are we doing it" |
| **Harper's LLM workflow** | `spec.md` -> `prompt_plan.md` -> `todo.md` | Sequential prompts build on previous | None (convention only) | Emphasizes "no big jumps in complexity at any stage" -- each prompt builds incrementally |

**Key insight**: adr-tools' bidirectional link propagation (superseding ADR 9 automatically updates ADR 9) is directly relevant to WP dependency management. The Rust RFC pattern of separating the document from a tracking issue that monitors implementation status is essentially what our `lane` frontmatter field does, but more explicitly.

### 3. Kanban-in-Files / Task-in-Files

| Tool | Storage | State Model | Transitions | Activity Log |
|------|---------|------------|-------------|--------------|
| **Taskwarrior** | JSON file per task (binary-managed) | Pending -> Completed -> Deleted + custom statuses | CLI commands with validation; undo support | Full modification history per task |
| **todo.txt** | Single text file, one line per task | Active -> Done (moved to `done.txt`) | Line editing + completion marker | None (file is the log via git) |
| **git-bug** | Git objects (NOT files) | Open -> Closed + labels | CLI operations stored as git commits | Complete audit trail via git history |
| **SIT** | Files in `.sit/` directory | Domain-specific via modules | Append-only records per issue | Event-sourced: each change is a new record |
| **Jujutsu (jj)** | Operations log | Snapshot per operation | Automatic rebasing of descendants | Full operation log with undo/redo support |

**Key insight**: git-bug's approach of storing structured data as git objects (not files) is interesting but overkill. SIT's append-only record model and Jujutsu's operations log both point to event sourcing as a pattern -- rather than mutating frontmatter in place, append state changes to a log. This is exactly what the Activity Log section in WPs already does, but it's decorative rather than authoritative.

### 4. CLI Design Patterns for Document Management

| Tool/Pattern | Scaffolding | Schema Validation | Guided Input | Notable Pattern |
|------|------|------|------|------|
| **Cookiecutter** | Template rendering from `cookiecutter.json` | Type coercion on input | Interactive prompts | Pre/post generation hooks for validation |
| **Copier** | Template rendering + lifecycle updates | Typed questionnaire (`type: str`) | Interactive prompts | Can re-render existing projects when template evolves -- handles schema migration |
| **Commitizen** | N/A | Pre-commit hook validation | Interactive commit builder | Schema-as-code: rules defined in config, enforced at git boundaries |
| **clig.dev** | N/A | N/A | N/A | "JSON for machines, text for humans" -- `--json` should be first-class, not an afterthought |

**Key insight**: Copier's ability to update existing projects when templates change is directly relevant -- when the WP schema evolves, existing WPs need migration. Commitizen's pattern of enforcing schema at git boundaries (pre-commit hooks) rather than at creation time is worth stealing.

### 5. LLM-Oriented Tool Design

| Pattern | Source | Application |
|------|------|------|
| **JSON Schema for input/output** | MCP specification | Tools declare `inputSchema` and `outputSchema` as JSON Schema; clients validate both |
| **Structured + unstructured output** | MCP specification | Return both `structuredContent` (JSON) and `content` (text) -- machine and human simultaneously |
| **Annotation-based audience** | MCP specification | Content items have `audience: ["user"]` or `audience: ["assistant"]` -- different content for different consumers |
| **Error as data, not crash** | MCP specification | Tool execution errors return `isError: true` with structured error content, separate from protocol errors |
| **Incremental spec documents** | Harper blog | `spec.md` -> `prompt_plan.md` -> `todo.md` pipeline where each document feeds the next |
| **JSON Lines for streaming** | jsonlines.org | One JSON object per line for log-like output that's both streamable and parseable |

**Key insight**: MCP's dual-output pattern (structured JSON for machines + text for humans, in the same response) is exactly what spec-helper needs. The `audience` annotation pattern could solve the "who's reading this" problem -- LLM agents get JSON, humans get formatted text, from the same tool invocation.

### 6. Data Validation Libraries

| Library | Approach | Relevance |
|------|------|------|
| **Pydantic** | Python dataclasses with type validation | Define WP schema as a Pydantic model; validate on read AND write; get serialization for free |
| **Zod** (TypeScript) | Runtime type validation | Used by Astro Content Collections for frontmatter schema |
| **JSON Schema** | Language-agnostic schema definition | Could define WP schema once, validate from Python CLI and from LLM tools |

## Patterns Worth Stealing

### Pattern 1: Schema-as-Code with Validation on Both Boundaries

**Source**: Astro Content Collections + Pydantic + Commitizen

Define the WP schema as a Pydantic model. Validate:
- **On write**: when `mine.draft-plan` creates WPs or `spec-helper` modifies them
- **On read**: when `mine.orchestrate` loads WPs (catch drift from manual edits)
- **At git boundary**: pre-commit hook rejects WPs with invalid frontmatter

This eliminates the split-authority problem (Finding 1) and the fragile parser (Finding 2) in one move. The schema definition IS the documentation -- no template can drift from it because the template is generated from the schema.

```python
class WorkPackage(BaseModel):
    work_package_id: str  # "WP01"
    title: str
    lane: Literal["planned", "doing", "for_review", "done"]
    plan_section: str = ""
    depends_on: list[str] = []
    # Computed/validated
    @validator('work_package_id')
    def valid_wp_id(cls, v):
        assert re.match(r'^WP\d{2,}$', v)
        return v
```

### Pattern 2: Activity Log as Source of Truth (Event Sourcing Lite)

**Source**: SIT + Jujutsu + git-bug

Instead of mutating the `lane` field and appending to an Activity Log as a side effect, make the Activity Log authoritative:
- The current lane is derived from the last `lane=X` entry in the Activity Log
- `wp-move` only appends to the log; it never modifies frontmatter
- A `wp-status` query reads the log to compute current state
- Frontmatter becomes a cache/snapshot that can be regenerated from the log

This makes the Activity Log the single source of truth, eliminates the read-modify-write race condition (Finding 8), and provides a complete audit trail for free. The frontmatter `lane` field becomes a convenience for tools that want to quickly peek at state without parsing the log.

### Pattern 3: Default to Machine-Readable Output

**Source**: clig.dev + MCP specification

Flip the default: JSON output by default, `--human` or `--pretty` for terminal use. Better yet, adopt MCP's dual-output pattern:
- Always write JSON to stdout
- Optionally write human-readable to stderr when a TTY is detected
- Or: always return a structured object that the caller (skill/agent) can format as needed

This eliminates Finding 7 (terminal-optimized output for LLM consumers) and simplifies the mine.wp skill, which currently exists just to translate between the LLM and the CLI.

### Pattern 4: Schema Migration via Template Re-rendering

**Source**: Copier

When the WP schema changes, provide a `wp-migrate` command that:
1. Reads all WP files
2. Validates against the current schema
3. For each invalid field, applies a migration (rename `depends` -> `depends_on`, add missing `work_package_id`)
4. Writes corrected files

This addresses the existing schema drift between feature 001 and feature 006 WPs.

### Pattern 5: Bidirectional Link Propagation

**Source**: adr-tools

When WP03 depends on WP01, and WP01 moves to `done`, automatically check if WP03 is now unblocked (all dependencies satisfied). This is the `adr new -s 9` pattern applied to work packages -- state changes propagate to dependents.

### Pattern 6: Creation Responsibility Belongs to the Schema Owner

**Source**: Hugo archetypes + Cookiecutter

The tool that owns the schema should own creation. If `spec-helper` defines what a valid WP looks like (via Pydantic model), it should also be the only way to create WPs:

```bash
spec-helper wp-create <feature> --title "..." --plan-section "..." --depends-on WP01,WP02
```

The `mine.draft-plan` skill then calls this command instead of writing files directly. The skill provides the content (objectives, subtasks, test strategy); the tool provides the structure (frontmatter, file naming, directory placement, Activity Log initialization).

## Alternative Architectures

### Architecture A: Pydantic-Validated CLI (Evolutionary)

**How it works**: Keep the current file-based architecture but replace the bespoke parser with python-frontmatter + Pydantic. Add `wp-create` and `wp-validate` commands. Make JSON the default output. Add a pre-commit hook for schema validation.

**What changes**:
- `spec-helper` grows ~100 lines (Pydantic model, wp-create, wp-validate)
- `mine.draft-plan` changes to call `spec-helper wp-create` instead of writing files
- `mine.wp` shrinks or is eliminated (spec-helper becomes more capable)
- Add `python-frontmatter` and `pydantic` as dependencies

**Pros**:
- Smallest change surface; fixes all 10 findings
- Pydantic model serves as living documentation of the WP schema
- Pre-commit hook catches drift before it enters the repo
- Familiar Python patterns; no new concepts

**Cons**:
- Still a custom CLI; still maintains its own argument parsing
- Two new dependencies (though both are ubiquitous in Python)
- Doesn't fundamentally rethink the tool/agent boundary

**Effort**: Small-Medium

### Architecture B: MCP Server (Paradigm Shift)

**How it works**: Replace the CLI with an MCP server that exposes WP management as tools. The LLM agent calls MCP tools directly instead of shelling out to a CLI. The server handles schema validation, state transitions, and returns structured JSON.

```
Tools exposed:
- wp_create(feature, title, plan_section, depends_on, body_sections)
- wp_move(feature, wp_id, lane)
- wp_status(feature?) -> structured JSON
- wp_validate(feature?) -> list of validation errors
- feature_init(slug) -> feature directory info
```

**What changes**:
- `spec-helper` becomes an MCP server (Python, using the MCP SDK)
- Skills stop using `Bash(spec-helper ...)` and instead call MCP tools
- The server owns file I/O; LLM agents never write WP files directly
- Input/output schemas defined in MCP tool definitions (JSON Schema)

**Pros**:
- Native LLM integration -- no CLI parsing, no stdout parsing, no `--json` flag
- JSON Schema for input AND output validation, declared in tool definitions
- Error handling is structured (MCP's `isError` pattern)
- Could expose as both MCP server and CLI (dual interface)
- Future-proof: as Claude Code's MCP support matures, this becomes more natural

**Cons**:
- Requires MCP SDK dependency and server lifecycle management
- Overkill for a personal tool? MCP servers need to be started and managed
- Skills that currently do `Bash(spec-helper wp-move ...)` would need rewriting
- MCP is still evolving; API may change

**Effort**: Medium-Large

### Architecture C: SQLite + Markdown Views (Database-First)

**How it works**: Use SQLite as the source of truth for WP state. Markdown files become generated views that are regenerated from the database. The database stores structured fields (lane, dependencies, timestamps) while the markdown body is stored as a text blob.

```
wp.db (SQLite):
  features(id, slug, number, created_at)
  work_packages(id, feature_id, title, lane, plan_section, body_md, created_at)
  dependencies(wp_id, depends_on_wp_id)
  activity_log(wp_id, lane, actor, timestamp, message)

Markdown files regenerated on demand or via git hook.
```

**What changes**:
- `spec-helper` becomes a sqlite-utils powered CLI
- WP creation writes to SQLite; `spec-helper render` generates markdown files
- `mine.orchestrate` queries SQLite for status instead of globbing/parsing files
- Pre-commit hook regenerates markdown from DB to keep them in sync
- Git tracks both the DB file and the rendered markdown

**Pros**:
- Eliminates all parsing issues -- SQL queries replace frontmatter parsing
- Activity log is a proper table with timestamps and indexing
- Dependency graph queries are trivial (`SELECT * FROM dependencies WHERE ...`)
- sqlite-utils provides instant CLI for ad-hoc queries
- Full ACID guarantees on state transitions

**Cons**:
- Binary SQLite file in git is awkward (merge conflicts, diff unfriendly)
- LLM agents currently Read markdown files directly; they'd need to use the CLI or query the DB
- Two sources of truth (DB + rendered markdown) unless you commit to DB-only
- Adds complexity for a problem that's fundamentally about ~50 files
- Overkill for the scale of this system

**Effort**: Large

### Architecture D: Schema File + Dumb Filesystem Operations (Minimalist)

**How it works**: Define a `wp-schema.yaml` file that describes valid frontmatter fields, types, allowed values, and transition rules. The "tool" becomes a thin validator that reads the schema and checks files against it. WP creation and modification happen via direct file writes (by LLM agents or skills), and validation happens at git boundaries.

```yaml
# design/wp-schema.yaml
fields:
  work_package_id:
    type: string
    pattern: "^WP\\d{2,}$"
    required: true
  title:
    type: string
    required: true
  lane:
    type: enum
    values: [planned, doing, for_review, done]
    default: planned
    transitions:
      planned: [doing]
      doing: [for_review, done, planned]
      for_review: [done, doing]
      done: []
  depends_on:
    type: array
    items: string
    default: []

activity_log:
  section: "## Activity Log"
  auto_append_on: [lane]
  format: "- {timestamp} -- {actor} -- {field}={value} -- {message}"
```

Then:
- A pre-commit hook runs `wp-validate` against the schema
- LLM agents write WP files directly (they already know the format from skill prompts)
- `spec-helper` shrinks to just `validate`, `status`, and `next-number`
- No `wp-create` needed -- the schema IS the template
- No `wp-move` needed -- agents edit frontmatter directly, validation catches errors

**What changes**:
- Add `wp-schema.yaml` defining the contract
- Shrink `spec-helper` to a validator + status viewer
- `mine.draft-plan` continues writing files directly (now validated by schema)
- `mine.orchestrate` edits frontmatter directly instead of calling `wp-move`
- Pre-commit hook enforces the schema

**Pros**:
- Eliminates the split-authority problem by embracing it: agents write, schema validates
- Schema file is human-readable documentation of the WP format
- Minimal tooling -- the schema file + a ~100-line validator
- Works with how LLM agents already operate (Read/Write files)
- Transition rules in the schema prevent invalid lane changes
- No new dependencies if you hand-write the validator; or use Pydantic/JSON Schema

**Cons**:
- Activity log auto-append requires either a pre-commit hook or agent discipline
- No atomic state transitions -- agents do read-modify-write on their own
- Validation is post-hoc (at commit time), not at write time
- Loses the `wp-move` audit trail unless agents are disciplined about Activity Log entries

**Effort**: Small

### Architecture E: Event-Sourced Activity Log (Hybrid)

**How it works**: The Activity Log becomes the authoritative state store. Frontmatter `lane` is a cached snapshot. A tool command only appends to the Activity Log; a separate `reconcile` step updates frontmatter from the log. This is the SIT/Jujutsu pattern applied to WPs.

```
## Activity Log

- 2026-03-24T10:00:00Z -- system -- lane=planned -- WP created
- 2026-03-24T11:30:00Z -- orchestrator -- lane=doing -- execution started
- 2026-03-24T12:15:00Z -- orchestrator -- lane=done -- all tests passing

Current state derived from last entry: lane=done
```

The tool provides:
- `wp-append <feature> <wp-id> <field>=<value> [--message "..."]` -- append to Activity Log
- `wp-reconcile [feature]` -- update frontmatter from Activity Log for all WPs
- `wp-status [feature]` -- derive current state from Activity Log (no frontmatter needed)
- `wp-history <feature> <wp-id>` -- show full history

**Pros**:
- Single source of truth (the log)
- No read-modify-write races on frontmatter
- Complete audit trail by construction
- Frontmatter is always derivable -- can be regenerated
- `reconcile` can be a pre-commit hook or run on demand

**Cons**:
- More complex than simple frontmatter mutation
- LLM agents would need to parse the Activity Log to determine current state (or read frontmatter as a cache)
- Adds a concept (event sourcing) that may be unfamiliar
- The Activity Log section is at the end of the markdown file, which means appending requires finding the right insertion point (the same bug as Finding 4, unless you move it to a separate file)

**Effort**: Medium

## Concerns

### Technical risks
- **MCP server lifecycle**: Architecture B requires managing a long-running process. Claude Code's MCP integration may not be mature enough for a personal tool that needs to start/stop cleanly.
- **SQLite in git**: Architecture C's binary database file creates merge conflict and diff problems that are well-known and unsolved for personal repos.
- **Schema migration**: Any schema-enforcing approach needs a story for migrating the 22 existing WP files across 4 features with 2 different schemas.

### Complexity risks
- **Event sourcing for ~50 files**: Architecture E adds conceptual complexity for a system that currently has 22 WP files across 4 features. The scale doesn't justify the abstraction.
- **MCP server for a personal tool**: Architecture B is the "right" long-term answer for LLM-oriented tools, but adds infrastructure that a single-file CLI doesn't need.

### Maintenance risks
- **Pydantic version churn**: Pydantic v1 -> v2 migration was painful for many projects. Pinning is manageable but adds dependency management overhead.
- **MCP SDK stability**: The MCP specification is still evolving (the spec shows `outputSchema` as a recent addition). Building on it now means accepting future migration cost.

## Open Questions

- [ ] **How much does `mine.orchestrate` rely on reading WP files directly (via Read) vs. calling `spec-helper`?** If it already reads files directly for content (objectives, subtasks) and only uses spec-helper for lane transitions, Architecture D (schema + direct writes) becomes more natural.
- [ ] **Is there appetite for adding Python dependencies to `bin/` scripts?** Currently spec-helper is stdlib-only. Adding `pydantic` and `python-frontmatter` changes the installation story.
- [ ] **Should the Activity Log move to a separate file per WP?** A `WP01.log` file next to `WP01.md` would eliminate the "append to correct section" problem entirely and make event sourcing cleaner.
- [ ] **Is MCP server support planned for Claude Code hooks/tools?** If so, Architecture B becomes more compelling as a long-term investment.
- [ ] **How often do WP files get manually edited?** If "never" (only LLMs and spec-helper touch them), pre-commit validation may be sufficient. If "sometimes" (human edits for corrections), write-time validation matters more.

## Recommendation

**Start with Architecture A (Pydantic-Validated CLI), with elements of Architecture D (Schema File) for future evolution.**

Reasoning:

1. **Architecture A fixes all 10 findings** with the smallest change surface. Replace the bespoke parser with python-frontmatter, add a Pydantic model, add `wp-create`, make JSON the default output.

2. **Borrow the schema file idea from Architecture D** by making the Pydantic model the single source of truth. Export it as a JSON Schema file (`design/wp-schema.json`) that can be used by pre-commit hooks and potentially by MCP tools in the future.

3. **Defer MCP (Architecture B) until Claude Code's MCP ecosystem matures.** The Pydantic model + JSON Schema export positions you to expose the same validation as MCP tool schemas when ready.

4. **Skip SQLite (Architecture C) and event sourcing (Architecture E).** Both add complexity that isn't justified at the current scale (22 WP files). If the system grows to hundreds of WPs across dozens of features, revisit.

5. **Adopt the "creation belongs to the schema owner" pattern immediately.** Add `wp-create` to spec-helper, update `mine.draft-plan` to call it. This is the single highest-impact change.

## Sources

- Hugo Archetypes: https://gohugo.io/content-management/archetypes/
- Astro Content Collections: https://docs.astro.build/en/guides/content-collections/
- Contentlayer: https://contentlayer.dev/docs/getting-started
- Front Matter CMS: https://frontmatter.codes/docs/getting-started
- Obsidian Dataview: https://blacksmithgu.github.io/obsidian-dataview/
- gray-matter: https://github.com/jonschlinkert/gray-matter
- python-frontmatter: https://github.com/eyeseast/python-frontmatter
- adr-tools: https://github.com/npryce/adr-tools
- log4brains: https://github.com/thomvaill/log4brains
- MADR: https://github.com/adr/madr
- Rust RFC process: https://github.com/rust-lang/rfcs
- Harper's LLM codegen workflow: https://harper.blog/2025/02/16/my-llm-codegen-workflow-atm/
- Taskwarrior: https://taskwarrior.org/docs/
- todo.txt: https://github.com/todotxt/todo.txt-cli
- git-bug: https://github.com/MichaelMure/git-bug
- SIT: https://github.com/sit-fyi/sit
- Jujutsu: https://github.com/martinvonz/jj
- Cookiecutter: https://github.com/cookiecutter/cookiecutter
- Copier: https://github.com/copier-org/copier
- Commitizen: https://github.com/commitizen-tools/commitizen
- MCP Tools specification: https://modelcontextprotocol.io/docs/concepts/tools
- CLI Guidelines: https://clig.dev/
- JSON Lines: https://jsonlines.org/
- sqlite-utils: https://sqlite-utils.datasette.io/en/stable/cli.html
- Datasette: https://github.com/simonw/datasette
- Pydantic: https://github.com/pydantic/pydantic
- Foam: https://github.com/foambubble/foam
