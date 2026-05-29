# Claudefiles

My personal [Claude Code](https://docs.anthropic.com/en/docs/claude-code) configuration — skills, commands, agents, rules, and hooks that make Claude Code better at planning, reviewing, and shipping code. Built up and refined over daily use. The core is a complete define → plan → orchestrate → ship pipeline; optional bundles add frontend design, CLI tooling, memory, and engineering specialists.

Read [ONBOARDING.md](ONBOARDING.md) to understand what's here and decide what to try first.

## Install

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/NodeJSmith/Claudefiles.git ~/Claudefiles
cd ~/Claudefiles
uv run install.py
```

The base bundle (full pipeline) always installs. The wizard asks about optional add-ons. Use `--reconfigure` to change selections, `--uninstall` to remove everything.

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- [uv](https://docs.astral.sh/uv/getting-started/installation/) — used by the installer and for package management
- The skills reference tools like `gh` (GitHub CLI), `git`, `pytest`, `ruff`, `pyright` — install what's relevant to your workflow

## Local Development

For contributing to this repo, install the shell linting tools:

- [`shellcheck`](https://github.com/koalaman/shellcheck) — shell script static analysis
- [`shfmt`](https://github.com/mvdan/sh) — shell script formatter
- [`pre-commit`](https://pre-commit.com/) — git hook framework

Then install the hooks:

```bash
pre-commit install
```

## License

MIT
