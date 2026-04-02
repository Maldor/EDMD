#!/usr/bin/env python3
"""
scripts/generate_flatpak_release.py

Generates a Flathub-ready Flatpak manifest from the development manifest.

Two transformations are applied:
  1. The python3-edmd-deps module's live pip install is replaced with an
     offline module containing pre-resolved wheel URLs and SHA256 hashes for
     all packages and their transitive dependencies.  Flathub's build
     environment has no network access during the build phase; all sources
     must be declared explicitly in the manifest.

  2. The edmd source is pinned from 'branch: main' to a specific tag and
     commit SHA, making the build fully reproducible.

Wheel resolution uses 'pip download --only-binary :all: --report' (pip 22.2+).
This produces a JSON report containing the canonical PyPI URL and SHA256 for
every wheel selected, including transitive dependencies.  No third-party tools
are required beyond pip and pyyaml.

--only-binary :all: is non-negotiable: cryptography uses maturin (Rust) and
psutil uses C extensions — neither can build from source in the GNOME SDK.

Usage:
    python3 scripts/generate_flatpak_release.py \\
        --tag 20260402 \\
        --commit abc123def456... \\
        --output flathub-release/io.github.drworman.EDMD.yml

Requirements:
    pip install pyyaml
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# ── Constants ─────────────────────────────────────────────────────────────────

BASE_MANIFEST = Path(__file__).parent.parent / "flatpak" / "io.github.drworman.EDMD.yml"

# Direct pip dependencies — transitive deps are resolved automatically.
PIP_PACKAGES = [
    "discord-webhook>=1.3.0",
    "cryptography>=41.0.0",
    "psutil>=5.9.0",
]

# Target platform for wheel selection.
# org.gnome.Platform//49 runs on Python 3.13, x86_64 Linux.
# manylinux_2_28 is the minimum glibc version for the Flatpak SDK base.
PIP_PLATFORM       = "manylinux_2_28_x86_64"
PIP_PYTHON_VERSION = "313"   # Python 3.13
PIP_IMPLEMENTATION = "cp"


# ── Wheel download ────────────────────────────────────────────────────────────

def _wheel_to_source(whl_path: Path) -> dict:
    """
    Build a Flatpak source entry for a downloaded wheel file.

    Computes the SHA256 from the file on disk, then queries the PyPI JSON API
    to get the canonical HTTPS URL.  The API lookup also cross-checks that our
    hash matches PyPI's reported hash, detecting any corruption.
    """
    import hashlib
    import urllib.request
    import urllib.error

    filename = whl_path.name
    sha256   = hashlib.sha256(whl_path.read_bytes()).hexdigest()

    # Wheel filenames: {name}-{version}-{python}-{abi}-{platform}.whl
    # Underscores in the name part map to hyphens in the PyPI package name.
    parts    = filename[:-4].split("-")       # strip .whl, split on '-'
    pkg_name = parts[0].lower().replace("_", "-")
    version  = parts[1]

    api_url = f"https://pypi.org/pypi/{pkg_name}/{version}/json"
    try:
        with urllib.request.urlopen(api_url, timeout=30) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        print(
            f"  ERROR: PyPI API returned {e.code} for {pkg_name} {version}.\n"
            f"  URL tried: {api_url}",
            file=sys.stderr,
        )
        sys.exit(1)

    for release_file in data.get("urls", []):
        if release_file["filename"] == filename:
            pypi_sha256 = release_file["digests"]["sha256"]
            if pypi_sha256 != sha256:
                print(
                    f"  ERROR: SHA256 mismatch for {filename}!\n"
                    f"  Local : {sha256}\n"
                    f"  PyPI  : {pypi_sha256}",
                    file=sys.stderr,
                )
                sys.exit(1)
            return {
                "type":          "file",
                "url":           release_file["url"],
                "sha256":        pypi_sha256,
                "dest-filename": filename,
            }

    print(
        f"  ERROR: {filename} not found in PyPI API response for {pkg_name} {version}.\n"
        f"  This usually means the wheel was renamed or is not a standard release.\n"
        f"  API URL: {api_url}",
        file=sys.stderr,
    )
    sys.exit(1)


def download_wheels(packages: list[str]) -> list[dict]:
    """
    Download binary wheels for the target platform and return Flatpak source
    entries: [{type, url, sha256, dest-filename}, ...] for every wheel,
    including all transitive dependencies.

    Uses plain 'pip download --only-binary :all:' (universally supported),
    then resolves canonical PyPI URLs and verifies SHA256 hashes via the
    PyPI JSON API.  No pip internals, no --report flag, no third-party tools.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        dest_dir = Path(tmpdir) / "wheels"
        dest_dir.mkdir()

        cmd = [
            sys.executable, "-m", "pip", "download",
            "--only-binary", ":all:",
            "--dest",           str(dest_dir),
            "--platform",       PIP_PLATFORM,
            "--python-version", PIP_PYTHON_VERSION,
            "--implementation", PIP_IMPLEMENTATION,
            "--quiet",
        ] + packages

        print(f"  Running pip download:")
        print(f"    {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(
                f"pip download failed (exit {result.returncode}):\n"
                f"{result.stderr.strip()}",
                file=sys.stderr,
            )
            sys.exit(1)

        wheels = sorted(dest_dir.glob("*.whl"))
        if not wheels:
            print("ERROR: pip download produced no .whl files.", file=sys.stderr)
            sys.exit(1)

        print(f"  Downloaded {len(wheels)} wheels — resolving PyPI URLs...")
        sources = []
        for whl in wheels:
            print(f"    {whl.name}")
            sources.append(_wheel_to_source(whl))

    return sources


