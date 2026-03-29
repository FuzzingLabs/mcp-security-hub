"""Test suite for MCP Security Hub servers.

Tests are organized in tiers:

Tier 1 — Structure (instant, no Docker)
    File existence, manifest presence, naming conventions.

Tier 2 — MCP compliance (fast, Python-only)
    server.py imports, list_tools() works, tools have valid schemas.

Tier 3 — Contract (fast, Python-only)
    list_tools() output matches manifest.yaml declarations.

Tier 4 — Docker smoke (slow, requires Docker)
    Build image, start container, speak MCP JSON-RPC, validate tools/list.
    Marked with @pytest.mark.docker so it only runs when requested.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

# Ensure tests/ directory is on path for discovery/harness imports
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from discovery import MCPServer, discover_servers, full_servers

ROOT_DIR = Path(__file__).resolve().parent.parent

# ─── Discovery-based fixtures ───────────────────────────────────────────────

ALL_SERVERS = discover_servers(ROOT_DIR)
FULL_SERVERS = [s for s in ALL_SERVERS if s.server_type == "full"]
WRAPPER_SERVERS = [s for s in ALL_SERVERS if s.server_type == "wrapper"]
SERVERS_WITH_MANIFESTS = [s for s in ALL_SERVERS if s.has_manifest]
FULL_WITH_MANIFESTS = [s for s in FULL_SERVERS if s.has_manifest]


def _sid(server: MCPServer) -> str:
    return f"{server.category}/{server.name}"


# ─── Helpers ─────────────────────────────────────────────────────────────────


def load_server_module(server: MCPServer):
    """Dynamically load a server.py module."""
    server_path = server.server_py
    if not server_path.exists():
        pytest.skip(f"No server.py: {server.path}")

    module_name = f"{server.category}_{server.name}".replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, server_path)
    if spec is None or spec.loader is None:
        pytest.fail(f"Cannot create module spec for {server_path}")

    module = importlib.util.module_from_spec(spec)

    mcp_dir = str(server_path.parent)
    if mcp_dir not in sys.path:
        sys.path.insert(0, mcp_dir)

    try:
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        pytest.fail(f"Failed to import {server_path}: {e}")


async def get_tools_from_module(module) -> list:
    """Extract tools from a loaded server module."""
    if hasattr(module, "list_tools"):
        return await module.list_tools()

    if hasattr(module.app, "_tool_handlers"):
        handler = module.app._tool_handlers.get("list_tools")
        if handler:
            return await handler()

    pytest.skip("Cannot find list_tools method")
    return []


# ═════════════════════════════════════════════════════════════════════════════
# Tier 1 — Structure validation
# ═════════════════════════════════════════════════════════════════════════════


class TestStructure:
    """File existence and naming convention checks."""

    @pytest.mark.parametrize("server", ALL_SERVERS, ids=[_sid(s) for s in ALL_SERVERS])
    def test_dockerfile_exists(self, server: MCPServer):
        assert server.dockerfile.exists(), f"Missing Dockerfile: {server.path}"

    @pytest.mark.parametrize("server", ALL_SERVERS, ids=[_sid(s) for s in ALL_SERVERS])
    def test_readme_exists(self, server: MCPServer):
        assert server.readme.exists(), f"Missing README.md: {server.path}"

    @pytest.mark.parametrize("server", ALL_SERVERS, ids=[_sid(s) for s in ALL_SERVERS])
    def test_manifest_exists(self, server: MCPServer):
        assert server.manifest_path.exists(), (
            f"Missing manifest.yaml: {server.path}\n"
            f"Run: python scripts/generate_manifests.py"
        )

    @pytest.mark.parametrize("server", FULL_SERVERS, ids=[_sid(s) for s in FULL_SERVERS])
    def test_server_py_exists(self, server: MCPServer):
        assert server.server_py.exists(), f"Missing server.py for full server: {server.path}"

    @pytest.mark.parametrize("server", FULL_SERVERS, ids=[_sid(s) for s in FULL_SERVERS])
    def test_requirements_exists(self, server: MCPServer):
        assert server.requirements.exists(), f"Missing requirements.txt: {server.path}"

    @pytest.mark.parametrize("server", ALL_SERVERS, ids=[_sid(s) for s in ALL_SERVERS])
    def test_name_convention(self, server: MCPServer):
        """Server directory name should contain 'mcp'."""
        assert "mcp" in server.name, (
            f"Server name '{server.name}' should contain 'mcp'"
        )

    @pytest.mark.parametrize(
        "server", SERVERS_WITH_MANIFESTS, ids=[_sid(s) for s in SERVERS_WITH_MANIFESTS]
    )
    def test_manifest_valid_yaml(self, server: MCPServer):
        """Manifest must be valid YAML with required fields."""
        manifest = server.manifest
        assert isinstance(manifest, dict), "Manifest is not a dict"
        assert "name" in manifest, "Manifest missing 'name'"
        assert "category" in manifest, "Manifest missing 'category'"
        assert "type" in manifest, "Manifest missing 'type'"
        assert manifest["type"] in ("full", "wrapper"), (
            f"Manifest type must be 'full' or 'wrapper', got '{manifest['type']}'"
        )
        assert manifest["name"] == server.name, (
            f"Manifest name '{manifest['name']}' != directory name '{server.name}'"
        )
        assert manifest["category"] == server.category, (
            f"Manifest category '{manifest['category']}' != directory '{server.category}'"
        )

    @pytest.mark.parametrize(
        "server", SERVERS_WITH_MANIFESTS, ids=[_sid(s) for s in SERVERS_WITH_MANIFESTS]
    )
    def test_manifest_tools_format(self, server: MCPServer):
        """If manifest declares tools, each must have a name."""
        tools = server.manifest.get("tools", [])
        if not tools:
            return
        for tool in tools:
            assert isinstance(tool, dict), f"Tool entry is not a dict: {tool}"
            assert "name" in tool, f"Tool entry missing 'name': {tool}"
            assert re.match(r"^[a-z][a-z0-9_]*$", tool["name"]), (
                f"Tool name '{tool['name']}' must be snake_case"
            )


# ═════════════════════════════════════════════════════════════════════════════
# Tier 2 — MCP compliance (Python import tests)
# ═════════════════════════════════════════════════════════════════════════════


class TestMCPCompliance:
    """Verify server.py modules follow MCP conventions."""

    @pytest.mark.parametrize("server", FULL_SERVERS, ids=[_sid(s) for s in FULL_SERVERS])
    def test_server_imports(self, server: MCPServer):
        module = load_server_module(server)
        assert module is not None

    @pytest.mark.parametrize("server", FULL_SERVERS, ids=[_sid(s) for s in FULL_SERVERS])
    def test_server_has_app(self, server: MCPServer):
        module = load_server_module(server)
        assert hasattr(module, "app"), f"Server {server.name} missing 'app' attribute"

    @pytest.mark.parametrize("server", FULL_SERVERS, ids=[_sid(s) for s in FULL_SERVERS])
    def test_app_has_name(self, server: MCPServer):
        module = load_server_module(server)
        app = module.app
        assert hasattr(app, "name") or hasattr(app, "_name"), "App missing name"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("server", FULL_SERVERS, ids=[_sid(s) for s in FULL_SERVERS])
    async def test_list_tools_returns_tools(self, server: MCPServer):
        module = load_server_module(server)
        tools = await get_tools_from_module(module)
        assert tools is not None, "list_tools() returned None"
        assert len(tools) > 0, f"Server {server.name} has no tools"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("server", FULL_SERVERS, ids=[_sid(s) for s in FULL_SERVERS])
    async def test_tools_have_required_fields(self, server: MCPServer):
        module = load_server_module(server)
        tools = await get_tools_from_module(module)

        for tool in tools:
            assert hasattr(tool, "name") and tool.name, (
                f"Tool missing name in {server.name}"
            )
            assert hasattr(tool, "description") and tool.description, (
                f"Tool '{tool.name}' missing description in {server.name}"
            )
            assert hasattr(tool, "inputSchema"), (
                f"Tool '{tool.name}' missing inputSchema in {server.name}"
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("server", FULL_SERVERS, ids=[_sid(s) for s in FULL_SERVERS])
    async def test_tool_schemas_valid(self, server: MCPServer):
        """Each tool's inputSchema must be a valid JSON Schema object."""
        module = load_server_module(server)
        tools = await get_tools_from_module(module)

        for tool in tools:
            schema = getattr(tool, "inputSchema", None)
            if schema is None:
                continue
            assert isinstance(schema, dict), (
                f"Tool '{tool.name}' inputSchema is not a dict"
            )
            assert schema.get("type") == "object", (
                f"Tool '{tool.name}' inputSchema type must be 'object'"
            )
            props = schema.get("properties")
            if props is not None:
                assert isinstance(props, dict), (
                    f"Tool '{tool.name}' properties must be a dict"
                )


