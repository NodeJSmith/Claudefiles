#!/usr/bin/env bash
# Git pre-commit hook: block commits containing secrets or credentials.
#
# Scans staged diffs for common secret patterns. Truncates matched lines
# to avoid echoing full secrets in terminal output.
#
# Installation (per-repo):
#   cp scripts/hooks/secrets-check.sh <repo>/.git/hooks/pre-commit
#   chmod +x <repo>/.git/hooks/pre-commit
#
# Or with pre-commit framework (.pre-commit-config.yaml):
#   - repo: local
#     hooks:
#       - id: secrets-check
#         name: secrets-check
#         entry: scripts/hooks/secrets-check.sh
#         language: script
#         stages: [pre-commit]
#
# Override: SKIP_SECRETS_CHECK=1 git commit -m "..."
#   Use only when the match is a known false positive.

set -euo pipefail

if [[ "${SKIP_SECRETS_CHECK:-0}" == "1" ]]; then
  exit 0
fi

# Patterns: name<tab>regex
# Each line is a category and an extended-grep pattern to match against staged diffs.
PATTERNS=(
  # Provider API keys
  "Anthropic API key	sk-ant-[a-zA-Z0-9_-]{20,}"
  "OpenAI API key	sk-[a-zA-Z0-9]{20,}"
  "GitHub token (classic)	ghp_[a-zA-Z0-9]{36}"
  "GitHub token (fine-grained)	github_pat_[a-zA-Z0-9_]{22,}"
  "GitHub server token	ghs_[a-zA-Z0-9]{36}"
  "GitHub OAuth token	gho_[a-zA-Z0-9]{36}"
  "GitHub user token	ghu_[a-zA-Z0-9]{36}"
  "GitHub refresh token	ghr_[a-zA-Z0-9]{36}"
  "Stripe secret key	sk_live_[a-zA-Z0-9]{24,}"
  "Stripe publishable key	pk_live_[a-zA-Z0-9]{24,}"
  "Stripe restricted key	rk_live_[a-zA-Z0-9]{24,}"
  "AWS access key	AKIA[0-9A-Z]{16}"
  "Slack bot token	xoxb-[0-9]{10,}-[a-zA-Z0-9-]+"
  "Slack user token	xoxp-[0-9]{10,}-[a-zA-Z0-9-]+"
  "Slack app token	xoxa-[0-9]{10,}-[a-zA-Z0-9-]+"
  "Slack export token	xoxe-[0-9]{10,}-[a-zA-Z0-9-]+"
  "Slack refresh token	xoxr-[0-9]{10,}-[a-zA-Z0-9-]+"
  "Google API key	AIza[0-9A-Za-z_-]{35}"
  "Twilio API key	SK[0-9a-fA-F]{32}"
  "SendGrid API key	SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}"
  "Mailgun API key	key-[0-9a-zA-Z]{32}"
  "npm token	npm_[a-zA-Z0-9]{36}"
  "PyPI token	pypi-[a-zA-Z0-9_-]{50,}"
  "Telegram bot token	[0-9]{8,10}:[a-zA-Z0-9_-]{35}"
  "Discord bot token	[MN][a-zA-Z0-9_-]{23,}\.[a-zA-Z0-9_-]{6}\.[a-zA-Z0-9_-]{27,}"

  # Generic secrets
  "JWT token	eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"
  "Private key header	-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"
  "Generic high-entropy secret	(password|passwd|secret|token|api_key|apikey|api-key|auth_token|access_token|client_secret)[[:space:]]*[=:][[:space:]]*['\"][^[:space:]'\"]{8,}['\"]"

  # Service account JSON (matched against diff content, like other PATTERNS entries)
  "Service account JSON	\"type\":[[:space:]]*\"service_account\""
)

# File-name patterns checked against staged file list (not diff content)
DANGEROUS_FILES=(
  '\.env$'
  '\.env\.local$'
  '\.env\.production$'
  'id_rsa$'
  'id_ed25519$'
  'id_ecdsa$'
  'id_dsa$'
  '\.pem$'
  '\.key$'
  '\.p12$'
  '\.pfx$'
  '\.jks$'
  '\.keystore$'
  'credentials\.json$'
  'service[_-]account.*\.json$'
)

found=0
findings=""

staged_files=$(git diff --cached --name-only --diff-filter=ACMR 2> /dev/null) || true

if [[ -n "$staged_files" ]]; then
  for pattern in "${DANGEROUS_FILES[@]}"; do
    matches=$(grep -E "$pattern" <<< "$staged_files" 2> /dev/null || true)
    if [[ -n "$matches" ]]; then
      found=1
      while IFS= read -r file; do
        findings+="  [BLOCKED] Dangerous file staged: ${file}\n"
      done <<< "$matches"
    fi
  done
fi

diff_output=$(git diff --cached --diff-filter=ACMR -U0 2> /dev/null) || true

if [[ -n "$diff_output" ]]; then
  for entry in "${PATTERNS[@]}"; do
    name="${entry%%	*}"
    pattern="${entry#*	}"

    matches=$(grep -nEo "^\+.*${pattern}" <<< "$diff_output" 2> /dev/null || true)
    if [[ -n "$matches" ]]; then
      found=1
      while IFS= read -r line; do
        truncated="${line:0:80}"
        if [[ ${#line} -gt 80 ]]; then
          truncated="${truncated}..."
        fi
        findings+="  [BLOCKED] ${name}: ${truncated}\n"
      done <<< "$matches"
    fi
  done
fi

if [[ $found -eq 1 ]]; then
  echo "secrets-check: potential credentials detected in staged changes"
  echo ""
  printf '%b' "$findings"
  echo "If these are false positives, re-run with: SKIP_SECRETS_CHECK=1 git commit ..."
  exit 1
fi

exit 0
