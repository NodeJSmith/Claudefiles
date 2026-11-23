#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["cyclopts>=4.16"]
# ///
"""Replace this package's src/ and tests/ with ado-api from an analytics checkout.

Every Claudefiles-side change to the upstream code is a named substitution below, and
UPSTREAM.md explains each one under the same name. A substitution that no longer
matches stops the run before src/ or tests/ are touched: upstream moved the code it
patches, so update the substitution and its UPSTREAM.md entry. The script also
rewrites UPSTREAM.md's "Upstream base" line.
"""

import io
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

PACKAGE_DIR = Path(__file__).resolve().parent
UPSTREAM_DOC = PACKAGE_DIR / "UPSTREAM.md"
UPSTREAM_PACKAGE = "packages/ado-api"
UPSTREAM_TAGS = "packages/rhyme-constants/src/rhyme_constants/ado_tags.py"
UPSTREAM_TAGS_TEST = "packages/rhyme-constants/tests/test_ado_tags.py"
# Only these are copied. Upstream's pyproject.toml, uv.lock, CI and requirements files
# stay behind: Claudefiles owns its own versions.
VENDORED_DIRS = ("src", "tests")
MONOREPO_DEPENDENCIES = {"rhyme-constants"}
BASE_LINE_RE = re.compile(r"^\*\*Upstream base:\*\*.*$", re.MULTILINE)

TAGS_DOCSTRING = '''"""ADO build tag format — one specific organization's build-tag conventions.

These constants encode Rhyme's build-tag format (`key=value` pairs, with a handful
of legacy hyphenated formats still recognized for older builds). `builds
missed-prod`, `builds retry-stage`, `builds cancel-superseded`, and `builds
approve` all depend on these conventions to find the builds they operate on.

At an organization whose pipelines tag builds differently, those commands will
find nothing — they are not broken, they simply have no matching tags to match
against.
"""'''

UPSTREAM_SETUP_HINT = "f\"    Run: az devops configure --defaults organization={ADO_ORG_URL} project='{ADO_PROJECT}'\""
GENERIC_SETUP_HINT = '"    Run: az devops configure --defaults organization=https://dev.azure.com/ORG project=PROJECT"'


@dataclass(frozen=True)
class Substitution:
    """Replace ``old`` with ``new`` in every file under the package matching ``glob``.

    ``name`` matches the heading of its entry in UPSTREAM.md. At least one occurrence
    must exist, or the revendor stops.
    """

    name: str
    glob: str
    old: str
    new: str


SUBSTITUTIONS = (
    Substitution("Vendored build-tag helpers", "**/*.py", "rhyme_constants.ado_tags", "ado_api.tags"),
    Substitution(
        "Vendored build-tag helpers", "src/ado_api/tags.py", "tag_pipeline_run.py writes", "a Rhyme pipeline run writes"
    ),
    Substitution(
        "Generic setup hint",
        "src/ado_api/commands/setup.py",
        "from rhyme_constants.ado import ADO_ORG_URL, ADO_PROJECT\n\n",
        "",
    ),
    Substitution("Generic setup hint", "src/ado_api/commands/setup.py", UPSTREAM_SETUP_HINT, GENERIC_SETUP_HINT),
    Substitution(
        "Review questions point at the README",
        "src/ado_api/REVIEW.md",
        "is in `.claude/reference/cli-tools/ado-api.md`\n(conventions section).",
        "is in the package README\n(Conventions section).",
    ),
    Substitution(
        "Pending upstream: mock the default branch in one test",
        "tests/test_entrypoint_pin.py",
        '        _dispatch(["builds", "missed-prod"])\n',
        '        with patch("ado_api.commands.missed_prod.get_default_branch", return_value="master"):\n'
        '            _dispatch(["builds", "missed-prod"])\n',
    ),
)


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout


def extract(repo: Path, ref: str, path: str, dest: Path) -> None:
    with tarfile.open(fileobj=io.BytesIO(git(repo, "archive", "--format=tar", ref, path))) as tar:
        tar.extractall(dest, filter="data")


def replace_docstring(text: str, docstring: str) -> str:
    """Swap the module docstring (the file's leading triple-quoted string) for ``docstring``."""
    if not text.startswith('"""'):
        sys.exit("Error: upstream ado_tags.py no longer starts with a module docstring; update revendor.py.")
    end = text.index('"""', 3) + 3
    return docstring + text[end:]


