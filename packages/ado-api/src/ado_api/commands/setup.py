"""Setup command — check and install az CLI + azure-devops extension + defaults."""

import json
import shutil
import subprocess
import sys


def _run(cmd: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def _has_az() -> bool:
    return shutil.which("az") is not None


def _has_devops_extension() -> bool:
    if not _has_az():
        return False
    result = _run(["az", "extension", "show", "--name", "azure-devops"])
    return result.returncode == 0


def _has_defaults() -> bool:
    if not _has_az():
        return False
    result = _run(["az", "devops", "configure", "--list"])
    output = result.stdout
    has_org = False
    has_project = False
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("organization") and "dev.azure.com" in stripped:
            has_org = True
        elif stripped.startswith("project"):
            value = stripped.split(None, 1)[-1].strip("= ")
            if value and value != "(not set)":
                has_project = True
    return has_org and has_project


def cmd_setup() -> None:
    """Check az CLI prerequisites and guide through setup."""
    all_ok = True

    # Step 1: az CLI
    if _has_az():
        result = _run(["az", "version"])
        version = "unknown"
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                version = data.get("azure-cli", "unknown")
            except (json.JSONDecodeError, AttributeError):
                pass
        print(f"  [ok] az CLI installed (version {version})")
    else:
        all_ok = False
        print("  [missing] az CLI not found")
        print()
        print(
            "  Install: https://learn.microsoft.com/en-us/cli/azure/install-azure-cli"
        )
        print()

    # Step 2: azure-devops extension
    if _has_az():
        if _has_devops_extension():
            print("  [ok] azure-devops extension installed")
        else:
            all_ok = False
            print("  [missing] azure-devops extension")
            print("    Run: az extension add --name azure-devops")
            print()

    # Step 3: defaults
    if _has_az() and _has_devops_extension():
        if _has_defaults():
            print("  [ok] az devops defaults configured")
        else:
            all_ok = False
            print("  [missing] az devops defaults not configured")
            print(
                "    Run: az devops configure --defaults organization=<org-url> project='<project-name>'"
            )
            print()

    # Step 4: login check
    if _has_az():
        result = _run(["az", "account", "show"])
        if result.returncode == 0:
            print("  [ok] az login active")
        else:
            all_ok = False
            print("  [missing] not logged in to Azure")
            print("    Run: az login")
            print()

    if all_ok:
        print()
        print("All prerequisites met. ado-api is ready to use.")
    else:
        print()
        print("Fix the items above, then run 'ado-api setup' again to verify.")
        sys.exit(1)
