#!/usr/bin/env python3
"""
scripts/generate_flatpak_release.py

Generates a Flathub-ready Flatpak manifest from the development manifest.

Two transformations are applied:
  1. The python3-edmd-deps module's live pip install is replaced with the
     output of flatpak-pip-generator, which contains pre-resolved wheel URLs
     and SHA256 hashes for all packages and their transitive dependencies.
     Flathub's build environment has no network access during the build phase;
     all sources must be declared explicitly in the manifest.

  2. The edmd source is pinned from 'branch: main' to a specific tag and
     commit SHA, making the build fully reproducible.

Usage (called by CI workflows):
    python3 scripts/generate_flatpak_release.py \\
        --tag 20260402 \\
        --commit abc123def456... \\
        --output flathub-release/io.github.drworman.EDMD.yml

Requirements:
    pip install pyyaml flatpak-pip-generator
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

BASE_MANIFEST  = Path(__file__).parent.parent / "flatpak" / "io.github.drworman.EDMD.yml"
APP_ID         = "io.github.drworman.EDMD"
GITHUB_URL     = "https://github.com/drworman/EDMD.git"

# Packages to install via pip.  These must exactly match what edmd requires.
PIP_PACKAGES = [
    "discord-webhook>=1.3.0",
    "cryptography>=41.0.0",
    "psutil>=5.9.0",
]


# ── flatpak-pip-generator wrapper ─────────────────────────────────────────────

def _find_fpg() -> list[str]:
    """
    Locate the flatpak-pip-generator command.

    The tool may be installed as a console script (flatpak-pip-generator)
    or run via python3 -m flatpak_pip_generator depending on how it was
    installed.  Returns the command list to use with subprocess.
    """
    import shutil
    if shutil.which("flatpak-pip-generator"):
        return ["flatpak-pip-generator"]
    # Try running as a module
    result = subprocess.run(
        [sys.executable, "-m", "flatpak_pip_generator", "--help"],
        capture_output=True,
    )
    if result.returncode == 0:
        return [sys.executable, "-m", "flatpak_pip_generator"]
    print(
        "ERROR: flatpak-pip-generator not found.\n"
        "Install with:  pip install flatpak-pip-generator\n"
        "Or from source: pip install "
        "git+https://github.com/flatpak/flatpak-builder-tools.git"
        "#subdirectory=pip",
        file=sys.stderr,
    )
    sys.exit(1)


def generate_pip_module(packages: list[str]) -> dict:
    """
    Run flatpak-pip-generator for the given packages and return the resulting
    module dict.

    flatpak-pip-generator resolves all transitive dependencies and produces a
    single Flatpak module definition containing:
      - build-commands: pip3 install calls for each top-level package
      - sources:        list of {type, url, sha256, dest-filename} for every
                        wheel or sdist that needs to be downloaded

    The sources are downloaded during flatpak-builder's fetch phase (which has
    network access) and installed from local files during the build phase
    (which does not).
    """
    fpg = _find_fpg()

    with tempfile.TemporaryDirectory() as tmpdir:
        out_stem = Path(tmpdir) / "pip-module"
        # --only-binary :all: forces wheel downloads; avoids maturin/Rust
        # requirement from cryptography sdist and C compilation for psutil.
        cmd = fpg + ["--only-binary", ":all:"] + packages + ["--output", str(out_stem)]
        print(f"  Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"flatpak-pip-generator failed:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)

        out_file = out_stem.with_suffix(".json")
        if not out_file.exists():
            print(
                f"ERROR: flatpak-pip-generator did not produce {out_file}",
                file=sys.stderr,
            )
            sys.exit(1)

        module = json.loads(out_file.read_text())

    # Standardise the module name regardless of how the tool names it
    module["name"] = "python3-edmd-deps"
    return module


# ── Manifest transformation ───────────────────────────────────────────────────

def patch_manifest(manifest: dict, tag: str, commit: str, pip_module: dict) -> dict:
    """
    Apply the two Flathub-required transformations to the manifest dict.

    Returns a new dict (does not mutate the input).
    """
    import copy
    m = copy.deepcopy(manifest)
    new_modules = []

    for module in m.get("modules", []):
        if not isinstance(module, dict):
            new_modules.append(module)
            continue

        name = module.get("name", "")

        # 1. Replace the pip module with the offline version
        if name.startswith("python3-edmd-deps") or name.startswith("python3-discord-webhook"):
            new_modules.append(pip_module)
            continue

        # 2. Pin the EDMD source to the release tag + commit
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
    """
    Dump a manifest dict to YAML with Flatpak-friendly formatting.

    PyYAML's default dumper converts multi-line strings to block style and
    preserves key order (Python 3.7+ dicts are ordered).
    """
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
    parser.add_argument("--tag",    required=True, help="Release version tag, e.g. 20260402")
    parser.add_argument("--commit", required=True, help="Full git commit SHA for the tag")
    parser.add_argument(
        "--output",
        default="flathub-release/io.github.drworman.EDMD.yml",
        help="Output path for the generated manifest",
    )
    parser.add_argument(
        "--skip-pip-gen",
        action="store_true",
        help="Skip flatpak-pip-generator (use for dry-runs without network)",
    )
    args = parser.parse_args()

    print(f"Generating Flathub manifest for EDMD {args.tag} @ {args.commit[:12]}...")

    # Load base manifest
    if not BASE_MANIFEST.exists():
        print(f"ERROR: Base manifest not found at {BASE_MANIFEST}", file=sys.stderr)
        sys.exit(1)
    manifest = yaml.safe_load(BASE_MANIFEST.read_text())

    # Generate pip module with offline sources
    if args.skip_pip_gen:
        print("  --skip-pip-gen: using placeholder pip module (not for Flathub submission)")
        pip_module = {
            "name": "python3-edmd-deps",
            "buildsystem": "simple",
            "build-commands": [
                'pip3 install --no-build-isolation --prefix=/app '
                '"discord-webhook>=1.3.0" "cryptography>=41.0.0" "psutil>=5.9.0"'
            ],
            "sources": [],
        }
    else:
        print("  Running flatpak-pip-generator (resolving wheels and dependencies)...")
        pip_module = generate_pip_module(PIP_PACKAGES)
        n_sources = len(pip_module.get("sources", []))
        print(f"  Resolved {n_sources} package sources.")

    # Apply transformations
    release_manifest = patch_manifest(manifest, args.tag, args.commit, pip_module)

    # Write output
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_yaml_dump(release_manifest), encoding="utf-8")

    print(f"  Written: {output}")
    print(f"  App ID : {release_manifest.get('app-id')}")
    print(f"  Tag    : {args.tag}")
    print(f"  Commit : {args.commit}")
    source_count = sum(
        len(m.get("sources", []))
        for m in release_manifest.get("modules", [])
        if isinstance(m, dict)
    )
    print(f"  Total sources in manifest: {source_count}")
    print("Done.")


if __name__ == "__main__":
    main()
