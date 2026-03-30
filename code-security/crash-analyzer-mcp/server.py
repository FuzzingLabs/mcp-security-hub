#!/usr/bin/env python3
"""Crash Analyzer MCP Server.

Analyzes crashes from cargo-fuzz: reproduces them for stack traces,
classifies crash types, determines severity, and deduplicates by signature.

Tools:
    - crash_analyze: Analyze and triage fuzzer crash inputs
"""

import asyncio
import hashlib
import json
import logging
import os
import re
from enum import Enum
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
logger = logging.getLogger("crash-analyzer-mcp")


class Settings(BaseSettings):
    """Server configuration."""

    reproduce_timeout: int = Field(default=30, alias="CRASH_ANALYZER_TIMEOUT")

    class Config:
        env_prefix = "CRASH_ANALYZER_"


settings = Settings()


# --- Models ---


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class CrashAnalysis(BaseModel):
    target: str
    input_file: str
    input_hash: str
    input_size: int = 0
    crash_type: str = "unknown"
    severity: Severity = Severity.UNKNOWN
    stack_trace: str = ""
    is_duplicate: bool = False
    signature: str = ""


class AnalysisReport(BaseModel):
    total_crashes: int = 0
    unique_crashes: int = 0
    duplicate_crashes: int = 0
    severity_summary: dict[str, int] = Field(default_factory=dict)
    unique_analyses: list[CrashAnalysis] = Field(default_factory=list)
    duplicate_analyses: list[CrashAnalysis] = Field(default_factory=list)


# --- Analysis Logic ---


HIGH_SEVERITY = {"heap-buffer-overflow", "stack-buffer-overflow", "use-after-free", "double-free"}
MEDIUM_SEVERITY = {"null-pointer-dereference", "out-of-memory", "integer-overflow"}
LOW_SEVERITY = {"panic", "assertion-failure", "timeout"}


def classify_crash_type(output: str) -> str:
    """Classify crash type from fuzzer output."""
    checks = [
        ("heap-buffer-overflow", "heap-buffer-overflow"),
        ("stack-buffer-overflow", "stack-buffer-overflow"),
        ("heap-use-after-free", "use-after-free"),
        ("double-free", "double-free"),
        ("null", "null-pointer-dereference"),  # paired with deref check below
        ("panic", "panic"),
        ("assertion", "assertion-failure"),
        ("timeout", "timeout"),
        ("out of memory", "out-of-memory"),
        ("oom", "out-of-memory"),
    ]
    lower = output.lower()
    for pattern, crash_type in checks:
        if pattern in lower:
            # null needs deref alongside
            if pattern == "null" and "deref" not in lower:
                continue
            return crash_type
    return "unknown"


def determine_severity(crash_type: str) -> Severity:
    """Determine severity from crash type."""
    if crash_type in HIGH_SEVERITY:
        return Severity.HIGH
    elif crash_type in MEDIUM_SEVERITY:
        return Severity.MEDIUM
    elif crash_type in LOW_SEVERITY:
        return Severity.LOW
    return Severity.UNKNOWN


def extract_stack_trace(output: str, max_lines: int = 50) -> str:
    """Extract stack trace from fuzzer output."""
    lines = output.splitlines()
    stack_lines = []
    in_stack = False
    for line in lines:
        if "SUMMARY:" in line or "ERROR:" in line:
            in_stack = True
        if in_stack:
            stack_lines.append(line)
            if len(stack_lines) >= max_lines:
                break
    return "\n".join(stack_lines)


def create_signature(target: str, crash_type: str, stack_trace: str) -> str:
    """Create dedup signature from crash info."""
    parts = [target, crash_type]
    func_pattern = re.compile(r"in (\S+)")
    funcs = func_pattern.findall(stack_trace)
    seen: set[str] = set()
    for func in funcs:
        if func not in seen and not func.startswith("std::"):
            parts.append(func)
            seen.add(func)
            if len(seen) >= 3:
                break
    return "|".join(parts)


async def reproduce_crash(
    fuzz_project: Path, target: str, crash_file: Path, timeout: int = 30,
) -> tuple[str, str]:
    """Reproduce a crash to get stack trace and crash type."""
    try:
        env = os.environ.copy()
        env["RUST_BACKTRACE"] = "1"

        proc = await asyncio.create_subprocess_exec(
            "cargo", "+nightly", "fuzz", "run", target,
            str(crash_file), "--", "-runs=1",
            cwd=str(fuzz_project),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=float(timeout),
        )

        output = ""
        if stdout_bytes:
            output += stdout_bytes.decode(errors="replace")
        if stderr_bytes:
            output += stderr_bytes.decode(errors="replace")

        crash_type = classify_crash_type(output)
        stack_trace = extract_stack_trace(output)

        return stack_trace, crash_type

    except asyncio.TimeoutError:
        return "", "timeout"
    except Exception as e:
        logger.warning(f"Failed to reproduce crash: {e}")
        return "", "unknown"


