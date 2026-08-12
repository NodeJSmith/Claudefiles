# OpenCode Integration Roadmap

## Purpose

Claudefiles was designed around Claude Code's configuration, tools, hooks, and subagent model. OpenCode support currently consists of copying compatible artifacts with `opencode-sync` and remapping Claude model tiers to OpenAI model IDs. That makes many skills and agents visible in OpenCode, but it does not make every workflow correct or enforce the same operational policies.

This document defines the target architecture and the sequence of independently shippable specs needed to make OpenCode a supported execution environment. It is a roadmap, not an implementation design. Each spec should investigate current OpenCode behavior, make its own detailed decisions, and update this document when those decisions change the overall direction.

## Current State

`bin/opencode-sync` stages the repository, invokes OpenPackage for the OpenCode platform, and post-processes installed files. It currently provides useful distribution but has important limits:

- Synced rules are not necessarily loaded as OpenCode instructions.
- Claude-specific dispatch syntax remains in skills, including `Agent`, `subagent_type`, per-dispatch models, background execution, and worktree isolation.
- Agent model remapping is only partially reliable today: some generated named agents can still keep Claude tier names instead of OpenAI model IDs, and OpenCode built-in subagents can still inherit the primary session model.
- Claude Code shell hooks are not OpenCode plugins and do not run in OpenCode.
- Claude-specific paths and interaction syntax remain in many workflows.
- OpenCode's Claude compatibility fallback can conceal missing or broken generated artifacts.
- There is no isolated integration test proving which configuration OpenCode loaded or which model a child session used.

The existing sync should therefore be treated as provisional compatibility, not feature parity.

## Ownership

`bin/opencode-sync` is the canonical user-facing entry point for generating, installing, upgrading, and pruning OpenCode artifacts. Future specs may replace OpenPackage or move implementation into helper modules, but they should preserve this command as the supported control plane unless a later design explicitly migrates it. `install.py` remains the Claude Code installer; it may advertise or invoke OpenCode setup only after the OpenCode path can preserve machine-local configuration safely.

The OpenCode generator owns version-controlled policy, generated agents, generated skills, instruction wiring, and first-party plugins. Machine-local provider credentials, MCP servers, permissions, and UI preferences are inputs or overlays that generation must preserve, not generated artifacts to overwrite. The first spec must choose and document the concrete overlay mechanism.

## Target Architecture

Claudefiles should become a shared source of workflow intent with platform-specific adapters:

```text
Shared skills, agents, rules, and policy
                  |
          +-------+--------+
          |                |
    Claude adapter    OpenCode adapter
          |                |
      ~/.claude      ~/.config/opencode
```

Shared content should remain shared where the two harnesses express the same behavior. Platform adapters should own differences in:

- instruction discovery and loading;
- agent frontmatter, permissions, and model identifiers;
- subagent dispatch and nesting;
- interactive questions and tool names;
- configuration paths;
- hook and plugin event models;
- execution isolation and concurrency guarantees.

The OpenCode output must be valid on its own. It must not rely on OpenCode silently falling back to files under `~/.claude`.

## Guiding Principles

### Correctness before breadth

One fully working OpenCode-native workflow is more valuable than many copied workflows that are only partially compatible. New migration machinery should be proven with a representative vertical slice before bulk conversion.

### Named agents enforce model policy

OpenCode selects a subagent's model from the named agent configuration; its task dispatch does not provide Claude Code's per-call model field. Cost and capability policy should therefore be expressed through named roles with explicit models and permissions, backed by task allowlists. Plugins may audit model use, but should not be the primary enforcement mechanism.

Expected role categories include:

- a low-cost worker for triage and mechanical analysis;
- a standard worker for ordinary implementation, review, and synthesis;
- explicitly expensive roles for work that justifies them;
- read-only exploration roles separated from write-capable execution roles.

Exact names and model assignments belong in the relevant spec.

### Unsupported guarantees must fail visibly

OpenCode does not currently expose Claude Code's per-dispatch worktree isolation. A conversion must not erase `isolation: "worktree"` while preserving a promise of safe parallel writers. Until an equivalent exists, write-capable subagents must run serially or through an explicitly designed external worktree mechanism.

The adapter should reject unsupported semantics rather than silently weakening them.

### Plugins replace hooks selectively

