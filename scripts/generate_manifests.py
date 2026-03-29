#!/usr/bin/env python3
"""Generate manifest.yaml files for all full MCP servers.

Imports each server.py, calls list_tools(), and writes a manifest
with the discovered tool names and required parameters.

Usage:
    python scripts/generate_manifests.py          # generate missing only
    python scripts/generate_manifests.py --all     # regenerate all
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import sys
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent

# Categories to scan
_SKIP_DIRS = {".git", ".github", "scripts", "tests", "examples", "docs", "node_modules", "__pycache__"}


def load_server(server_dir: Path):
    """Dynamically import a server.py module."""
    server_path = server_dir / "server.py"
    if not server_path.exists():
        return None

    module_name = f"gen_{server_dir.parent.name}_{server_dir.name}".replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, server_path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)

    mcp_dir = str(server_dir)
    if mcp_dir not in sys.path:
        sys.path.insert(0, mcp_dir)

    try:
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"  SKIP {server_dir.name}: import failed ({e})")
        return None


async def get_tools(module) -> list[dict]:
    """Extract tools from a server module."""
    if hasattr(module, "list_tools"):
        tools = await module.list_tools()
    elif hasattr(module.app, "_tool_handlers"):
        handler = module.app._tool_handlers.get("list_tools")
        if handler:
            tools = await handler()
        else:
            return []
    else:
        return []

    result = []
    for tool in tools:
        entry = {"name": tool.name}
        schema = getattr(tool, "inputSchema", {})
        required = schema.get("required", [])
        if required:
            entry["required_params"] = required
        result.append(entry)
    return result


def generate_manifest(category: str, name: str, server_type: str, tools: list[dict]) -> dict:
    """Build the manifest dict."""
    manifest = {
        "name": name,
        "category": category,
        "type": server_type,
    }
    if tools:
        manifest["tools"] = tools
    return manifest


def discover_full_servers() -> list[tuple[str, str, Path]]:
    """Find all full servers in the repo."""
    servers = []
    for category_dir in sorted(ROOT_DIR.iterdir()):
        if not category_dir.is_dir() or category_dir.name in _SKIP_DIRS or category_dir.name.startswith("."):
            continue
        for server_dir in sorted(category_dir.iterdir()):
            if not server_dir.is_dir():
                continue
            if (server_dir / "Dockerfile").exists():
                stype = "full" if (server_dir / "server.py").exists() else "wrapper"
                servers.append((category_dir.name, server_dir.name, server_dir, stype))
    return servers


async def main():
    parser = argparse.ArgumentParser(description="Generate manifest.yaml for MCP servers")
    parser.add_argument("--all", action="store_true", help="Regenerate all manifests")
    args = parser.parse_args()

    servers = discover_full_servers()
    generated = 0
    skipped = 0

    for category, name, server_dir, stype in servers:
        manifest_path = server_dir / "manifest.yaml"

        if manifest_path.exists() and not args.all:
            skipped += 1
            continue

        tools = []
        if stype == "full":
            module = load_server(server_dir)
            if module:
                try:
                    tools = await get_tools(module)
                except Exception as e:
                    print(f"  WARN {name}: list_tools() failed ({e})")

        manifest = generate_manifest(category, name, stype, tools)

        with open(manifest_path, "w") as f:
            yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)

        print(f"  OK {category}/{name} ({len(tools)} tools)")
        generated += 1

    print(f"\nDone: {generated} generated, {skipped} skipped")


if __name__ == "__main__":
    asyncio.run(main())
