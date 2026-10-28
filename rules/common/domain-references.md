# Domain References

**BLOCKING REQUIREMENT**: Before starting work that matches a row below, Read the reference file under `${CLAUDE_CONFIG_DIR:-~/.claude}/references/common/`. Do NOT proceed with domain work without loading the relevant guidance first.

| When working with... | Read |
|----------------------|------|
| `.ts`, `.tsx`, `.js`, `.jsx` files | `typescript.md` |
| Frontend components, CSS, UI | `frontend.md` |
| Backend services, async code, retries | `reliability.md`, `dependency-injection.md` |
| Tests, TDD, pytest | `testing.md` |
| Prose: PR descriptions, docs, skills, rules | `writing-quality.md` |
| Subagent orchestration, parallel executors | `agents.md` |
| Processing code review findings | `receiving-code-review.md` |
| Writing rules or skill files | `instruction-quality.md` |
| Asking the user to pick among options with a recommendation | `presenting-decisions.md` |
| API endpoints, auth handlers, user input | `security.md` |
| User-facing CLI tools: commands with flags, subcommands, help text, output design | `cli-ux.md` |
| Authoring `REVIEW.md` review-question files | `review-questions.md` |
