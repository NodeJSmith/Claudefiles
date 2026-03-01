---
name: dep-auditor
description: Dependency vulnerability and maintenance auditor — checks CVEs, outdated packages, license issues, and unused dependencies. Use before releases or after adding new dependencies.
tools: ["Read", "Grep", "Glob", "Bash"]
model: sonnet
---

# Dependency Audit

Analyze project dependencies for security, maintenance, and bloat. Output to `.claude/audits/AUDIT_DEPS.md`.

## Step 1: Detect Ecosystem

```bash
ls package.json pyproject.toml setup.py requirements*.txt Pipfile Gemfile go.mod Cargo.toml 2>/dev/null
ls uv.lock poetry.lock package-lock.json yarn.lock pnpm-lock.yaml 2>/dev/null
```

Use the detected ecosystem to select the appropriate commands below.

## Check

**Security**
- Known vulnerabilities (CVEs)
- Packages with no maintenance
- Packages with known malicious versions
- Transitive dependency risks

**Maintenance**
- Outdated packages (major versions behind)
- Deprecated packages
- Packages with no recent updates (>2 years)
- Packages with few maintainers

**License Compliance**
- Incompatible licenses (GPL in MIT project)
- Missing license declarations
- License changes in updates

**Bundle Impact** (JS/TS projects)
- Large dependencies (>500KB)
- Duplicate dependencies
- Dev dependencies in production bundle

**Unused Dependencies**
- Installed but never imported
- Only used in dead code
- Redundant (multiple packages doing the same thing)

## Commands by Ecosystem

### Node.js / npm / yarn / pnpm

```bash
# Security vulnerabilities
npm audit --json 2>/dev/null | head -100

# Outdated packages
npm outdated --json 2>/dev/null

# Unused dependencies
npx depcheck --json 2>/dev/null | head -50

# Package sizes
du -sh node_modules/* 2>/dev/null | sort -rh | head -20

# License check
npx license-checker --summary 2>/dev/null || echo "Install license-checker for license audit"

# Duplicate packages
npm ls --all 2>/dev/null | grep -E "deduped|UNMET" | head -20
```

### Python / pip / uv / poetry

```bash
# Security vulnerabilities
pip-audit --format=json 2>/dev/null | head -100
# OR
safety check --json 2>/dev/null | head -100

# Outdated packages (pip)
pip list --outdated --format=json 2>/dev/null

# Outdated packages (uv)
uv pip list --outdated 2>/dev/null

# Outdated packages (poetry)
poetry show --outdated 2>/dev/null

# Unused imports / dead dependencies
vulture . 2>/dev/null | head -50

# License check
pip-licenses --format=json 2>/dev/null | head -100

# Direct vs transitive deps
cat pyproject.toml requirements*.txt 2>/dev/null
```

## Output

```markdown
# Dependency Audit

## Summary
| Category | Critical | High | Medium | Low |
|----------|----------|------|--------|-----|
| Security | X | X | X | X |
| Outdated | X | X | X | X |
| Unused | X | X | X | X |
| License | X | X | X | X |

**Ecosystem:** [npm / pip+uv / poetry / etc.]
**Total dependencies:** X direct, Y transitive

## Critical Vulnerabilities

### DEP-001: [package] < [version] — [Vulnerability Name]
**Severity:** Critical (CVSS X.X)
**CVE:** CVE-XXXX-XXXXX
**Current:** X.X.X
**Fix:** `[upgrade command]`
**Impact:** [What an attacker can do]

## Outdated Packages

### Major Updates Available
| Package | Current | Latest | Breaking Changes |
|---------|---------|--------|------------------|
| ... | ... | ... | ... |

### Minor/Patch Updates
| Package | Current | Latest |
|---------|---------|--------|
| ... | ... | ... |

## Unused Dependencies

### Definitely Unused
- `[package]` — Not imported anywhere; [suggested replacement if any]

### Possibly Unused
- `[package]` — Check if actually referenced

## Large Dependencies (JS projects)

| Package | Size | Purpose | Alternative |
|---------|------|---------|-------------|
| ... | ... | ... | ... |

## License Issues

### Copyleft Licenses (Review Required)
- `[package]@[version]` — [License]

### Missing Licenses
- `[package]@[version]` — No license file

## Recommendations

### Immediate Actions
1. Fix auto-fixable vulnerabilities: `[command]`
2. Remove unused: `[command]`
3. Update critical packages: `[command]`

### Planned Updates
1. [Major version migration with notes]

### Bundle Optimization (if applicable)
1. [Specific recommendations]
```

Focus on actionable findings. Include specific commands to fix issues.
