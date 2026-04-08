#!/usr/bin/env python3
"""Generate manifest.yaml scaffold files for wrapper MCP servers.

Wrapper servers have no server.py, so the manifest is their only source
of truth for tool declarations.  Full servers are skipped — their tools
are discovered at runtime via list_tools().

Usage:
    python scripts/generate_manifests.py          # generate missing only
    python scripts/generate_manifests.py --all     # regenerate all
    python scripts/generate_manifests.py --list    # list wrapper servers
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent

_SKIP_DIRS = {".git", ".github", "scripts", "tests", "examples", "docs", "node_modules", "__pycache__"}


def discover_wrapper_servers() -> list[tuple[str, str, Path]]:
    """Find all wrapper servers (Dockerfile but no server.py)."""
    servers = []
    for category_dir in sorted(ROOT_DIR.iterdir()):
        if not category_dir.is_dir() or category_dir.name in _SKIP_DIRS or category_dir.name.startswith("."):
            continue
        for server_dir in sorted(category_dir.iterdir()):
            if not server_dir.is_dir():
                continue
            if (server_dir / "Dockerfile").exists() and not (server_dir / "server.py").exists():
                servers.append((category_dir.name, server_dir.name, server_dir))
    return servers


def generate_scaffold(category: str, name: str) -> dict:
    """Build a minimal manifest scaffold for a wrapper server."""
    return {
        "name": name,
        "category": category,
        "type": "wrapper",
        "tools": [],
    }


def main():
    parser = argparse.ArgumentParser(description="Generate manifest.yaml for wrapper MCP servers")
    parser.add_argument("--all", action="store_true", help="Regenerate all manifests")
    parser.add_argument("--list", action="store_true", help="List wrapper servers and exit")
    args = parser.parse_args()

    servers = discover_wrapper_servers()

    if args.list:
        for category, name, _ in servers:
            has_manifest = (_.parent / name / "manifest.yaml").exists() if False else (_ / "manifest.yaml").exists()
            status = "✓" if has_manifest else "✗"
            print(f"  {status} {category}/{name}")
        print(f"\n{len(servers)} wrapper servers total")
        return

    generated = 0
    skipped = 0

    for category, name, server_dir in servers:
        manifest_path = server_dir / "manifest.yaml"

        if manifest_path.exists() and not args.all:
            skipped += 1
            continue

        manifest = generate_scaffold(category, name)

        with open(manifest_path, "w") as f:
            yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)

        print(f"  OK {category}/{name} (scaffold — fill in tools manually)")
        generated += 1

    print(f"\nDone: {generated} generated, {skipped} skipped")


if __name__ == "__main__":
    main()
