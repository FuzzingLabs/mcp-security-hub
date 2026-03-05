#!/usr/bin/env python3
"""
Semgrep MCP Server

A Model Context Protocol server that provides static code analysis
capabilities using Semgrep.

Tools:
    - semgrep_scan: Scan code files with default or registry rules
    - semgrep_scan_with_custom_rule: Scan code with a custom YAML rule
    - get_supported_languages: List languages supported by Semgrep
    - get_abstract_syntax_tree: Get AST for code in any supported language
    - semgrep_rule_schema: Get the YAML schema for writing Semgrep rules
"""

import asyncio
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("semgrep-mcp")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_TIMEOUT = int(os.environ.get("SEMGREP_TIMEOUT", "120"))
HOST = os.environ.get("SEMGREP_MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("SEMGREP_MCP_PORT", "8000"))

# ---------------------------------------------------------------------------
# FastMCP application
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "Semgrep",
    host=HOST,
    port=PORT,
    stateless_http=True,
    json_response=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _run_semgrep(args: list[str], timeout: int = DEFAULT_TIMEOUT) -> tuple[str, str, int]:
    """Run a semgrep command asynchronously and return (stdout, stderr, returncode)."""
    cmd = ["semgrep", *args]
    logger.info(f"Running: {' '.join(cmd)}")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise TimeoutError(f"semgrep timed out after {timeout}s")

    return stdout.decode(), stderr.decode(), proc.returncode


def _clean_temp_paths(data: dict, tmpdir: str) -> None:
    """Remove temp directory prefixes from scan results."""
    # Semgrep converts the rule file path into a dot-separated check_id prefix.
    # e.g. /tmp/semgrep_scan_abc123/rule.yaml -> "tmp.semgrep_scan_abc123.my-rule"
    # Strip everything derived from the temp dir path.
    tmpdir_clean = tmpdir.strip("/")
    prefix_dot = tmpdir_clean.replace("/", ".") + "."
    for result in data.get("results", []):
        # Clean file paths
        p = result.get("path", "")
        if p.startswith(tmpdir):
            result["path"] = p[len(tmpdir) + 1:]
        # Clean check_id prefix
        cid = result.get("check_id", "")
        if cid.startswith(prefix_dot):
            result["check_id"] = cid[len(prefix_dot):]
    # Also clean scanned paths
    for key in ("scanned", "_comment"):
        if key in data.get("paths", {}):
            data["paths"][key] = [
                p[len(tmpdir) + 1:] if p.startswith(tmpdir) else p
                for p in data["paths"][key]
            ]


def _write_code_files(tmpdir: str, code_files: list[dict]) -> list[str]:
    """Write code files into a temporary directory. Returns list of paths."""
    paths = []
    for cf in code_files:
        p = os.path.join(tmpdir, cf["path"])
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(cf["content"])
        paths.append(p)
    return paths


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_supported_languages() -> str:
    """
    Returns a list of programming languages supported by Semgrep.

    Only use this tool if you are not sure what languages Semgrep supports.
    """
    stdout, stderr, rc = await _run_semgrep(["show", "supported-languages"])
    if rc != 0:
        raise RuntimeError(f"semgrep failed (rc={rc}): {stderr}")
    return stdout.strip()


@mcp.tool()
async def get_abstract_syntax_tree(
    code: str,
    language: str,
    named_only: bool = False,
) -> str:
    """
    Returns the Abstract Syntax Tree (AST) for the provided code in JSON format.

    Use this tool when you need to:
      - get the AST for a piece of code
      - understand the structure of the code at a parser level
    """
    tmpdir = tempfile.mkdtemp(prefix="semgrep_ast_")
    try:
        fpath = os.path.join(tmpdir, "code.txt")
        with open(fpath, "w") as f:
            f.write(code)

        args = ["scan", "--experimental", "--dump-ast", "-l", language, "--json", fpath]
        stdout, stderr, rc = await _run_semgrep(args)
        if rc != 0:
            raise RuntimeError(f"semgrep dump-ast failed (rc={rc}): {stderr}")
        return stdout.strip()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@mcp.tool()
async def semgrep_rule_schema() -> str:
    """
    Get the schema for a Semgrep rule.

    Use this tool when you need to:
      - know what fields are available for a Semgrep rule
      - verify the syntax for a Semgrep rule
      - write a custom Semgrep rule
    """
    stdout, stderr, rc = await _run_semgrep(["scan", "--validate", "--help"])
    # The schema is large; provide a minimal helpful summary instead.
    # For the full reference, point to the official docs.
    schema_summary = {
        "reference": "https://semgrep.dev/docs/writing-rules/rule-syntax",
        "top_level_keys": {
            "rules": "List of rule objects",
        },
        "rule_keys": {
            "id": "(required) Unique rule identifier",
            "pattern": "Single Semgrep pattern to match",
            "patterns": "List of pattern clauses combined with AND logic",
            "pattern-either": "List of pattern clauses combined with OR logic",
            "pattern-regex": "PCRE-compatible regex pattern",
            "message": "(required) Explanation shown when the rule matches",
            "languages": "(required) List of target languages, e.g. ['python', 'javascript']",
            "severity": "(required) One of: ERROR, WARNING, INFO",
            "fix": "Auto-fix replacement text",
            "metadata": "Arbitrary key-value metadata (category, confidence, etc.)",
            "options": "Advanced options (e.g. symbolic_propagation)",
        },
        "example": (
            "rules:\n"
            "  - id: no-eval\n"
            "    pattern: eval(...)\n"
            "    message: Do not use eval()\n"
            "    languages: [python]\n"
            "    severity: ERROR\n"
        ),
    }
    return json.dumps(schema_summary, indent=2)


@mcp.tool()
async def semgrep_scan_with_custom_rule(
    code_files: list[dict],
    rule: str,
) -> str:
    """
    Scan code files with a custom Semgrep YAML rule.

    Use this tool when you need to:
      - scan code for a specific vulnerability pattern
      - check code against a custom rule you wrote

    Args:
        code_files: List of objects with 'path' and 'content' keys.
                    Example: [{"path": "app.py", "content": "import os\\nos.system(input())"}]
        rule: A complete Semgrep YAML rule string starting with 'rules:'.
    """
    tmpdir = tempfile.mkdtemp(prefix="semgrep_scan_")
    try:
        _write_code_files(tmpdir, code_files)

        rule_path = os.path.join(tmpdir, "rule.yaml")
        with open(rule_path, "w") as f:
            f.write(rule)

        args = [
            "scan",
            "--config", rule_path,
            "--json",
            "--no-git-ignore",
            "--x-mcp",
            tmpdir,
        ]
        stdout, stderr, rc = await _run_semgrep(args)

        # semgrep exits 0 for no findings, 1 for findings, >1 for errors
        if rc > 1:
            raise RuntimeError(f"semgrep scan failed (rc={rc}): {stderr}")

        # Parse and clean up temp paths from output
        try:
            data = json.loads(stdout)
            _clean_temp_paths(data, tmpdir)
            return json.dumps(data, indent=2)
        except json.JSONDecodeError:
            return stdout.strip()

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@mcp.tool()
async def semgrep_scan(
    code_files: list[dict],
    config: str = "auto",
) -> str:
    """
    Scan code files with Semgrep using registry rules.

    Use this tool when you need to:
      - scan code for security vulnerabilities using Semgrep's default rules
      - scan code for code quality issues
      - run a general security audit on code

    Args:
        code_files: List of objects with 'path' and 'content' keys.
                    Example: [{"path": "app.py", "content": "import os\\nos.system(input())"}]
        config: Semgrep config string (default: "auto" for recommended rules).
                Can also be a registry rule ID like "p/python" or "p/owasp-top-ten".
    """
    tmpdir = tempfile.mkdtemp(prefix="semgrep_scan_")
    try:
        _write_code_files(tmpdir, code_files)

        args = [
            "scan",
            "--config", config,
            "--json",
            "--no-git-ignore",
            "--x-mcp",
            tmpdir,
        ]
        stdout, stderr, rc = await _run_semgrep(args)

        if rc > 1:
            raise RuntimeError(f"semgrep scan failed (rc={rc}): {stderr}")

        try:
            data = json.loads(stdout)
            _clean_temp_paths(data, tmpdir)
            return json.dumps(data, indent=2)
        except json.JSONDecodeError:
            return stdout.strip()

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    transport = "streamable-http"
    for arg in sys.argv[1:]:
        if arg in ("stdio", "streamable-http", "sse"):
            transport = arg

    logger.info(f"Starting Semgrep MCP Server (transport={transport})")

    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http")