OpenCode plugins provide events such as tool execution, session lifecycle, environment injection, and compaction customization. They are not wire-compatible with Claude Code hooks. Hook migration should be based on the behavior being preserved, not on translating every shell script.

Good plugin candidates include safety guards, dispatch telemetry, selected session notifications, environment setup, and compaction context. Hooks coupled to Claude transcripts, Claude hook payloads, tmux behavior, or sudo prompting may remain Claude-only unless a real OpenCode need and sound event equivalent exist.

### Generated and local configuration need clear ownership

The integration must define which OpenCode artifacts are generated and how machine-local settings survive regeneration. Multiple sibling config files must not serve as an undocumented overlay mechanism. The chosen mechanism should be explicit, testable, and documented.

### Tests must isolate OpenCode from Claude fallback

Integration tests must use a temporary OpenCode home/configuration and disable Claude-compatible prompt and skill fallback. Otherwise, a test may pass because OpenCode loaded the original Claude artifact rather than the generated OpenCode artifact.

## Minimum Supported Workflows

The roadmap is not complete after proving only a synthetic example. At minimum, native OpenCode support must cover these existing workflow classes and representative skills:

- direct implementation through `mine-build`;
- parallel read-only review through `mine-review`;
- low-cost triage plus standard-model synthesis through `mine-challenge`;
- nested investigation through `mine-research`;
- interactive planning through `mine-define` or its current successor;
- write-capable task execution through `mine-orchestrate`, with writers serialized until worktree isolation exists;
- commit and PR workflows through `mine-commit-push` and `mine-create-pr`.

The compatibility inventory may classify other skills as portable, adapter-required, or intentionally Claude-only. Any intentionally unsupported skill must be excluded from generated OpenCode discovery and listed in the capability matrix. A later spec may update the named representatives when workflows are renamed or replaced, but it must preserve equivalent coverage of implementation, review, research, planning, orchestration, and shipping.

## Workstream Sequence

The expected delivery is five required specs, with an optional sixth for parallel writer parity. A spec may produce more than one PR when reviewability requires it, but each PR should leave the current OpenCode support usable.

### 1. Configuration Baseline and Test Harness

Establish a trustworthy foundation before changing workflow behavior.

Scope:

- define the canonical generated OpenCode config and machine-local overlay mechanism;
- consolidate or deliberately account for existing `opencode.json` and `opencode.jsonc` content;
- decide how and when Claude compatibility fallback is disabled;
- create an isolated fixture home for sync and OpenCode startup tests;
- validate generated configuration against OpenCode's published schema;
- add tests for installation, deletion of stale artifacts, and source provenance;
- define how tests observe loaded agents, skills, plugins, and child-session models.

Exit condition: tests can prove that OpenCode starts using only generated OpenCode artifacts and can identify the model used by a child session.

### 2. Native Agents and Model Enforcement

Make subagent cost and capability routing intentional before migrating workflows onto it.

Scope:

- define OpenCode-native worker roles and their model tiers;
- generate explicit `mode`, model, provider options, and native permissions;
- replace deprecated tool declarations where appropriate;
- override or restrict built-in `general` and `explore` behavior;
- use `permission.task` allowlists for orchestrating agents;
- configure and test the `subagent_depth` needed by nested workflows;
- verify direct and nested child sessions use the expected models.

Exit condition: a primary session using an expensive model cannot accidentally dispatch routine work to an equally expensive inherited model through an approved workflow.

