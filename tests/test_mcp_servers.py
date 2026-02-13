"""
Unit tests for all MCP servers.

Tests verify:
1. Server modules import without errors
2. Server app is properly configured
3. Tools are properly defined with required fields
"""

import importlib.util
import sys
from pathlib import Path

import pytest

# Root directory of the project
ROOT_DIR = Path(__file__).parent.parent

# MCP servers with full Python implementation (server.py)
MCP_SERVERS = [
    ("reconnaissance", "nmap-mcp"),
    ("reconnaissance", "whatweb-mcp"),
    ("reconnaissance", "masscan-mcp"),
    ("web-security", "nuclei-mcp"),
    ("web-security", "sqlmap-mcp"),
    ("web-security", "ffuf-mcp"),
    ("binary-analysis", "binwalk-mcp"),
    ("binary-analysis", "yara-mcp"),
    ("binary-analysis", "capa-mcp"),
    ("cloud-security", "trivy-mcp"),
    ("cloud-security", "prowler-mcp"),
    ("exploitation", "searchsploit-mcp"),
    ("blockchain", "daml-viewer-mcp"),
]

# MCP servers that wrap external implementations (Dockerfile only, no server.py)
MCP_WRAPPERS = [
    ("reconnaissance", "shodan-mcp"),
    ("reconnaissance", "pd-tools-mcp"),
    ("web-security", "nikto-mcp"),
    ("binary-analysis", "radare2-mcp"),
]

# All MCPs (for file existence tests)
ALL_MCPS = MCP_SERVERS + MCP_WRAPPERS


def load_server_module(category: str, mcp_name: str):
    """Dynamically load a server.py module from an MCP directory."""
    server_path = ROOT_DIR / category / mcp_name / "server.py"

    if not server_path.exists():
        pytest.skip(f"Server not found: {server_path}")

    module_name = f"{category.replace('-', '_')}_{mcp_name.replace('-', '_')}_server"
    spec = importlib.util.spec_from_file_location(module_name, server_path)
    module = importlib.util.module_from_spec(spec)

    # Add the MCP directory to path for relative imports
    mcp_dir = str(server_path.parent)
    if mcp_dir not in sys.path:
        sys.path.insert(0, mcp_dir)

    try:
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        pytest.fail(f"Failed to import {server_path}: {e}")


def get_mcp_ids():
    """Generate test IDs for parametrized tests."""
    return [f"{cat}/{name}" for cat, name in MCP_SERVERS]


@pytest.mark.parametrize("category,mcp_name", MCP_SERVERS, ids=get_mcp_ids())
class TestMCPServer:
    """Test suite for MCP servers."""

    def test_server_imports(self, category: str, mcp_name: str):
        """Test that server.py imports without errors."""
        module = load_server_module(category, mcp_name)
        assert module is not None

    def test_server_has_app(self, category: str, mcp_name: str):
        """Test that server has an 'app' attribute."""
        module = load_server_module(category, mcp_name)
        assert hasattr(module, "app"), f"Server {mcp_name} missing 'app' attribute"

    def test_app_has_name(self, category: str, mcp_name: str):
        """Test that app has a name configured."""
        module = load_server_module(category, mcp_name)
        app = module.app
        # The MCP Server stores name in _name attribute
        assert hasattr(app, "name") or hasattr(app, "_name"), "App missing name"

    @pytest.mark.asyncio
    async def test_list_tools_returns_tools(self, category: str, mcp_name: str):
        """Test that list_tools() returns a non-empty list."""
        module = load_server_module(category, mcp_name)

        # Find the list_tools handler
        if hasattr(module, "list_tools"):
            tools = await module.list_tools()
        elif hasattr(module.app, "_tool_handlers"):
            # Access internal handler
            handler = module.app._tool_handlers.get("list_tools")
            if handler:
                tools = await handler()
            else:
                pytest.skip("No list_tools handler found")
        else:
            pytest.skip("Cannot find list_tools method")

        assert tools is not None, "list_tools() returned None"
        assert len(tools) > 0, f"Server {mcp_name} has no tools defined"

    @pytest.mark.asyncio
    async def test_tools_have_required_fields(self, category: str, mcp_name: str):
        """Test that each tool has name, description, and inputSchema."""
        module = load_server_module(category, mcp_name)

        # Find the list_tools handler
        if hasattr(module, "list_tools"):
            tools = await module.list_tools()
        elif hasattr(module.app, "_tool_handlers"):
            handler = module.app._tool_handlers.get("list_tools")
            if handler:
                tools = await handler()
            else:
                pytest.skip("No list_tools handler found")
        else:
            pytest.skip("Cannot find list_tools method")

        for tool in tools:
            assert hasattr(tool, "name") and tool.name, f"Tool missing name in {mcp_name}"
            assert hasattr(tool, "description") and tool.description, (
                f"Tool {tool.name} missing description in {mcp_name}"
            )
            assert hasattr(tool, "inputSchema"), (
                f"Tool {tool.name} missing inputSchema in {mcp_name}"
            )


def get_all_mcp_ids():
    """Generate test IDs for all MCPs."""
    return [f"{cat}/{name}" for cat, name in ALL_MCPS]


class TestMCPServerPaths:
    """Test that all expected MCP directories exist."""

    @pytest.mark.parametrize("category,mcp_name", MCP_SERVERS, ids=get_mcp_ids())
    def test_server_file_exists(self, category: str, mcp_name: str):
        """Test that server.py exists for full implementation MCPs."""
        server_path = ROOT_DIR / category / mcp_name / "server.py"
        assert server_path.exists(), f"Missing: {server_path}"

    @pytest.mark.parametrize("category,mcp_name", ALL_MCPS, ids=get_all_mcp_ids())
    def test_dockerfile_exists(self, category: str, mcp_name: str):
        """Test that Dockerfile exists for each MCP."""
        dockerfile_path = ROOT_DIR / category / mcp_name / "Dockerfile"
        assert dockerfile_path.exists(), f"Missing: {dockerfile_path}"

    @pytest.mark.parametrize("category,mcp_name", MCP_SERVERS, ids=get_mcp_ids())
    def test_requirements_exists(self, category: str, mcp_name: str):
        """Test that requirements.txt exists for full implementation MCPs."""
        req_path = ROOT_DIR / category / mcp_name / "requirements.txt"
        assert req_path.exists(), f"Missing: {req_path}"

    @pytest.mark.parametrize("category,mcp_name", ALL_MCPS, ids=get_all_mcp_ids())
    def test_readme_exists(self, category: str, mcp_name: str):
        """Test that README.md exists for each MCP."""
        readme_path = ROOT_DIR / category / mcp_name / "README.md"
        assert readme_path.exists(), f"Missing: {readme_path}"


class TestMCPWrappers:
    """Test wrapper MCPs have required files."""

    @pytest.mark.parametrize(
        "category,mcp_name",
        MCP_WRAPPERS,
        ids=[f"{cat}/{name}" for cat, name in MCP_WRAPPERS],
    )
    def test_wrapper_has_dockerfile(self, category: str, mcp_name: str):
        """Test that wrapper MCPs have a Dockerfile."""
        dockerfile_path = ROOT_DIR / category / mcp_name / "Dockerfile"
        assert dockerfile_path.exists(), f"Missing: {dockerfile_path}"
