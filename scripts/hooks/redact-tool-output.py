#!/usr/bin/env python3
# Source: https://github.com/SilentAutomaton/redact-hook (MIT) — check here for upstream updates.
"""PostToolUse/PostToolUseFailure hook: redact secrets and PII from tool output
before Claude sees it. Registered on both events (settings.json) because a
failed Bash command's stdout/stderr — a `curl -v`, a failed login, a CLI error
echoing a token — carries secrets just as often as a successful one's.

Reads stdin JSON {tool_name, tool_input, tool_response, hook_event_name}, writes
{"hookSpecificOutput": {...}} to stdout with the secret-bearing values replaced.

Every rule has a name, and every replacement says which rule fired
([REDACTED:stripe]), so the rule to switch off is visible in the output itself.
Pick the active rules in $CLAUDE_CONFIG_DIR/redact.toml (or ~/.claude/redact.toml
if that var is unset); `--list-rules` prints them.

Run `redact-tool-output.py --self-check` to verify both directions: known secret
shapes get cut, and ordinary code/output is not.

Adapted from https://github.com/SilentAutomaton/redact-hook (MIT), which itself
credits rule shapes from gitleaks and detect-secrets. See "Limitations" below —
this hook protects the model's context and the transcript, not the network: the
tool has already run and any side effects have already happened by the time this
fires, and it does nothing for @-mention file expansion, which bypasses hooks
entirely (see l-mb/claude-code-redaction-hooks for that gap in detail).

This is a different interception point than scripts/hooks/secrets-check.sh (a
git pre-commit hook scanning staged diff content before a commit), not a
replacement for it — but the two independently hardcode overlapping vendor
prefixes (GitHub, Stripe, Slack, AWS, etc.). Adding a vendor format to one is
worth checking the other for the same gap.
"""

import copy
import ipaddress
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Callable
from math import log2
from typing import NamedTuple

try:
    import tomllib
except ImportError:  # config file needs Python 3.11
    tomllib = None

_PREFIX = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(dckr_pat_|tok_|sk-|ghp_|gho_|ghs_|ghu_|ghr_|github_pat_|AKIA|hf_"
    r"|xoxb-|xoxp-|xoxa-|xoxe-|xoxr-|Bearer\s+"
    r"|SG\."  # SendGrid
    r"|npm_"  # npm
    r"|pypi-"  # PyPI
    r"|hvs\."  # HashiCorp Vault service token
    r"|hvb\."  # HashiCorp Vault batch token
    r"|glpat-"  # GitLab Personal Access Token
    r"|gldt-"  # GitLab Deploy Token
    r"|xapp-"  # Slack app token
    r"|whsec_"  # Stripe webhook secret
    r"|pat_v\d+\."  # GitHub fine-grained PAT
    r")"
    r"([A-Za-z0-9_\-\.]{8,})",
    re.IGNORECASE,
)

# Mailgun API key: key- + a ~30-char lowercase-alnum token (e.g.
# key-3ax6xnjp29jd6fds4gc373sgvjxteol). Kept out of the generic _PREFIX
# alternation (and given its own value-shape check, not just a length/digit
# check) because "key-" is a common substring of ordinary identifiers
# (key-rotation-v2) that a boundary anchor alone can't rule out.
_MAILGUN_KEY = re.compile(r"(?<![A-Za-z0-9_])(key-)([a-z0-9]{28,40})\b")

# Resend API key: re_ + a long random token. "re_" is a common substring of
# ordinary identifiers (future_annotations_enabled contains "re_" mid-word),
# so this needs the same boundary anchor as Mailgun above.
_RESEND_KEY = re.compile(r"(?<![A-Za-z0-9_])(re_)([A-Za-z0-9_]{20,})\b")

# Twilio API key SID: SK + 32 hex chars. Kept out of the generic _PREFIX
# alternation — "SK" is only two characters, far too short/common a substring
# (ASKED, TASK, DESK, MASK) for a boundary anchor alone to make safe, so it
# needs the same dedicated value-shape check as Mailgun/Resend above.
_TWILIO_KEY = re.compile(r"(?<![A-Za-z0-9_])(SK)([0-9a-fA-F]{32})\b")

# AmneziaWG fake init-packet blobs: I1 = <b 0x...hex...>
_AWG_INIT = re.compile(r"<b\s+0x[a-fA-F0-9]{20,}>")

# AmneziaWG obfuscation params — reveal handshake fingerprint
_AWG_PARAMS = re.compile(
    r"^(Jc|Jmin|Jmax|S1|S2|H1|H2|H3|H4)(\s*=\s*)\d+",
    re.MULTILINE,
)

# Docker registry auth blob in config.json
_DOCKER_AUTH = re.compile(r'("auth"\s*:\s*")[A-Za-z0-9+/]{20,}={0,2}(")')

