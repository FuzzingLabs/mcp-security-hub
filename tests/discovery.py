"""Auto-discovery of MCP servers in the hub.

Scans the repository for server directories instead of maintaining
hardcoded lists.  A directory is an MCP server if it contains a
Dockerfile.  It is a "full" server if it also has server.py, otherwise
it is a "wrapper".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT_DIR: Path = Path(__file__).resolve().parent.parent

# Directories at the repo root that are NOT server categories.
_SKIP_DIRS: set[str] = {
    ".git",
    ".github",
    "scripts",
    "tests",
    "examples",
    "docs",
    "node_modules",
    "__pycache__",
}


@dataclass
class MCPServer:
    """Represents a single MCP server in the hub."""

    category: str
    name: str
    path: Path
    server_type: str  # "full" or "wrapper"
    manifest: dict[str, Any] = field(default_factory=dict)

    @property
    def has_manifest(self) -> bool:
        return bool(self.manifest)

    @property
    def dockerfile(self) -> Path:
        return self.path / "Dockerfile"

    @property
    def server_py(self) -> Path:
        return self.path / "server.py"

    @property
    def readme(self) -> Path:
        return self.path / "README.md"

    @property
    def requirements(self) -> Path:
        return self.path / "requirements.txt"

    @property
    def manifest_path(self) -> Path:
        return self.path / "manifest.yaml"


def discover_servers(root: Path = ROOT_DIR) -> list[MCPServer]:
    """Discover all MCP servers by scanning the directory tree.

    Looks for ``{category}/{server-name}/Dockerfile`` patterns.

    :param root: Repository root directory.
    :returns: Sorted list of discovered servers.
    """
    servers: list[MCPServer] = []

    for category_dir in sorted(root.iterdir()):
        if not category_dir.is_dir():
            continue
        if category_dir.name in _SKIP_DIRS or category_dir.name.startswith("."):
            continue

        for server_dir in sorted(category_dir.iterdir()):
            if not server_dir.is_dir():
                continue
            if not (server_dir / "Dockerfile").exists():
                continue

            server_type = "full" if (server_dir / "server.py").exists() else "wrapper"

            manifest: dict[str, Any] = {}
            manifest_path = server_dir / "manifest.yaml"
            if manifest_path.exists():
                try:
                    manifest = yaml.safe_load(manifest_path.read_text()) or {}
                except yaml.YAMLError:
                    manifest = {}

            servers.append(
                MCPServer(
                    category=category_dir.name,
                    name=server_dir.name,
                    path=server_dir,
                    server_type=server_type,
                    manifest=manifest,
                )
            )

    return servers


def full_servers(root: Path = ROOT_DIR) -> list[MCPServer]:
    """Return only servers with a server.py implementation."""
    return [s for s in discover_servers(root) if s.server_type == "full"]


def wrapper_servers(root: Path = ROOT_DIR) -> list[MCPServer]:
    """Return only wrapper servers (Dockerfile-only)."""
    return [s for s in discover_servers(root) if s.server_type == "wrapper"]