def generate_pip_module(packages: list[str]) -> dict:
    """
    Build the complete Flatpak module dict for pip-managed dependencies.

    The build command uses --no-index --find-links to install from the
    pre-downloaded wheel files in 'sources', never touching the network.
    """
    sources = download_wheels(packages)

    # Strip version specifiers for the install command — the wheels are
    # already version-pinned by the sources list.
    names = [p.split(">=")[0].split("==")[0].split("!=")[0].strip() for p in packages]
    quoted = " ".join(f'"{n}"' for n in names)

    install_cmd = (
        "pip3 install --verbose --no-build-isolation --no-index "
        "--only-binary :all: "
        '--find-links="file://${PWD}" '
        "--prefix=${FLATPAK_DEST} "
        + quoted
    )

    return {
        "name":           "python3-edmd-deps",
        "buildsystem":    "simple",
        "build-commands": [install_cmd],
        "sources":        sources,
    }


# ── Manifest transformation ───────────────────────────────────────────────────

def patch_manifest(manifest: dict, tag: str, commit: str, pip_module: dict) -> dict:
    """Replace the pip module and pin the EDMD source. Returns a new dict."""
    import copy
    m = copy.deepcopy(manifest)
    new_modules = []

    for module in m.get("modules", []):
        if not isinstance(module, dict):
            new_modules.append(module)
            continue

        name = module.get("name", "")

        if name.startswith("python3-edmd-deps") or name.startswith("python3-discord"):
            new_modules.append(pip_module)
            continue

        if name == "edmd":
            mod = dict(module)
            new_sources = []
            for source in module.get("sources", []):
                if source.get("type") == "git" and "drworman/EDMD" in source.get("url", ""):
                    pinned = {k: v for k, v in source.items() if k != "branch"}
                    pinned["tag"]    = tag
                    pinned["commit"] = commit
                    new_sources.append(pinned)
                else:
                    new_sources.append(source)
            mod["sources"] = new_sources
            new_modules.append(mod)
            continue

        new_modules.append(module)

    m["modules"] = new_modules
    return m


# ── YAML output ───────────────────────────────────────────────────────────────

def _yaml_dump(data: dict) -> str:
    return yaml.dump(
        data,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=100,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a Flathub-ready Flatpak manifest for an EDMD release."
    )
    parser.add_argument("--tag",    required=True, help="Release tag, e.g. 20260402")
    parser.add_argument("--commit", required=True, help="Full git commit SHA for the tag")
    parser.add_argument(
        "--output",
        default="flathub-release/io.github.drworman.EDMD.yml",
        help="Output path (default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip wheel download; produces a manifest with empty sources (structure test only)",
    )
    args = parser.parse_args()

    print(f"Generating Flathub manifest for EDMD {args.tag} @ {args.commit[:12]}...")

    if not BASE_MANIFEST.exists():
        print(f"ERROR: Base manifest not found at {BASE_MANIFEST}", file=sys.stderr)
        sys.exit(1)
    manifest = yaml.safe_load(BASE_MANIFEST.read_text(encoding="utf-8"))

    if args.dry_run:
        print("  --dry-run: skipping wheel download")
        pip_module = {
            "name":           "python3-edmd-deps",
            "buildsystem":    "simple",
            "build-commands": ["echo 'DRY RUN — sources not populated'"],
            "sources":        [],
        }
    else:
        print(
            f"  Packages  : {', '.join(PIP_PACKAGES)}\n"
            f"  Platform  : {PIP_PLATFORM}\n"
            f"  Python    : {PIP_PYTHON_VERSION}\n"
            f"  (resolves all transitive dependencies)"
        )
        pip_module = generate_pip_module(PIP_PACKAGES)
        print(f"  Wheels    : {len(pip_module['sources'])} sources resolved")

    release_manifest = patch_manifest(manifest, args.tag, args.commit, pip_module)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_yaml_dump(release_manifest), encoding="utf-8")

    total_src = sum(
        len(m.get("sources", []))
        for m in release_manifest.get("modules", [])
        if isinstance(m, dict)
    )
    print(
        f"  Written   : {output}\n"
        f"  App ID    : {release_manifest.get('app-id')}\n"
        f"  Tag       : {args.tag}\n"
        f"  Commit    : {args.commit}\n"
        f"  Sources   : {total_src} total manifest entries\n"
        "Done."
    )


if __name__ == "__main__":
    main()