# Separator must be a real = or : on the same line. A bare space used to join a
# keyword to whatever followed it on the next line. The optional quote before
# the separator handles JSON/TOML's quoted keys ("access_token": "..."),
# which otherwise sit between the keyword and the separator and block the match.
_ASSIGNMENT = re.compile(
    r"(?<![A-Za-z])"
    r"(password|passwd|secret|api_key|apikey|access_key|private_key|privatekey"
    r"|presharedkey|auth_key|auth_token|access_token|client_secret|token|psk|bearer)"
    r'["\']?[ \t]*[:=][ \t]*'
    r'["\']?([A-Za-z0-9._\-/+]{6,})["\']?(?!\s*\()',
    re.IGNORECASE,
)

# WireGuard / NaCl base64 keys. Anchored to the field name: a bare 44-char
# base64 run is any base64, not a key.
_WG_KEY = re.compile(
    r"((?:Private|Public|Preshared|Peer)Key\s*=\s*)[A-Za-z0-9+/]{43}=",
    re.IGNORECASE,
)

# bcrypt / argon2 / scrypt hashes — offline-crackable, treat as secrets
_HASH = re.compile(
    r"\$2[aby]\$\d{2}\$[A-Za-z0-9./]{53}"
    r"|\$(?:argon2(?:id|i|d)|scrypt)\$[A-Za-z0-9$,=+/._\-]{20,}"
    r"|\$(?:1|5|6|7|y|gy|apr1|md5|sha1)\$[A-Za-z0-9./$,=+_\-]{12,}"
)

# note: DOTALL needed — private keys span multiple lines
_SSH_KEY = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----"
    r".*?"
    r"-----END [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----",
    re.DOTALL,
)

# Credentials in a URL, any scheme: postgresql://, amqp://, clickhouse://,
# sftp://, ldap://. The user name stays; only the password is the secret.
# Scheme is bounded to 20 chars (real schemes are well under that) so a long
# run of scheme-charset text with no "://" anywhere — a minified file, a
# base64 blob — can't force O(n^2) backtracking across every start position.
_CONN_STR = re.compile(r"([a-z][a-z0-9+.\-]{0,20}://[^\s/:@]+:)[^\s/@]+@")

_JWT = re.compile(
    r"eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"
)

# PII. Phones need the + so version strings and ids are left alone; cards are
# checked by Luhn and by issuer digit, which rules out unix timestamps.
_PHONE = re.compile(r"(?<![\d+])\+\d[\d\s().\-]{7,17}\d(?!\d)")
_CARD = re.compile(r"(?<![\d.])([3-6](?:[ -]?\d){12,18})(?![\d.])")

# Vendor formats. Each is anchored to a prefix no ordinary string carries.
_GOOGLE_API_KEY = re.compile(r"AIza[0-9A-Za-z_\-]{4,}")
_GCP_KEY_ID = re.compile(r'("private_key_id"\s*:\s*")[a-f0-9]{8,}')
_STRIPE = re.compile(r"\b(?:sk|rk|pk)_(?:live|test)_[0-9A-Za-z]{16,}")
_DIGITALOCEAN = re.compile(r"\bdo[opr]_v1_[a-f0-9]{8,}")
_AZURE_STORAGE = re.compile(r"(AccountKey=)[A-Za-z0-9+/]{60,}={0,2}", re.IGNORECASE)
_SLACK_WEBHOOK = re.compile(r"(hooks\.slack\.com/services/)[A-Za-z0-9/]{20,}")
_DISCORD_WEBHOOK = re.compile(r"(discord(?:app)?\.com/api/webhooks/\d+/)[\w\-]{20,}")
_TELEGRAM_BOT = re.compile(r"(?:(?<=/bot)|(?<!\w))\d{8,}:AA[\w\-]*")
# MTProto application credentials and Telethon/Pyrogram session strings. The
# session string alone is a full account takeover, so it outranks the bot token.
_TELEGRAM_API_HASH = re.compile(
    r'((?:api_hash|app_hash|tg_api_hash)\s*[:=]\s*["\']?)[a-f0-9]{8,}',
    re.IGNORECASE,
)
_TELEGRAM_SESSION = re.compile(
    r'((?:string_?session|session_?string|session)\s*[:=]\s*["\']?)[A-Za-z0-9+/=_\-]{80,}',
    re.IGNORECASE,
)

# HTTP request auth. Shows up in `curl -v`, in proxy logs, in MCP transports.
_BASIC_AUTH = re.compile(
    r"(Authorization:\s*Basic\s+)[A-Za-z0-9+/=]{8,}", re.IGNORECASE
)
_AUTH_HEADER = re.compile(
    r"((?:X-)?(?:Api|Auth|Access|Session)[-_](?:Key|Token|Secret)\s*:\s*)\S{8,}",
    re.IGNORECASE,
)
_COOKIE = re.compile(
    r"((?:Set-)?Cookie:[^\n]*?\b\w*(?:session|sid|token|csrf|auth)\w*\s*=\s*)[^;\s]{8,}",
    re.IGNORECASE,
)