def apply_substitutions(root: Path) -> None:
    for sub in SUBSTITUTIONS:
        hits = 0
        for path in sorted(root.glob(sub.glob)):
            text = path.read_text()
            if sub.old in text:
                hits += text.count(sub.old)
                path.write_text(text.replace(sub.old, sub.new))
        if hits == 0:
            sys.exit(f"Error: substitution {sub.name!r} no longer matches in {sub.glob}. Update revendor.py.")
        print(f"  {sub.name} ({sub.glob}): {hits}", file=sys.stderr)
    leftovers = [str(p.relative_to(root)) for p in root.rglob("*.py") if "rhyme_constants" in p.read_text()]
    if leftovers:
        sys.exit(f"Error: rhyme_constants still referenced in {', '.join(leftovers)}. Add a substitution.")


def dependency_names(pyproject: str) -> dict[str, str]:
    """Map each runtime dependency's name to its full requirement string."""
    deps = tomllib.loads(pyproject)["project"]["dependencies"]
    names = (re.split(r"[\s<>=!~\[;@]", dep, maxsplit=1)[0] for dep in deps)
    return {re.sub(r"[-_.]+", "-", name).lower(): dep for name, dep in zip(names, deps, strict=True)}


def report_dependency_drift(upstream_pyproject: str) -> None:
    upstream = dependency_names(upstream_pyproject)
    ours = dependency_names((PACKAGE_DIR / "pyproject.toml").read_text())
    drift = [
        f"  upstream: {req}    here: {ours.get(name, '(missing)')}"
        for name, req in sorted(upstream.items())
        if name not in MONOREPO_DEPENDENCIES and ours.get(name) != req
    ]
    drift += [f"  here only: {req}" for name, req in sorted(ours.items()) if name not in upstream]
    if drift:
        print("\nRuntime dependencies differ from upstream; update pyproject.toml:", file=sys.stderr)
        print("\n".join(drift), file=sys.stderr)


def swap_in(staged: Path, name: str) -> None:
    """Replace PACKAGE_DIR/name with the staged copy, keeping the old one until the new one is in place."""
    target = PACKAGE_DIR / name
    incoming = PACKAGE_DIR / f".{name}.revendor-new"
    outgoing = PACKAGE_DIR / f".{name}.revendor-old"
    # Leftovers from an interrupted run hold nothing needed: the dirty check passed,
    # so the old src/ and tests/ are recoverable from git.
    for stale in (incoming, outgoing):
        shutil.rmtree(stale, ignore_errors=True)
    shutil.copytree(staged, incoming)
    if target.exists():
        target.rename(outgoing)
    incoming.rename(target)
    shutil.rmtree(outgoing)


app = App(help=__doc__)


@app.default
def revendor(
    analytics: Annotated[Path, Parameter(help="Path to an analytics monorepo clone. Fetch it first.")],
    *,
    ref: Annotated[str, Parameter(help="Commit or branch to vendor from.")] = "origin/master",
    force: Annotated[bool, Parameter(help="Overwrite uncommitted changes under src/ and tests/.")] = False,
) -> None:
    """Replace src/ and tests/ with the upstream package at REF, with the Claudefiles changes applied."""
    dirty = git(PACKAGE_DIR, "status", "--porcelain", "--", *VENDORED_DIRS).decode().strip()
    if dirty and not force:
        sys.exit(
            f"Error: uncommitted changes under src/ or tests/ would be lost:\n{dirty}\nCommit them or pass --force."
        )

    doc = UPSTREAM_DOC.read_text()
    if not BASE_LINE_RE.search(doc):
        sys.exit(f"Error: no '**Upstream base:**' line in {UPSTREAM_DOC.name} to record the new base in.")
    base = git(analytics, "log", "-1", "--date=short", "--format=`%h` (%ad, %s)", ref).decode().strip()

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp)
        extract(analytics, ref, UPSTREAM_PACKAGE, staging)
        root = staging / UPSTREAM_PACKAGE
        tags = git(analytics, "show", f"{ref}:{UPSTREAM_TAGS}").decode()
        (root / "src/ado_api/tags.py").write_text(replace_docstring(tags, TAGS_DOCSTRING))
        (root / "tests/test_tags.py").write_bytes(git(analytics, "show", f"{ref}:{UPSTREAM_TAGS_TEST}"))

        print(f"Applying {len(SUBSTITUTIONS)} substitutions:", file=sys.stderr)
        apply_substitutions(root)

        for name in VENDORED_DIRS:
            swap_in(root / name, name)
        upstream_pyproject = (root / "pyproject.toml").read_text()

    UPSTREAM_DOC.write_text(BASE_LINE_RE.sub(lambda _: f"**Upstream base:** {base}", doc, count=1))
    print(f"Vendored {base}.", file=sys.stderr)
    report_dependency_drift(upstream_pyproject)
    print("\nNext: the checklist under 'Revendoring' in UPSTREAM.md.", file=sys.stderr)


if __name__ == "__main__":
    app()
