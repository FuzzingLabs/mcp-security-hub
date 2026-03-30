"""Test suite for MCP Security Hub servers.

Tests are organized in tiers:

Tier 1 — Structure (instant, no Docker)
    File existence, naming conventions.
    manifest.yaml is only required for wrapper servers (no server.py to introspect).

Tier 2 — MCP compliance (fast, Python-only, full servers only)
    server.py imports, list_tools() works, tools have valid schemas.

Tier 3 — Docker smoke (slow, requires Docker)
    Build image, start container, speak MCP JSON-RPC, validate tools/list.
    For full servers: expected tools are generated from list_tools() at test time.
    For wrapper servers: expected tools come from manifest.yaml.
    Marked with @pytest.mark.docker so it only runs when requested.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

import pytest

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

    @pytest.mark.parametrize(
        "server", WRAPPER_SERVERS, ids=[_sid(s) for s in WRAPPER_SERVERS]
    )
    def test_wrapper_manifest_exists(self, server: MCPServer):
        """Wrapper servers must have manifest.yaml (only source of truth)."""
        assert server.manifest_path.exists(), (
            f"Missing manifest.yaml for wrapper: {server.path}\n"
            f"Wrapper servers need a manifest since there is no server.py to introspect."
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
        "server", WRAPPER_SERVERS, ids=[_sid(s) for s in WRAPPER_SERVERS]
    )
    def test_wrapper_manifest_valid(self, server: MCPServer):
        """Wrapper manifest must have required fields."""
        manifest = server.manifest
        assert isinstance(manifest, dict), "Manifest is not a dict"
        assert "name" in manifest, "Manifest missing 'name'"
        assert "category" in manifest, "Manifest missing 'category'"
        assert "type" in manifest, "Manifest missing 'type'"
        assert manifest["name"] == server.name, (
            f"Manifest name '{manifest['name']}' != directory name '{server.name}'"
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
# Tier 3 — Docker MCP smoke test (slow, opt-in)
# ═════════════════════════════════════════════════════════════════════════════

# Wrappers with manifest declaring tools can be smoke-tested against manifest.
WRAPPER_WITH_TOOLS = [
    s for s in WRAPPER_SERVERS
    if s.has_manifest and s.manifest.get("tools")
]


def _tools_from_module_sync(server: MCPServer) -> list[dict[str, Any]]:
    """Load server.py and extract expected tools (synchronous wrapper)."""
    import asyncio

    module = load_server_module(server)
    loop = asyncio.new_event_loop()
    try:
        tools = loop.run_until_complete(get_tools_from_module(module))
    finally:
        loop.close()

    result = []
    for tool in tools:
        entry: dict[str, Any] = {"name": tool.name}
        schema = getattr(tool, "inputSchema", {})
        required = schema.get("required", [])
        if required:
            entry["required_params"] = required
        result.append(entry)
    return result


@pytest.mark.docker
class TestDockerSmoke:
    """Build image, start container, validate MCP protocol and tool list.

    For full servers: expected tools generated from list_tools() at test time.
    For wrapper servers: expected tools come from manifest.yaml.

    Run with: pytest -m docker
    """

    @pytest.mark.parametrize(
        "server", FULL_SERVERS, ids=[_sid(s) for s in FULL_SERVERS]
    )
    def test_full_server_smoke(self, server: MCPServer, docker_available):
        """MCP smoke test for full servers — expected tools from list_tools()."""
        if not docker_available:
            pytest.skip("Docker not available")

        from mcp_harness import MCPSmokeTestError, build_image, run_mcp_smoke_test

        image_tag = f"test-{server.name}:smoke"
        expected_tools = _tools_from_module_sync(server)

        try:
            build_image(server.path, image_tag, timeout=600)
        except MCPSmokeTestError as e:
            pytest.fail(str(e))

        try:
            result = run_mcp_smoke_test(
                image_tag=image_tag,
                expected_tools=expected_tools,
                timeout=30.0,
            )
        except MCPSmokeTestError as e:
            pytest.fail(f"MCP smoke test failed for {server.name}: {e}")
        finally:
            import subprocess
            subprocess.run(["docker", "rmi", "-f", image_tag], capture_output=True)

        assert not result["errors"], (
            f"Contract violations for {server.name}:\n"
            + "\n".join(f"  - {e}" for e in result["errors"])
        )

    @pytest.mark.parametrize(
        "server", WRAPPER_WITH_TOOLS, ids=[_sid(s) for s in WRAPPER_WITH_TOOLS]
    )
    def test_wrapper_smoke(self, server: MCPServer, docker_available):
        """MCP smoke test for wrapper servers — expected tools from manifest.yaml."""
        if not docker_available:
            pytest.skip("Docker not available")

        from mcp_harness import MCPSmokeTestError, build_image, run_mcp_smoke_test

        image_tag = f"test-{server.name}:smoke"
        expected_tools = server.manifest.get("tools", [])

        try:
            build_image(server.path, image_tag, timeout=600)
        except MCPSmokeTestError as e:
            pytest.fail(str(e))

        try:
            result = run_mcp_smoke_test(
                image_tag=image_tag,
                expected_tools=expected_tools,
                timeout=30.0,
            )
        except MCPSmokeTestError as e:
            pytest.fail(f"MCP smoke test failed for {server.name}: {e}")
        finally:
            import subprocess
            subprocess.run(["docker", "rmi", "-f", image_tag], capture_output=True)

        assert not result["errors"], (
            f"Contract violations for {server.name}:\n"
            + "\n".join(f"  - {e}" for e in result["errors"])
        )
