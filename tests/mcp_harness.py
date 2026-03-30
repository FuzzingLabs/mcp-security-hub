"""MCP protocol smoke test harness.

Builds a Docker image, starts the container, speaks MCP JSON-RPC over
stdin/stdout, and validates the ``tools/list`` response against expected
tool declarations.

This is the only test that catches real breakages: upstream binary
changes, renamed entrypoints, broken dependencies inside the container.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

_INITIALIZE_REQUEST: dict[str, Any] = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "fuzzforge-test", "version": "1.0.0"},
    },
}

_INITIALIZED_NOTIFICATION: dict[str, Any] = {
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
}

_LIST_TOOLS_REQUEST: dict[str, Any] = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {},
}


class MCPSmokeTestError(Exception):
    """Raised when the MCP smoke test fails."""


def build_image(server_path: Path, image_tag: str, timeout: int = 300) -> None:
    """Build the Docker image for a server.

    :param server_path: Path to the server directory containing Dockerfile.
    :param image_tag: Tag for the built image.
    :param timeout: Build timeout in seconds.
    :raises MCPSmokeTestError: If the build fails.
    """
    result = subprocess.run(
        ["docker", "build", "-t", image_tag, "."],
        cwd=server_path,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise MCPSmokeTestError(
            f"Docker build failed for {server_path.name}:\n{result.stderr[-2000:]}"
        )


def _send_jsonrpc(proc: subprocess.Popen, message: dict[str, Any]) -> None:
    """Send a JSON-RPC message to the MCP server via stdin."""
    payload = json.dumps(message) + "\n"
    proc.stdin.write(payload)
    proc.stdin.flush()


def _read_response(proc: subprocess.Popen, timeout: float = 30.0) -> dict[str, Any]:
    """Read a JSON-RPC response from stdout, skipping notifications."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            # Check if process has died
            if proc.poll() is not None:
                stderr = proc.stderr.read() if proc.stderr else ""
                raise MCPSmokeTestError(
                    f"MCP server exited with code {proc.returncode}: {stderr[-2000:]}"
                )
            time.sleep(0.1)
            continue

        line = line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Skip notifications (no "id" field)
        if "id" in msg:
            return msg

    raise MCPSmokeTestError("Timed out waiting for MCP response")


def run_mcp_smoke_test(
    image_tag: str,
    expected_tools: list[dict[str, Any]] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Start a container, perform MCP handshake, and validate tools/list.

    :param image_tag: Docker image tag to run.
    :param expected_tools: List of expected tool dicts ({"name": ..., "required_params": [...]}).
        If None, only validates that the MCP handshake succeeds and tools/list returns.
    :param timeout: Per-request timeout.
    :returns: Dict with tools found and validation results.
    :raises MCPSmokeTestError: On protocol errors.
    """
    proc = subprocess.Popen(
        ["docker", "run", "-i", "--rm", image_tag],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    try:
        # Step 1: initialize
        _send_jsonrpc(proc, _INITIALIZE_REQUEST)
        init_response = _read_response(proc, timeout)

        if "error" in init_response:
            raise MCPSmokeTestError(
                f"MCP initialize failed: {init_response['error']}"
            )

        # Step 2: send initialized notification
        _send_jsonrpc(proc, _INITIALIZED_NOTIFICATION)

        # Step 3: tools/list
        _send_jsonrpc(proc, _LIST_TOOLS_REQUEST)
        tools_response = _read_response(proc, timeout)

        if "error" in tools_response:
            raise MCPSmokeTestError(
                f"MCP tools/list failed: {tools_response['error']}"
            )

        tools = tools_response.get("result", {}).get("tools", [])
        tool_names = {t["name"] for t in tools}

        # Validate against expected tools
        errors: list[str] = []
        if expected_tools:
            for expected_tool in expected_tools:
                name = expected_tool["name"]
                if name not in tool_names:
                    errors.append(f"Tool '{name}' expected but not returned by server")

                # Check required params if tool exists
                matching = [t for t in tools if t["name"] == name]
                if matching:
                    schema = matching[0].get("inputSchema", {})
                    schema_required = set(schema.get("required", []))
                    expected_required = set(expected_tool.get("required_params", []))
                    missing_params = expected_required - schema_required
                    if missing_params:
                        errors.append(
                            f"Tool '{name}' missing required params: {missing_params}"
                        )

        return {
            "tools_found": sorted(tool_names),
            "tools_expected": [t["name"] for t in expected_tools] if expected_tools else [],
            "tool_count": len(tools),
            "errors": errors,
            "init_response": init_response,
        }

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
