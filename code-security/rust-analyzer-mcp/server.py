#!/usr/bin/env python3
"""Rust Analyzer MCP Server.

A Model Context Protocol server that analyzes Rust source code to identify
fuzzable entry points, unsafe blocks, and known CVEs via cargo-audit.

Tools:
    - rust_analyze: Full static analysis of a Rust project
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("rust-analyzer-mcp")


class Settings(BaseSettings):
    """Server configuration from environment variables."""

    default_timeout: int = Field(default=300, alias="RUST_ANALYZER_TIMEOUT")

    class Config:
        env_prefix = "RUST_ANALYZER_"


settings = Settings()


# --- Models ---


class EntryPoint(BaseModel):
    """A fuzzable entry point in the Rust codebase."""

    function: str
    file: str
    line: int
    signature: str
    fuzzable: bool = True


class UnsafeBlock(BaseModel):
    """An unsafe block detected in the codebase."""

    file: str
    line: int
    context: str


class Vulnerability(BaseModel):
    """A known vulnerability from cargo-audit."""

    advisory_id: str
    crate_name: str
    version: str
    title: str
    severity: str


class AnalysisResult(BaseModel):
    """The complete analysis result."""

    crate_name: str
    crate_version: str
    lib_name: str = ""
    entry_points: list[EntryPoint] = []
    unsafe_blocks: list[UnsafeBlock] = []
    vulnerabilities: list[Vulnerability] = []
    summary: dict[str, int] = {}


# --- Analysis Logic ---


def parse_cargo_toml(cargo_path: Path) -> tuple[str, str, str]:
    """Parse Cargo.toml to extract crate name, version, and lib name."""
    import tomllib

    with cargo_path.open("rb") as f:
        data = tomllib.load(f)

    package = data.get("package", {})
    crate_name = package.get("name", "unknown")
    version = package.get("version", "0.0.0")

    lib_section = data.get("lib", {})
    lib_name = lib_section.get("name", crate_name.replace("-", "_"))

    return crate_name, version, lib_name


def find_entry_points(project_path: Path) -> list[EntryPoint]:
    """Find fuzzable entry points in the Rust source."""
    entry_points: list[EntryPoint] = []

    fuzzable_patterns = [
        r"pub\s+fn\s+(\w+)\s*\([^)]*&\[u8\][^)]*\)",
        r"pub\s+fn\s+(\w+)\s*\([^)]*&str[^)]*\)",
        r"pub\s+fn\s+(\w+)\s*\([^)]*impl\s+Read[^)]*\)",
        r"pub\s+fn\s+(\w+)\s*\([^)]*data:\s*&\[u8\][^)]*\)",
        r"pub\s+fn\s+(\w+)\s*\([^)]*input:\s*&\[u8\][^)]*\)",
        r"pub\s+fn\s+(\w+)\s*\([^)]*buf:\s*&\[u8\][^)]*\)",
    ]

    parser_patterns = [
        r"pub\s+fn\s+(parse\w*)\s*\([^)]*\)",
        r"pub\s+fn\s+(decode\w*)\s*\([^)]*\)",
        r"pub\s+fn\s+(deserialize\w*)\s*\([^)]*\)",
        r"pub\s+fn\s+(from_bytes\w*)\s*\([^)]*\)",
        r"pub\s+fn\s+(read\w*)\s*\([^)]*\)",
    ]

    src_path = project_path / "src"
    if not src_path.exists():
        src_path = project_path

    for rust_file in src_path.rglob("*.rs"):
        try:
            content = rust_file.read_text()
            lines = content.split("\n")

            for line_num, line in enumerate(lines, 1):
                for pattern in fuzzable_patterns:
                    match = re.search(pattern, line)
                    if match:
                        entry_points.append(
                            EntryPoint(
                                function=match.group(1),
                                file=str(rust_file.relative_to(project_path)),
                                line=line_num,
                                signature=line.strip(),
                                fuzzable=True,
                            )
                        )

                for pattern in parser_patterns:
                    match = re.search(pattern, line)
                    if match:
                        func_name = match.group(1)
                        if not any(ep.function == func_name for ep in entry_points):
                            entry_points.append(
                                EntryPoint(
                                    function=func_name,
                                    file=str(rust_file.relative_to(project_path)),
                                    line=line_num,
                                    signature=line.strip(),
                                    fuzzable=True,
                                )
                            )
        except Exception:
            continue

    return entry_points


def find_unsafe_blocks(project_path: Path) -> list[UnsafeBlock]:
    """Find unsafe blocks in the Rust source."""
    unsafe_blocks: list[UnsafeBlock] = []

    src_path = project_path / "src"
    if not src_path.exists():
        src_path = project_path

    for rust_file in src_path.rglob("*.rs"):
        try:
            content = rust_file.read_text()
            lines = content.split("\n")

            for line_num, line in enumerate(lines, 1):
                if "unsafe" in line and ("{" in line or "fn" in line):
                    context = "unsafe block"
                    if "unsafe fn" in line:
                        context = "unsafe function"
                    elif "unsafe impl" in line:
                        context = "unsafe impl"
                    elif "*const" in line or "*mut" in line:
                        context = "raw pointer operation"

                    unsafe_blocks.append(
                        UnsafeBlock(
                            file=str(rust_file.relative_to(project_path)),
                            line=line_num,
                            context=context,
                        )
                    )
        except Exception:
            continue

    return unsafe_blocks


async def run_cargo_audit(project_path: Path, timeout: int = 120) -> list[Vulnerability]:
    """Run cargo-audit to find known vulnerabilities."""
    vulnerabilities: list[Vulnerability] = []

    try:
        process = await asyncio.create_subprocess_exec(
            "cargo", "audit", "--json",
            cwd=str(project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, _ = await asyncio.wait_for(
            process.communicate(),
            timeout=float(timeout),
        )

        if stdout:
            audit_data = json.loads(stdout.decode())
            for vuln in audit_data.get("vulnerabilities", {}).get("list", []):
                advisory = vuln.get("advisory", {})
                vulnerabilities.append(
                    Vulnerability(
                        advisory_id=advisory.get("id", "UNKNOWN"),
                        crate_name=vuln.get("package", {}).get("name", "unknown"),
                        version=vuln.get("package", {}).get("version", "0.0.0"),
                        title=advisory.get("title", "Unknown vulnerability"),
                        severity=advisory.get("severity", "unknown"),
                    )
                )
    except (asyncio.TimeoutError, json.JSONDecodeError, FileNotFoundError) as e:
        logger.warning(f"cargo-audit failed: {e}")

    return vulnerabilities


async def analyze_project(
    project_path_str: str,
    run_audit: bool = True,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Perform full static analysis on a Rust project."""
    project_path = Path(project_path_str)

    # Find Cargo.toml
    if project_path.name == "Cargo.toml":
        cargo_path = project_path
        project_path = cargo_path.parent
    else:
        cargo_path = project_path / "Cargo.toml"

    if not cargo_path.exists():
        return {"error": f"Cargo.toml not found at {cargo_path}"}

    logger.info(f"Analyzing Rust project at {project_path}")

    # Parse Cargo.toml
    crate_name, crate_version, lib_name = parse_cargo_toml(cargo_path)
    logger.info(f"Found crate: {crate_name} v{crate_version} (lib: {lib_name})")

    # Find entry points
    entry_points = find_entry_points(project_path)
    logger.info(f"Found {len(entry_points)} fuzzable entry points")

    # Find unsafe blocks
    unsafe_blocks = find_unsafe_blocks(project_path)
    logger.info(f"Found {len(unsafe_blocks)} unsafe blocks")

    # Run cargo-audit
    vulnerabilities: list[Vulnerability] = []
    if run_audit:
        vulnerabilities = await run_cargo_audit(
            project_path,
            timeout=timeout or 120,
        )
        logger.info(f"Found {len(vulnerabilities)} known vulnerabilities")

    analysis = AnalysisResult(
        crate_name=crate_name,
        crate_version=crate_version,
        lib_name=lib_name,
        entry_points=entry_points,
        unsafe_blocks=unsafe_blocks,
        vulnerabilities=vulnerabilities,
        summary={
            "entry_points": len(entry_points),
            "unsafe_blocks": len(unsafe_blocks),
            "vulnerabilities": len(vulnerabilities),
        },
    )

    return analysis.model_dump()


# --- MCP Server ---


app = Server("rust-analyzer-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="rust_analyze",
            description=(
                "Analyze a Rust project to identify fuzzable entry points, unsafe blocks, "
                "and known CVEs via cargo-audit. Returns structured analysis with function "
                "signatures, file locations, and vulnerability details. "
                "Use this as the first step in a Rust fuzzing pipeline."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Rust project directory containing Cargo.toml",
                    },
                    "run_audit": {
                        "type": "boolean",
                        "description": "Run cargo-audit for CVE detection",
                        "default": True,
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Analysis timeout in seconds",
                        "default": 300,
                    },
                },
                "required": ["project_path"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "rust_analyze":
            project_path = arguments["project_path"]

            if not Path(project_path).exists():
                return [TextContent(type="text", text=f"Project not found: {project_path}")]

            result = await analyze_project(
                project_path_str=project_path,
                run_audit=arguments.get("run_audit", True),
                timeout=arguments.get("timeout"),
            )

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        logger.exception(f"Error in {name}: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Start the MCP server."""
    logger.info("Starting Rust Analyzer MCP Server")

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