# ═════════════════════════════════════════════════════════════════════════════
# Tier 3 — Contract tests (manifest vs runtime)
# ═════════════════════════════════════════════════════════════════════════════


class TestContract:
    """Verify list_tools() output matches manifest declarations."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "server", FULL_WITH_MANIFESTS, ids=[_sid(s) for s in FULL_WITH_MANIFESTS]
    )
    async def test_manifest_tools_present(self, server: MCPServer):
        """Every tool declared in manifest must be returned by list_tools()."""
        module = load_server_module(server)
        tools = await get_tools_from_module(module)
        tool_names = {t.name for t in tools}

        manifest_tools = server.manifest.get("tools", [])
        if not manifest_tools:
            pytest.skip("Manifest declares no tools")

        missing = []
        for expected in manifest_tools:
            if expected["name"] not in tool_names:
                missing.append(expected["name"])

        assert not missing, (
            f"Tools declared in manifest but missing from list_tools(): {missing}\n"
            f"Server returns: {sorted(tool_names)}"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "server", FULL_WITH_MANIFESTS, ids=[_sid(s) for s in FULL_WITH_MANIFESTS]
    )
    async def test_manifest_required_params(self, server: MCPServer):
        """Required params declared in manifest must appear in tool schema."""
        module = load_server_module(server)
        tools = await get_tools_from_module(module)
        tools_by_name = {t.name: t for t in tools}

        manifest_tools = server.manifest.get("tools", [])
        errors = []

        for expected in manifest_tools:
            name = expected["name"]
            expected_params = set(expected.get("required_params", []))
            if not expected_params:
                continue

            tool = tools_by_name.get(name)
            if tool is None:
                continue  # caught by test_manifest_tools_present

            schema = getattr(tool, "inputSchema", {})
            actual_required = set(schema.get("required", []))
            missing = expected_params - actual_required
            if missing:
                errors.append(f"Tool '{name}' missing required params: {missing}")

        assert not errors, "\n".join(errors)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "server", FULL_WITH_MANIFESTS, ids=[_sid(s) for s in FULL_WITH_MANIFESTS]
    )
    async def test_no_undeclared_tools(self, server: MCPServer):
        """Warn about tools returned by server but not in manifest.

        New tools aren't errors, but the manifest should be kept in sync.
        """
        module = load_server_module(server)
        tools = await get_tools_from_module(module)
        tool_names = {t.name for t in tools}

        manifest_tools = server.manifest.get("tools", [])
        declared = {t["name"] for t in manifest_tools}

        undeclared = tool_names - declared
        if undeclared:
            pytest.warns(
                UserWarning,
                match="undeclared",
            ) if False else None
            # This is informational — just print a warning
            import warnings
            warnings.warn(
                f"Tools not in manifest for {server.name}: {sorted(undeclared)}. "
                f"Run: python scripts/generate_manifests.py --all",
                stacklevel=1,
            )


# ═════════════════════════════════════════════════════════════════════════════
# Tier 4 — Docker MCP smoke test (slow, opt-in)
# ═════════════════════════════════════════════════════════════════════════════

# Only servers with manifests declaring tools can be smoke-tested.
SMOKE_TESTABLE = [
    s for s in SERVERS_WITH_MANIFESTS
    if s.manifest.get("tools")
]


@pytest.mark.docker
class TestDockerSmoke:
    """Build image, start container, validate MCP protocol and tool list.

    Run with: pytest -m docker
    """

    @pytest.mark.parametrize(
        "server", SMOKE_TESTABLE, ids=[_sid(s) for s in SMOKE_TESTABLE]
    )
    def test_mcp_smoke(self, server: MCPServer, docker_available):
        """Full MCP protocol smoke test inside Docker."""
        if not docker_available:
            pytest.skip("Docker not available")

        from mcp_harness import MCPSmokeTestError, build_image, run_mcp_smoke_test

        image_tag = f"test-{server.name}:smoke"

        # Build
        try:
            build_image(server.path, image_tag, timeout=600)
        except MCPSmokeTestError as e:
            pytest.fail(str(e))

        # Test MCP protocol
        try:
            result = run_mcp_smoke_test(
                image_tag=image_tag,
                manifest=server.manifest,
                timeout=30.0,
            )
        except MCPSmokeTestError as e:
            pytest.fail(f"MCP smoke test failed for {server.name}: {e}")
        finally:
            # Cleanup image
            import subprocess
            subprocess.run(
                ["docker", "rmi", "-f", image_tag],
                capture_output=True,
            )

        assert not result["errors"], (
            f"Contract violations for {server.name}:\n"
            + "\n".join(f"  - {e}" for e in result["errors"])
        )