# Credentials on a command line or in ~/.netrc.
_CLI_USERPASS = re.compile(r"((?:-u|--user)\s+[^\s:]+:)\S+")
_CLI_PASSWORD = re.compile(r"(--(?:password|pass|token|api-key)[= ])\S{4,}")
_NETRC = re.compile(
    r"(machine\s+\S+(?:\s+(?:login|account)\s+\S+)?\s+password\s+)\S+",
    re.IGNORECASE,
)

# A password handed straight to a password-setting command. Anchored to the
# command name: a quoted string on its own is prose.
_PW_COMMAND = re.compile(
    r"\b(wgpw|htpasswd|chpasswd|smbpasswd|mkpasswd|openssl\s+passwd)"
    r'([^\n\'"]{0,60}[\'"])([^\'"\n]{4,})([\'"])'
)


# Key material the PEM rule does not cover.
_PUTTY_PPK = re.compile(r"(Private-Lines:\s*\d+\s*\n)(?:[A-Za-z0-9+/=]+[ \t]*\n?)+")
_K8S_KEY_DATA = re.compile(
    r"((?:client-key-data|client-certificate-data)\s*:\s*)[A-Za-z0-9+/=]{20,}"
)
# A wallet seed is 12-24 short words. Anchored to the field name, because a
# bare run of English words is prose.
_BIP39_SEED = re.compile(
    r"((?:mnemonic|seed(?:\s+phrase)?|recovery(?:\s+phrase)?)\s*[:=]\s*)"
    r"(?:[a-z]{3,8}\s+){11,23}[a-z]{3,8}",
    re.IGNORECASE,
)

# Environment variable names. Uppercase only: that is what keeps the Python
# keyword `pass` and argparse's `--token` out of it.
_ENV_SECRET = re.compile(
    r"\b(?![A-Z0-9_]*PUBLIC)((?:[A-Z][A-Z0-9]*_)*(?:PASS|PASSWD|PWD|PASSPHRASE|CREDS|CREDENTIALS"
    r"|SECRET|TOKEN|APIKEY|KEY|DSN|PAT)"
    r"|PGPASSWORD|MYSQL_PWD|SECRET_KEY_BASE)"
    r'[ \t]*=[ \t]*["\']?([^\s"\']{4,})',
)
# Two words that mean one thing in any case. `key` and `auth` are not here on
# purpose; they appear in ordinary code far more often than in secrets.
_SECRET_WORD = re.compile(
    r'\b(passphrase|credentials)["\']?\s*[:=]\s*["\']?([A-Za-z0-9._\-/+]{6,})["\']?',
    re.IGNORECASE,
)

# Identity. Off by default: cutting paths and mail addresses breaks ordinary
# work with git log, stack traces and CODEOWNERS.
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
_HOME_PATH = re.compile(r'(/(?:home|Users))/[^/\s:"\']+')
_MAC_ADDR = re.compile(r"\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b")
_PUBLIC_IP = re.compile(
    r"\b(?!10\.)(?!127\.)(?!0\.)(?!255\.)(?!169\.254\.)(?!192\.168\.)"
    r"(?!172\.(?:1[6-9]|2\d|3[01])\.)"
    r"\d{1,3}(?:\.\d{1,3}){3}\b"
)

# IPv6. Match the shape, then let ipaddress decide: is_global already rules out
# loopback, link-local, unique-local and the 2001:db8::/32 documentation range.
_PUBLIC_IP6 = re.compile(
    r"(?<![:.\w])[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{0,4}){2,7}(?![:.\w])"
)

# Phone numbers without a country code. Opt-in: this is the shape that also
# fits part numbers and ticket ids, which is why the default rule needs the +.
_PHONE_LOOSE = re.compile(
    r"(?<![\d\-.])(?:\(\d{3}\)[ .\-]?|\d{1,3}[ .\-])?\d{3}[ .\-]\d{2,3}[ .\-]\d{2,4}(?![\d\-.])"
)

# Entropy. Only assignment values, never bare text, and never after a hash
# label. Off by default: it misses about a third of real secrets and invents
# false positives, so the named rules above do the real work.
_ENTROPY = re.compile(
    r"(?<!h1)(?<!md5)(?<!sha1)(?<!sha256)(?<!sha512)"
    r'([:=]\s*["\']?)([A-Za-z0-9+/_\-]{16,128})'
)
_ENTROPY_SKIP = re.compile(
    r"^(?:[0-9a-f]{7,64}"  # git sha, digest
    r"|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"  # uuid
    r"|[\d._\-]+"  # numbers, versions
    r"|v?\d[\w.\-+]*)$",  # v1.24.3+build
    re.IGNORECASE,
)


def _random_enough(value: str) -> bool:
    """A secret is long or has digits. `re.compile` and `npm_check.py` are neither."""
    return len(value) >= 16 or any(c.isdigit() for c in value)