async def analyze_crashes(
    project_path_str: str,
    crashes_path_str: str | None = None,
    reproduce: bool = True,
    reproduce_timeout: int = 30,
    max_crashes: int = 0,
) -> dict[str, Any]:
    """Analyze crashes from a fuzzing campaign."""
    project_path = Path(project_path_str)

    if not project_path.exists():
        return {"error": f"Project not found: {project_path}"}

    # Find crashes directory
    if crashes_path_str:
        crashes_path = Path(crashes_path_str)
    else:
        # Try standard locations (including FuzzForge output mount)
        candidates = [
            Path("/app/output/crashes"),
            project_path / "crashes",
            project_path / "fuzz" / "artifacts",
            project_path / "artifacts",
        ]
        crashes_path = None
        for c in candidates:
            if c.is_dir():
                crashes_path = c
                break

        if crashes_path is None:
            return {"error": "No crashes directory found. Specify crashes_path explicitly."}

    if not crashes_path.exists():
        return {"error": f"Crashes path not found: {crashes_path}"}

    # Find fuzz project for reproduction
    fuzz_project: Path | None = None
    if reproduce:
        fuzz_dir = project_path / "fuzz"
        if fuzz_dir.is_dir() and (fuzz_dir / "Cargo.toml").exists():
            fuzz_project = project_path
        elif (project_path / "Cargo.toml").exists() and (project_path / "fuzz_targets").is_dir():
            fuzz_project = project_path

    # Collect all crash files
    analyses: list[CrashAnalysis] = []

    # If crashes_path has subdirectories (per-target), iterate them
    has_subdirs = any(p.is_dir() for p in crashes_path.iterdir())

    crash_count = 0
    if has_subdirs:
        for target_dir in crashes_path.iterdir():
            if not target_dir.is_dir():
                continue
            target = target_dir.name
            for crash_file in target_dir.glob("crash-*"):
                if not crash_file.is_file():
                    continue
                if max_crashes > 0 and crash_count >= max_crashes:
                    break
                analysis = await _analyze_single_crash(
                    target, crash_file, fuzz_project, reproduce, reproduce_timeout,
                )
                analyses.append(analysis)
                crash_count += 1
            if max_crashes > 0 and crash_count >= max_crashes:
                break
    else:
        # Flat directory of crash files
        for crash_file in crashes_path.glob("crash-*"):
            if not crash_file.is_file():
                continue
            if max_crashes > 0 and crash_count >= max_crashes:
                break
            analysis = await _analyze_single_crash(
                "unknown", crash_file, fuzz_project, reproduce, reproduce_timeout,
            )
            analyses.append(analysis)
            crash_count += 1

    # Deduplicate
    seen_sigs: set[str] = set()
    for analysis in analyses:
        sig = create_signature(analysis.target, analysis.crash_type, analysis.stack_trace)
        analysis.signature = sig
        if sig in seen_sigs:
            analysis.is_duplicate = True
        else:
            seen_sigs.add(sig)

    unique = [a for a in analyses if not a.is_duplicate]
    duplicates = [a for a in analyses if a.is_duplicate]

    report = AnalysisReport(
        total_crashes=len(analyses),
        unique_crashes=len(unique),
        duplicate_crashes=len(duplicates),
        severity_summary={
            "high": sum(1 for a in unique if a.severity == Severity.HIGH),
            "medium": sum(1 for a in unique if a.severity == Severity.MEDIUM),
            "low": sum(1 for a in unique if a.severity == Severity.LOW),
            "unknown": sum(1 for a in unique if a.severity == Severity.UNKNOWN),
        },
        unique_analyses=unique,
        duplicate_analyses=duplicates,
    )

    return report.model_dump()


async def _analyze_single_crash(
    target: str, crash_file: Path,
    fuzz_project: Path | None, reproduce: bool, timeout: int,
) -> CrashAnalysis:
    """Analyze a single crash file."""
    crash_data = crash_file.read_bytes()
    input_hash = hashlib.sha256(crash_data).hexdigest()[:16]

    stack_trace = ""
    crash_type = "unknown"

    if reproduce and fuzz_project:
        stack_trace, crash_type = await reproduce_crash(
            fuzz_project, target, crash_file, timeout,
        )

    severity = determine_severity(crash_type)

    return CrashAnalysis(
        target=target,
        input_file=str(crash_file),
        input_hash=input_hash,
        input_size=len(crash_data),
        crash_type=crash_type,
        severity=severity,
        stack_trace=stack_trace,
    )


# --- MCP Server ---


app = Server("crash-analyzer-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="crash_analyze",
            description=(
                "Analyze crashes from a Rust fuzzing campaign. Reproduces each crash "
                "to extract stack traces, classifies crash types (heap-buffer-overflow, "
                "use-after-free, panic, etc.), determines severity (high/medium/low), "
                "and deduplicates by call-stack signature. "
                "Requires the original project for crash reproduction."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Rust project directory containing Cargo.toml",
                    },
                    "crashes_path": {
                        "type": "string",
                        "description": "Path to crashes directory (default: auto-detect from project)",
                    },
                    "reproduce": {
                        "type": "boolean",
                        "description": "Whether to reproduce crashes for stack traces",
                        "default": True,
                    },
                    "reproduce_timeout": {
                        "type": "integer",
                        "description": "Timeout per crash reproduction in seconds",
                        "default": 30,
                    },
                    "max_crashes": {
                        "type": "integer",
                        "description": "Maximum number of crashes to analyze (0 = all)",
                        "default": 0,
                    },
                },
                "required": ["project_path"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        if name == "crash_analyze":
            project_path = arguments["project_path"]

            if not Path(project_path).exists():
                return [TextContent(type="text", text=f"Project not found: {project_path}")]

            result = await analyze_crashes(
                project_path_str=project_path,
                crashes_path_str=arguments.get("crashes_path"),
                reproduce=arguments.get("reproduce", True),
                reproduce_timeout=arguments.get("reproduce_timeout", 30),
                max_crashes=arguments.get("max_crashes", 0),
            )

            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        logger.exception(f"Error in {name}: {e}")
        return [TextContent(type="text", text=f"Error: {e!s}")]


async def main():
    logger.info("Starting Crash Analyzer MCP Server")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
