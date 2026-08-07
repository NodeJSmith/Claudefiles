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

For contributing to this repo, install the shell linting tools and [`mise`](https://mise.jdx.dev/):

- [`shellcheck`](https://github.com/koalaman/shellcheck) — shell script static analysis
- [`shfmt`](https://github.com/mvdan/sh) — shell script formatter
- [`mise`](https://mise.jdx.dev/getting-started.html) — installs [`prek`](https://github.com/j178/prek), the git hook runner, and runs the per-package test tasks

Then install the hooks:

```bash
mise install
prek install -t pre-commit -t pre-push
```

Run everything manually with `prek run --all-files`, or just the test suites with `mise run 'test:*'`.

## License

MIT