def _luhn_ok(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        digit = int(char)
        if index % 2:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _redact_card(match: re.Match) -> str:
    digits = re.sub(r"[ -]", "", match.group(1))
    if 13 <= len(digits) <= 19 and _luhn_ok(digits):
        return "[REDACTED:card]"
    return match.group(0)


def _shannon(value: str) -> float:
    counts = Counter(value)
    size = len(value)
    return -sum((n / size) * log2(n / size) for n in counts.values())


def _redact_entropy(match: re.Match) -> str:
    value = match.group(2)
    if _ENTROPY_SKIP.match(value) or _shannon(value) < 3.5:
        return match.group(0)
    return match.group(1) + "[REDACTED:entropy]"


def _redact_ip6(match: re.Match) -> str:
    try:
        address = ipaddress.IPv6Address(match.group(0))
    except ValueError:
        return match.group(0)
    return "[REDACTED:public_ip6]" if address.is_global else match.group(0)


def _redact_pw_command(match: re.Match) -> str:
    value = match.group(3)
    if value.startswith("$") or not _random_enough(value):
        return match.group(0)
    return f"{match.group(1)}{match.group(2)}[REDACTED:pw_command]{match.group(4)}"


def _keyed(name: str) -> Callable[[re.Match], str]:
    """Assignment-shaped rules: cut the value only when it looks random."""

    def repl(match: re.Match) -> str:
        if not _random_enough(match.group(2)):
            return match.group(0)
        return f"{match.group(1)}=[REDACTED:{name}]"

    return repl


def _prefixed(match: re.Match) -> str:
    """Prefix-shaped rules: cut the value only when it looks random."""
    if not _random_enough(match.group(2)):
        return match.group(0)
    return match.group(1) + "[REDACTED:prefix]"


def _vendor_prefixed(name: str) -> Callable[[re.Match], str]:
    """For a vendor rule whose pattern already enforces a specific value
    shape (fixed length, character set) via its own regex. Unlike _prefixed,
    this always redacts on a match — there's no _random_enough gate to skip,
    because the shape check already ruled out ordinary identifiers."""

    def repl(match: re.Match) -> str:
        return f"{match.group(1)}[REDACTED:{name}]"

    return repl


class Rule(NamedTuple):
    name: str
    pattern: re.Pattern
    repl: (
        str | Callable[[re.Match], str]
    )  # replacement template, or a callable taking the match
    on: bool = True  # part of the default set


# Order matters. Structural and vendor rules run before the generic assignment
# and prefix rules, so the placeholder names the most specific rule that fits.
#
# Adding a rule touches up to four places: the compiled pattern above, an
# optional custom callable above that, the Rule(...) entry below (position
# also encodes execution order), and a _MUST_CUT fixture — self_check() fails
# if a default rule has no fixture, so that step isn't optional.
_RULES = (
    Rule("ssh_key", _SSH_KEY, "[REDACTED:ssh_key]"),
    Rule("putty_ppk", _PUTTY_PPK, "\\1[REDACTED:putty_ppk]\n"),
    Rule("awg_init", _AWG_INIT, "[REDACTED:awg_init]"),
    Rule("awg_params", _AWG_PARAMS, "\\1\\2[REDACTED:awg_params]"),
    Rule("wg_key", _WG_KEY, "\\1[REDACTED:wg_key]"),
    Rule("hash", _HASH, "[REDACTED:hash]"),
    Rule("docker_auth", _DOCKER_AUTH, "\\1[REDACTED:docker_auth]\\2"),
    Rule("k8s_key_data", _K8S_KEY_DATA, "\\1[REDACTED:k8s_key_data]"),
    Rule("gcp_key_id", _GCP_KEY_ID, "\\1[REDACTED:gcp_key_id]"),
    Rule("azure_storage", _AZURE_STORAGE, "\\1[REDACTED:azure_storage]"),
    Rule("google_api_key", _GOOGLE_API_KEY, "[REDACTED:google_api_key]"),
    Rule("stripe", _STRIPE, "[REDACTED:stripe]"),
    Rule("digitalocean", _DIGITALOCEAN, "[REDACTED:digitalocean]"),
    Rule("mailgun_key", _MAILGUN_KEY, _vendor_prefixed("mailgun_key")),
    Rule("resend_key", _RESEND_KEY, _vendor_prefixed("resend_key")),
    Rule("twilio_key", _TWILIO_KEY, _vendor_prefixed("twilio_key")),
    Rule("telegram_bot", _TELEGRAM_BOT, "[REDACTED:telegram_bot]"),
    Rule("telegram_session", _TELEGRAM_SESSION, "\\1[REDACTED:telegram_session]"),
    Rule("telegram_api_hash", _TELEGRAM_API_HASH, "\\1[REDACTED:telegram_api_hash]"),
    Rule("slack_webhook", _SLACK_WEBHOOK, "\\1[REDACTED:slack_webhook]"),
    Rule("discord_webhook", _DISCORD_WEBHOOK, "\\1[REDACTED:discord_webhook]"),
    Rule("basic_auth", _BASIC_AUTH, "\\1[REDACTED:basic_auth]"),
    Rule("auth_header", _AUTH_HEADER, "\\1[REDACTED:auth_header]"),
    Rule("cookie", _COOKIE, "\\1[REDACTED:cookie]"),
    Rule("netrc", _NETRC, "\\1[REDACTED:netrc]"),
    Rule("cli_userpass", _CLI_USERPASS, "\\1[REDACTED:cli_userpass]"),
    Rule("cli_password", _CLI_PASSWORD, "\\1[REDACTED:cli_password]"),
    Rule("pw_command", _PW_COMMAND, _redact_pw_command),
    Rule("bip39_seed", _BIP39_SEED, "\\1[REDACTED:bip39_seed]"),
    Rule("env_secret", _ENV_SECRET, _keyed("env_secret")),
    Rule("secret_word", _SECRET_WORD, _keyed("secret_word")),
    # note: assignment before prefix — avoids double-[REDACTED] when both match same value
    Rule("assignment", _ASSIGNMENT, _keyed("assignment")),
    Rule("prefix", _PREFIX, _prefixed),
    Rule("conn_str", _CONN_STR, "\\1[REDACTED:conn_str]@"),
    Rule("jwt", _JWT, "[REDACTED:jwt]"),
    Rule("phone", _PHONE, "[REDACTED:phone]"),
    Rule("card", _CARD, _redact_card),
    # Off by default.
    Rule("email", _EMAIL, "[REDACTED:email]", False),
    Rule("ssn", _SSN, "[REDACTED:ssn]", False),
    Rule("iban", _IBAN, "[REDACTED:iban]", False),
    Rule("home_path", _HOME_PATH, "\\1/[REDACTED:home_path]", False),
    Rule("mac_addr", _MAC_ADDR, "[REDACTED:mac_addr]", False),
    Rule("public_ip", _PUBLIC_IP, "[REDACTED:public_ip]", False),
    Rule("public_ip6", _PUBLIC_IP6, _redact_ip6, False),
    Rule("phone_loose", _PHONE_LOOSE, "[REDACTED:phone_loose]", False),
    Rule("entropy", _ENTROPY, _redact_entropy, False),
)

_DEFAULT_RULES = tuple(rule for rule in _RULES if rule.on)


def _guard(repl, allow):
    """Single place the allowlist applies: an allowed match is left alone."""

    def sub(match: re.Match) -> str:
        if any(pattern.search(match.group(0)) for pattern in allow):
            return match.group(0)
        return repl(match) if callable(repl) else match.expand(repl)

    return sub


def redact_regex(text: str, rules=None, allow=()) -> str:
    for rule in _DEFAULT_RULES if rules is None else rules:
        text = rule.pattern.sub(_guard(rule.repl, allow), text)
    return text


def _env_list(name: str) -> set:
    return {
        part.strip() for part in os.environ.get(name, "").split(",") if part.strip()
    }


def _config_path() -> str:
    """$CLAUDE_CONFIG_DIR/redact.toml, then the old ~/.claude/redact.toml."""
    if os.environ.get("REDACT_CONFIG"):
        return os.environ["REDACT_CONFIG"]
    default = os.path.expanduser("~/.claude/redact.toml")
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if not config_dir:
        return default
    path = os.path.join(os.path.expanduser(config_dir), "redact.toml")
    return path if os.path.exists(path) else default


def load_config() -> dict:
    """A broken config must never take the hook down."""
    path = _config_path()
    if not os.path.exists(path):
        return {}
    if tomllib is None:
        print(
            "redact: config needs Python 3.11 or newer, using defaults", file=sys.stderr
        )
        return {}
    try:
        with open(path, "rb") as handle:
            return tomllib.load(handle)
    except (tomllib.TOMLDecodeError, OSError) as exc:
        print(f"redact: cannot read {path}: {exc}", file=sys.stderr)
        return {}


def _ensure_list(value, key: str) -> list:
    """A malformed config (e.g. `[rule]` table instead of `[[rule]]` array, or
    a scalar `enable`) must fall back to empty, not crash the hook downstream
    with an AttributeError/TypeError — same "broken config never takes the
    hook down" contract as load_config()'s own error handling."""
    if isinstance(value, list):
        return value
    if value is not None:
        print(f"redact: config key {key!r} must be a list, ignoring", file=sys.stderr)
    return []


def active_rules(config: dict) -> tuple:
    off = set(_ensure_list(config.get("disable"), "disable")) | _env_list(
        "REDACT_DISABLE"
    )
    on = set(_ensure_list(config.get("enable"), "enable")) | _env_list("REDACT_ENABLE")
    if os.environ.get("REDACT_AGGRESSIVE"):
        on.add("entropy")
    rules = [r for r in _RULES if (r.on or r.name in on) and r.name not in off]
    for spec in _ensure_list(config.get("rule"), "rule"):
        if not isinstance(spec, dict):
            print(
                f"redact: skipping malformed [[rule]] entry: {spec!r}", file=sys.stderr
            )
            continue
        name = spec.get("name", "custom")
        if name in off:
            continue
        try:
            pattern = re.compile(spec["pattern"])
        except (KeyError, re.error) as exc:
            print(f"redact: skipping rule {name!r}: {exc}", file=sys.stderr)
            continue
        rules.append(Rule(name, pattern, spec.get("replacement", f"[REDACTED:{name}]")))
    return tuple(rules)


def allow_patterns(config: dict) -> tuple:
    out = []
    for expr in _ensure_list(config.get("allow"), "allow"):
        if not isinstance(expr, str):
            print(f"redact: skipping malformed allow entry: {expr!r}", file=sys.stderr)
            continue
        try:
            out.append(re.compile(expr))
        except re.error as exc:
            print(f"redact: skipping allow {expr!r}: {exc}", file=sys.stderr)
    return tuple(out)


def build_updated_response(data: dict, rules: tuple, allow: tuple) -> dict | str:
    """Reconstruct tool_response with redacted content. CC validates against tool outputSchema.

    Only Read's and Bash's shapes are understood well enough to rewrite safely. A
    dict-shaped response in neither shape (Edit/Write, Agent, an MCP tool with its
    own schema) is returned untouched rather than collapsed to a bare string —
    replacing a structured response with a string previously corrupted output for
    every tool that isn't Read or Bash, which is why the PostToolUse hook's
    matcher in settings.json stays scoped to `Read|Bash` rather than every tool.

    stdout and stderr are redacted independently: joining them into one string
    before redaction (as the upstream script this was adapted from did) redacts
    the combined text but only ever writes the result back into `stdout`, so a
    secret in `stderr` — a curl -v auth header, a failed-login password, a CLI
    error echoing a token — passed through completely unredacted.

    PostToolUseFailure carries no `tool_response` at all — the failure detail
    is a top-level `error` string instead (confirmed against this repo's own
    fixture at tests/test_hooks.py's test_captures_failed_command, and the
    Claude Code hooks reference). Redacting that string is what
    `updatedToolOutput` rewrites for this event, same field name as PostToolUse.
    """
    if data.get("hook_event_name") == "PostToolUseFailure":
        return redact_regex(str(data.get("error", "")), rules, allow)
    resp = data.get("tool_response")
    if isinstance(resp, dict):
        # Read tool: {"type": "text", "file": {"content": "...", ...}}
        if "file" in resp and isinstance(resp["file"], dict):
            updated = copy.deepcopy(resp)
            content = redact_regex(str(resp["file"].get("content", "")), rules, allow)
            updated["file"]["content"] = content
            # totalLines describes the whole source file (set by the Read tool,
            # not by us) and must survive untouched, including for an
            # offset/limit partial read — overwriting it with the returned
            # chunk's line count falsely reports EOF. numLines describes only
            # the returned chunk, so it's the one value redaction can change,
            # and only when a multiline secret collapses into one placeholder.
            updated["file"]["numLines"] = len(content.splitlines())
            return updated
        # Bash tool: {"stdout": "...", "stderr": "...", ...}
        if "stdout" in resp:
            updated = copy.deepcopy(resp)
            updated["stdout"] = redact_regex(str(resp.get("stdout", "")), rules, allow)
            if resp.get("stderr"):
                updated["stderr"] = redact_regex(str(resp["stderr"]), rules, allow)
            return updated
        # Unrecognized dict shape: leave it alone rather than guess.
        return resp
    # plain string (MCP tools, older CC versions)
    if isinstance(resp, list):
        return redact_regex(json.dumps(resp), rules, allow)
    return redact_regex(str(resp), rules, allow)


_SKIP_TOOLS = frozenset(
    os.environ.get("REDACT_SKIP_TOOLS", "WebFetch,WebSearch").split(",")
)

# One sample per default rule. Every value here is invented.
_MUST_CUT = [
    (
        "ssh_key",
        "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXk=\n-----END OPENSSH PRIVATE KEY-----",
    ),
    ("putty_ppk", "Private-Lines: 2\nAAAAgQCabcdefghijklmnop\nQQQQbbbbccccddddeeee\n"),
    ("awg_init", "I1 = <b 0x52454347abcdef0123456789abcdef>"),
    ("awg_params", "Jc = 5\nJmin = 10\nS1 = 37"),
    ("wg_key", "PresharedKey = AbCdEf0123456789ghijklmnopqrstuvwxyzABCDEFG="),
    ("hash", "root:$2b$12$AbCdEf0123456789ghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ:0:0"),
    (
        "docker_auth",
        '{"auths":{"registry.local":{"auth":"dXNlcjpteXBhc3N3b3JkMTIzNDU2"}}}',
    ),
    (
        "k8s_key_data",
        "    client-key-data: LS0tLS1CRUdJTiBSU0EgUFJJVkFURSBLRVktLS0tLQo=",
    ),
    ("gcp_key_id", '"private_key_id": "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b"'),
    (
        "azure_storage",
        "AccountKey=AbCdEf0123456789ghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ012==",
    ),
    ("google_api_key", "GOOGLE_MAPS AIzaAbCdEf0123456789ghijklmnopqrstuvwxy"),
    ("stripe", "charge with sk_live_AbCdEf0123456789ghij"),
    # Assembled, never written out: a literal do*_v1_ fixture trips secret scanners.
    ("digitalocean", "token " + "do" + "p_v1_" + "d0" * 32),
    ("telegram_bot", "bot 123456789:AAAbCdEf0123456789ghijklmnopqrstuvw"),
    (
        "telegram_bot",
        "https://api.telegram.org/bot123456789:AAAbCdEf0123456789ghijklmnopqrstuvw/sendMessage",
    ),
    (
        "telegram_session",
        "SESSION_STRING=1BVtsOKcBu0YAbCdEf0123456789ghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcd",
    ),
    ("telegram_api_hash", "api_hash = 0123456789abcdef0123456789abcdef"),
    (
        "slack_webhook",
        "https://hooks.slack.com/services/T00000000/B00000000/AbCdEf0123456789ghij",
    ),
    (
        "discord_webhook",
        "https://discord.com/api/webhooks/123456789012345678/AbCdEf0123456789ghij",
    ),
    ("basic_auth", "Authorization: Basic dXNlcjpzZWNyZXRwYXNzd29yZA=="),
    ("auth_header", "X-Api-Key: AbCdEf0123456789ghij"),
    ("cookie", "Set-Cookie: sessionid=8xk2mfq9wz1p4v7b3n5j6h0g; Path=/"),
    ("netrc", "machine api.example.com login bob password s3cr3tpassw0rd"),
    ("cli_userpass", "curl -u admin:s3cr3tpassw0rd https://api.example.com"),
    ("cli_password", "mysqldump --password=s3cr3tpassw0rd appdb"),
    ("pw_command", "docker run wg-easy wgpw 'Tr0ub4dor-Stapler-91'"),
    ("hash", "root:$6$rounds=5000$abcdefgh$" + "x" * 86 + ":19000:0:99999:7:::"),
    (
        "bip39_seed",
        "mnemonic: legal winner thank year wave sausage worth useful legal winner thank yellow",
    ),
    ("env_secret", "DB_PASS=hunter2xyz"),
    ("secret_word", "passphrase=correcthorsebattery"),
    ("assignment", "password=hunter2xyz"),
    ("prefix", "pushed with ghp_AbCdEf0123456789ghijklmnopqrstuvwxyz"),
    # No leading "KEY=" / "TOKEN=" assignment on purpose: that shape is
    # already caught by env_secret earlier in rule order, which would mask
    # whether mailgun_key/resend_key themselves actually fire.
    ("mailgun_key", "rotating the mailgun key-3ax6xnjp29jd6fds4gc373sgvjxteol now"),
    ("resend_key", "rotating the resend re_123456789012345678901234567890 now"),
    # Built via concatenation, not a literal — GitHub push protection flags
    # a bare "SK" + 32 hex chars string as a real Twilio key on sight.
    ("twilio_key", "printed the twilio " + "SK" + "1234567890abcdef" * 2 + " now"),
    ("conn_str", "postgresql://app:s3cr3tpassw0rd@db.local/app"),
    (
        "jwt",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.AbCdEf0123456789ghij",
    ),
    ("phone", "call +7 999 123-45-67 now"),
    ("card", "card 4111 1111 1111 1111 on file"),
    # Cut in half by an upstream truncation. Assembled, never written out.
    (
        "telegram_bot",
        "https://api.telegram.org/" + "bot" + "1234567890:" + "AA" + "Bc3dEfGhIjKlMnOp",
    ),
    ("google_api_key", "key=" + "AIza" + "SyD9xQv7Lm"),
    ("digitalocean", "token " + "do" + "p_v1_" + "d0" * 10),
    ("telegram_api_hash", "api_hash = " + "a1b2c3d4e5f6a7b8"),
    ("gcp_key_id", '"private_key_id": "' + "a1b2c3d4e5f6a7b8"),
]

# Ordinary output that must come back byte-identical under the default rules.
_MUST_KEEP = [
    "_DOCKER_AUTH = re.compile(r'x')",
    "config = {'key': 'value', 'token': 'placeholder'}",
    "auth: enabled\ntoken: ${GITHUB_TOKEN}",
    "PASSWORD=$DB_PASSWORD",
    "PASSWORD = os.environ.get('X')",
    "parser.add_argument('--token', help='api token')",
    "commit 9fceb02d0ae598e95dc970b74767f19372d61af8",
    "sha256:e2fc4e5012d16e7fe466f5291c476431beaa1f9b90a5c2125b493ed28e2aba57",
    "id: 550e8400-e29b-41d4-a716-446655440000",
    "2026-09-05T13:07:41.123456Z",
    "ts 1757000000000 ms",
    "v1.24.3+build.20260905",
    "0.0.0.0:8080->80/tcp, :::5432->5432/tcp",
    "inet 192.168.1.42/24 brd 192.168.1.255",
    "aGVsbG8gd29ybGQgdGhpcyBpcyBiYXNlNjQgcGFkZGluZ3M=",
    "checks/npm_check.py",
    "systemd-ask-password --echo",
    "except: pass\nprint(count)",
    "User: John Smith <john@company.internal>",
    "kernel 7.1.11-zen1-1-zen",
    "h1:AbCdEf0123456789ghijklmnopqrstuvwxyzABCDEFG=",
    "pytest -k 'test_token_parsing'",
    "curl --user-agent claude/1 https://example.com",
    "License: MIT",
    "PUBLIC_KEY=ssh-ed25519",
    "htpasswd -c /etc/nginx/.htpasswd admin",
    'openssl passwd -6 "$PASS"',
    # Regression: "key-"/"re_" appearing mid-identifier or as an
    # ordinary, non-secret-shaped token must not be flagged.
    "monkey-patching-library",
    "future_annotations_enabled",
    "key-rotation-v2",
    # Regression: "SK" is a common substring of ordinary words, not just the
    # Twilio prefix — must not be flagged without the exact hex-shaped value.
    "TASK: review the pull request",
    "the DESK lamp needs a new bulb",
    "wear a MASK when sanding",
]

# Rules that are off by default: one sample each, checked with the rule on.
_OPTIN_CUT = [
    ("email", "reach bob@example.org for access"),
    ("ssn", "SSN: 123-45-6789"),
    ("iban", "IBAN: DE89370400440532013000"),
    ("home_path", "reading /home/jsmith/.config/app.toml"),
    ("mac_addr", "link/ether a4:83:e7:1b:2c:3d brd ff:ff:ff:ff:ff:ff"),
    ("public_ip", "connected from 203.0.113.47:44321"),
    ("public_ip6", "inet6 2a01:4f8:1c1c:abcd::1/64 scope global"),
    ("phone_loose", "call 415-555-0142 for support"),
    ("entropy", "OPAQUE=Xk7pQ2mZr9TvB4nLs6WyD3fH8jCe1AuG"),
]

# The noisy rules get a keep list of their own, checked with the rule on.
_RULE_KEEP = {
    "entropy": [
        "sha256:e2fc4e5012d16e7fe466f5291c476431beaa1f9b90a5c2125b493ed28e2aba57",
        "h1:AbCdEf0123456789ghijklmnopqrstuvwxyzABCDEFG=",
        "id: 550e8400-e29b-41d4-a716-446655440000",
        "commit 9fceb02d0ae598e95dc970b74767f19372d61af8",
    ],
    "public_ip6": [
        "inet6 ::1/128 scope host",
        "inet6 fe80::1e69:7aff:fe3c:1/64 scope link",
        "inet6 fd00:1234::5/64 scope global",
        "docs use 2001:db8::1 as the example address",
        "started 12:34:56, link/ether 00:11:22:33:44:55",
    ],
}


def self_check() -> int:
    bad = []
    for name, sample in _MUST_CUT:
        out = redact_regex(sample)
        if f"[REDACTED:{name}]" not in out:
            bad.append(f"rule {name} did not fire on its own sample")
    covered = {name for name, _ in _MUST_CUT}
    for rule in _DEFAULT_RULES:
        if rule.name not in covered:
            bad.append(f"rule {rule.name} has no _MUST_CUT sample")
    for sample in _MUST_KEEP:
        out = redact_regex(sample)
        if out != sample:
            bad.append(f"mangled: {sample!r} -> {out!r}")
    for name, sample in _OPTIN_CUT:
        rules = tuple(r for r in _RULES if r.name == name)
        if f"[REDACTED:{name}]" not in redact_regex(sample, rules):
            bad.append(f"opt-in rule {name} did not fire on its own sample")
    for name, samples in _RULE_KEEP.items():
        rules = tuple(r for r in _RULES if r.name == name)
        for sample in samples:
            out = redact_regex(sample, rules)
            if out != sample:
                bad.append(f"{name} mangled: {sample!r} -> {out!r}")

    for line in bad:
        print(line)
    print(
        f"{len(_MUST_CUT)} secrets, {len(_MUST_KEEP)} clean samples, "
        f"{len(_OPTIN_CUT)} opt-in, {len(bad)} failures"
    )
    return 1 if bad else 0


def list_rules() -> int:
    active = {rule.name for rule in active_rules(load_config())}
    for rule in _RULES:
        print(f"{'on ' if rule.name in active else 'off'}  {rule.name}")
    return 0


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return
    if not isinstance(data, dict):
        return

    # Registered for both PostToolUse and PostToolUseFailure (a failed Bash
    # command's stdout/stderr carries secrets just as often as a successful
    # one's) — echo back whichever event actually triggered us rather than
    # hardcoding PostToolUse, since the response is discriminated by this field.
    event_name = data.get("hook_event_name", "PostToolUse")
    resp = data.get("tool_response", "")
    if data.get("tool_name") in _SKIP_TOOLS:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": event_name,
                        "updatedToolOutput": resp,
                    }
                }
            )
        )
        return
    config = load_config()
    updated = build_updated_response(data, active_rules(config), allow_patterns(config))
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "updatedToolOutput": updated,
                }
            }
        )
    )


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        sys.exit(self_check())
    if "--list-rules" in sys.argv:
        sys.exit(list_rules())
    main()