**Status: Complete** — shipped in PR `#503` (opencode-sync Python rewrite with worker agents, config.json model enforcement, dispatch rewriter, and compatibility lint). Two originally-scoped items were dropped: permission.task allowlists (FR#8 removed — blanket allow in opencode.jsonc makes per-agent gating inert) and deprecated tool declaration replacement (no applicable declarations identified).

### 3. Skill Compatibility Adapter

Replace broad textual substitutions with a structured, testable platform adapter.

Scope:

- convert Claude agent dispatch to named OpenCode task dispatch;
- generate thin slash-command bridges only for selected user-facing skills, without copying skill bodies or falling back to Claude skill paths;
- convert interactive question syntax and platform paths;
- express parallel read-only dispatch using OpenCode-supported calls;
- route workflow model intent through named agents rather than task-local model fields;
- detect background and isolation semantics that cannot be preserved;
- add a compatibility lint for residual Claude-only constructs;
- migrate one representative workflow as a vertical slice before bulk migration;
- include the minimum OpenCode-native instruction and task-routing policy needed by that vertical slice, rather than testing it in an ungoverned environment;
- classify remaining skills as portable, adapter-required, or harness-specific.

Exit condition: generated OpenCode skills contain no unsupported Claude dispatch constructs, and the vertical-slice workflow completes with its intended instruction policy, named agents, and model routing active.

**Status: Partially complete** — dispatch rewriting and the compatibility lint shipped in the Spec 2 PR. Remaining: interactive question syntax conversion, vertical-slice-first validation, and skill classification as portable/adapter-required/harness-specific.

### 4. Instructions and Runtime Plugins

Load the intended policy and restore runtime behavior that has a sound OpenCode equivalent.

Scope:

- generate a concise OpenCode-native global `AGENTS.md`;
- complete and generalize the instruction loading introduced for the Phase 3 vertical slice;
- load applicable shared rules through OpenCode's `instructions` configuration;
- exclude Claude-only rules deliberately rather than relying on unrecognized frontmatter;
- implement selected runtime plugins for guards, telemetry, compaction context, or session behavior;
- test plugin event payloads and failure behavior;
- document each Claude hook as ported, replaced by configuration, intentionally unsupported, or deferred.

Exit condition: OpenCode receives the intended global behavior instructions, and every installed plugin preserves a documented behavior with automated coverage.

### 5. End-to-End Hardening and Documentation

Validate the integration as a product rather than a collection of converted files.

Scope:

- smoke-test exploration, review, research, nested-agent, and write-capable workflows;
- exercise every minimum supported workflow named in this roadmap;
- verify model routing and permissions from observed child sessions;
- test sync upgrades, stale file removal, restart requirements, and failure recovery;
- add OpenCode schema, version, and plugin API drift checks;
- publish a Claude/OpenCode capability matrix and maintenance instructions;
- update `REFERENCE.md`, `ONBOARDING.md`, and relevant capability routing;
- decide whether OpenCode support is ready to stop being labeled provisional.

Exit condition: supported workflows have isolated end-to-end coverage and documented behavior differences, and routine OpenCode upgrades have a defined validation path.

### 6. Optional: Worktree-Isolated Parallel Execution

This is separate because it introduces orchestration infrastructure rather than simple compatibility.

Scope:

- create isolated git worktrees for concurrent write-capable workers;
- launch independent OpenCode executions in those worktrees;
- collect results and reconcile branches safely;
- handle cleanup, cancellation, partial failure, and merge conflicts;
- integrate dispatch and run telemetry with the existing orchestration store.

Until this ships, OpenCode workflows must serialize write-capable subagents.

## Cross-Spec Invariants

Every spec in this roadmap must preserve these properties:

- Claude Code behavior must not regress merely to simplify OpenCode support.
- OpenCode artifacts must work with Claude fallback disabled.
- Routine subagent work must use an explicitly configured non-SOTA model.
- Expensive models must be attached only to named roles with a documented justification.
- Read-only and write-capable agents must have permissions matching their responsibility.
- Concurrent writers must never share a working tree without real isolation.
- Unsupported platform behavior must be reported by validation, not skipped silently.
- Generated configuration must preserve machine-local settings through a documented mechanism.
- Configuration and plugin changes require an OpenCode restart and should say so in user-facing instructions.

## Spec Author Checklist

Future specs derived from this roadmap should answer:

1. Which shared source artifacts and generated OpenCode artifacts does this change own?
2. What behavior is equivalent across harnesses, and what requires an adapter?
3. Which named agent runs each subtask, with which model and permissions?
4. Can any nested agent dispatch another agent, and what depth is required?
5. Does the workflow write files, and can any writers run concurrently?
6. Which Claude-only syntax or paths must the compatibility lint reject?
7. Is a plugin required, or can configuration provide stronger enforcement?
8. How will tests prove OpenCode did not load a Claude fallback artifact?
9. How will tests observe the actual child model and permissions?
10. What OpenCode version, schema, or experimental API assumptions are introduced?

## Completion Definition

OpenCode support is complete when supported workflows run from generated OpenCode configuration with Claude compatibility disabled; rules, skills, agents, models, permissions, nesting, and plugins are verified by isolated tests; unsupported differences are documented and enforced; and routine maintenance does not require editing generated files under `~/.config/opencode` directly.
