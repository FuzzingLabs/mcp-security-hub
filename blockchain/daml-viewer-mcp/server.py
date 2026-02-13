#!/usr/bin/env python3
"""
daml-viewer MCP Server

Model Context Protocol server for generating DAML access-control tables via
the `daml-viewer` CLI.
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LOG_LEVEL = os.environ.get("DAML_VIEWER_LOG_LEVEL", "WARNING").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.WARNING),
    stream=sys.stderr,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("daml-viewer-mcp")


class Settings(BaseSettings):
    """Server configuration from environment variables."""

    model_config = SettingsConfigDict(env_prefix="DAML_VIEWER_")

    output_dir: str = Field(default="/app/output", alias="DAML_VIEWER_OUTPUT_DIR")
    upload_dir: str = Field(default="/app/uploads", alias="DAML_VIEWER_UPLOAD_DIR")
    default_timeout: int = Field(default=120, alias="DAML_VIEWER_TIMEOUT")
    max_concurrent: int = Field(default=3, alias="DAML_VIEWER_MAX_CONCURRENT")
    max_file_size: int = Field(default=104857600, alias="DAML_VIEWER_MAX_FILE_SIZE")  # 100MB
    allow_any_path: bool = Field(default=False, alias="DAML_VIEWER_ALLOW_ANY_PATH")
    daml_viewer_bin: str = Field(default="daml-viewer", alias="DAML_VIEWER_BIN")
    max_text_output: int = Field(default=20000, alias="DAML_VIEWER_MAX_TEXT_OUTPUT")
    max_table_preview: int = Field(default=20000, alias="DAML_VIEWER_MAX_TABLE_PREVIEW")


settings = Settings()


class RunResult(BaseModel):
    run_id: str
    command: list[str]
    input_path: str
    output_path: str
    cleared: bool
    started_at: datetime
    completed_at: datetime | None = None
    status: str = "running"  # running|completed|failed|timeout|error
    stdout: str | None = None
    stderr: str | None = None
    error: str | None = None


run_results: dict[str, RunResult] = {}
active_runs: set[str] = set()


def _resolve(path_str: str) -> Path:
    return Path(path_str).expanduser().resolve(strict=False)


def _is_allowed_path(p: Path) -> bool:
    if settings.allow_any_path:
        return True

    upload_root = _resolve(settings.upload_dir)
    output_root = _resolve(settings.output_dir)

    try:
        p.relative_to(upload_root)
        return True
    except ValueError:
        pass

    try:
        p.relative_to(output_root)
        return True
    except ValueError:
        pass

    return False


def _validate_existing_path(
    path_str: str,
    *,
    allow_files: bool = True,
    allow_dirs: bool = True,
) -> tuple[Path | None, str | None]:
    p = _resolve(path_str)

    if not _is_allowed_path(p):
        return None, (
            f"Path not allowed: {p}. "
            f"Allowed roots: {settings.upload_dir}, {settings.output_dir}. "
            "Set DAML_VIEWER_ALLOW_ANY_PATH=1 to disable this restriction."
        )

    if not p.exists():
        return None, f"Path not found: {p}"

    if p.is_file() and not allow_files:
        return None, f"Expected a directory, got file: {p}"

    if p.is_dir() and not allow_dirs:
        return None, f"Expected a file, got directory: {p}"

    if p.is_file():
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        if size > settings.max_file_size:
            return None, f"File too large ({size} bytes). Max: {settings.max_file_size} bytes."

    return p, None


def _validate_output_path(path_str: str | None, run_dir: Path) -> tuple[Path | None, str | None]:
    if not path_str:
        return run_dir / "daml_table.md", None

    output_path = _resolve(path_str)
    if output_path.exists() and output_path.is_dir():
        if not _is_allowed_path(output_path):
            return None, (
                f"Output path not allowed: {output_path}. "
                f"Allowed roots: {settings.upload_dir}, {settings.output_dir}."
            )
        return output_path / "daml_table.md", None

    parent = output_path.parent
    if not _is_allowed_path(parent):
        return None, (
            f"Output path not allowed: {output_path}. "
            f"Allowed roots: {settings.upload_dir}, {settings.output_dir}."
        )

    return output_path, None


async def _run_cmd(cmd: list[str], *, cwd: Path, timeout: int | None) -> tuple[int, str, str]:
    env = os.environ.copy()
    env.setdefault("TERM", "dumb")

    logger.debug("Running command: %s (cwd=%s)", " ".join(cmd), cwd)
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd),
        env=env,
    )

    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            process.communicate(),
            timeout=float(timeout or settings.default_timeout),
        )
    except asyncio.TimeoutError:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        raise

    stdout = (stdout_b or b"").decode(errors="replace")
    stderr = (stderr_b or b"").decode(errors="replace")
    return int(process.returncode or 0), stdout, stderr


def _truncate(s: str | None, max_chars: int) -> str | None:
    if s is None:
        return None
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + "\n...(truncated)...\n"


def _read_text_preview(path: Path, max_chars: int) -> str:
    try:
        data = path.read_text(errors="replace")
    except Exception as exc:
        return f"(error reading {path}: {exc})"

    if len(data) <= max_chars:
        return data
    return data[:max_chars] + "\n...(truncated)...\n"


def _new_run(command: list[str], input_path: Path, output_path: Path, cleared: bool) -> RunResult:
    run_id = str(uuid.uuid4())[:8]
    result = RunResult(
        run_id=run_id,
        command=command,
        input_path=str(input_path),
        output_path=str(output_path),
        cleared=cleared,
        started_at=datetime.now(),
    )
    run_results[run_id] = result
    return result


def _format_run_summary(
    result: RunResult,
    *,
    include_stdout: bool = False,
    include_stderr: bool = False,
    include_table_preview: bool = True,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "run_id": result.run_id,
        "status": result.status,
        "command": result.command,
        "input_path": result.input_path,
        "output_path": result.output_path,
        "cleared": result.cleared,
        "started_at": result.started_at.isoformat(),
        "completed_at": result.completed_at.isoformat() if result.completed_at else None,
        "error": result.error,
    }

    if include_stdout:
        out["stdout"] = result.stdout
    if include_stderr:
        out["stderr"] = result.stderr

    if include_table_preview:
        output_path = Path(result.output_path)
        if output_path.exists() and output_path.is_file():
            out["table_preview"] = _read_text_preview(output_path, settings.max_table_preview)

    return out


async def _run_daml_viewer(
    *,
    input_path: Path,
    output_path: Path,
    cleared: bool,
    timeout: int | None,
    run_dir: Path,
) -> RunResult:
    if len(active_runs) >= settings.max_concurrent:
        raise RuntimeError(f"Maximum concurrent runs ({settings.max_concurrent}) reached.")

    cmd = [settings.daml_viewer_bin, str(input_path), "--output", str(output_path)]
    if cleared:
        cmd.append("--cleared")

    result = _new_run(cmd, input_path, output_path, cleared)
    active_runs.add(result.run_id)

    try:
        rc, stdout, stderr = await _run_cmd(cmd, cwd=run_dir, timeout=timeout)

        result.completed_at = datetime.now()
        result.stdout = _truncate(stdout, settings.max_text_output)
        result.stderr = _truncate(stderr, settings.max_text_output)

        if rc == 0:
            result.status = "completed"
        else:
            result.status = "failed"
            if stderr.strip():
                result.error = stderr.strip()[:2000]
            else:
                result.error = f"Command failed with exit code {rc}"

    except asyncio.TimeoutError:
        result.completed_at = datetime.now()
        result.status = "timeout"
        result.error = f"Timed out after {timeout or settings.default_timeout} seconds"

    except Exception as exc:
        result.completed_at = datetime.now()
        result.status = "error"
        result.error = str(exc)

    finally:
        active_runs.discard(result.run_id)
        run_results[result.run_id] = result

    return result


app = Server("daml-viewer-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="damlviewer_generate_table",
            description="Generate a DAML access-control markdown table from a project directory or a single `.daml` file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to a DAML project root (directory) or a single `.daml` file.",
                    },
                    "output": {
                        "type": "string",
                        "description": "Optional output path for the markdown table. Defaults to an MCP run directory under /app/output.",
                    },
                    "cleared": {
                        "type": "boolean",
                        "default": False,
                        "description": "Clear placeholder cells `(N/A)` and `(none)` from output.",
                    },
                    "timeout": {"type": "integer", "default": 120, "description": "Timeout in seconds."},
                    "include_stdout": {"type": "boolean", "default": False},
                    "include_stderr": {"type": "boolean", "default": False},
                    "include_table_preview": {"type": "boolean", "default": True},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="get_run_results",
            description="Retrieve results from a previous run by run ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string", "description": "Run ID returned by a previous tool call."},
                    "include_stdout": {"type": "boolean", "default": False},
                    "include_stderr": {"type": "boolean", "default": False},
                    "include_table_preview": {"type": "boolean", "default": True},
                },
                "required": ["run_id"],
            },
        ),
        Tool(
            name="list_runs",
            description="List completed DAML viewer runs (most recent first).",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by status (completed|failed|timeout|error)."},
                    "limit": {"type": "integer", "default": 50, "description": "Maximum number of runs to return."},
                },
            },
        ),
        Tool(
            name="list_active_runs",
            description="List currently running DAML viewer jobs.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        output_root = _resolve(settings.output_dir)
        output_root.mkdir(parents=True, exist_ok=True)

        if name == "damlviewer_generate_table":
            input_path, err = _validate_existing_path(arguments["path"], allow_files=True, allow_dirs=True)
            if err:
                return [TextContent(type="text", text=err)]

            run_dir = output_root / f"table_{str(uuid.uuid4())[:8]}"
            run_dir.mkdir(parents=True, exist_ok=True)

            output_path, err = _validate_output_path(arguments.get("output"), run_dir)
            if err:
                return [TextContent(type="text", text=err)]

            cleared = bool(arguments.get("cleared", False))
            timeout = arguments.get("timeout")

            result = await _run_daml_viewer(
                input_path=input_path,
                output_path=output_path,
                cleared=cleared,
                timeout=timeout,
                run_dir=run_dir,
            )
            summary = _format_run_summary(
                result,
                include_stdout=bool(arguments.get("include_stdout", False)),
                include_stderr=bool(arguments.get("include_stderr", False)),
                include_table_preview=bool(arguments.get("include_table_preview", True)),
            )
            return [TextContent(type="text", text=json.dumps(summary, indent=2))]

        if name == "get_run_results":
            run_id = arguments["run_id"]
            result = run_results.get(run_id)
            if not result:
                return [TextContent(type="text", text=f"Run '{run_id}' not found")]

            summary = _format_run_summary(
                result,
                include_stdout=bool(arguments.get("include_stdout", False)),
                include_stderr=bool(arguments.get("include_stderr", False)),
                include_table_preview=bool(arguments.get("include_table_preview", True)),
            )
            return [TextContent(type="text", text=json.dumps(summary, indent=2))]

        if name == "list_runs":
            limit = int(arguments.get("limit", 50))
            filter_status = arguments.get("status")

            items = list(run_results.values())
            items.sort(key=lambda run: run.started_at, reverse=True)

            runs: list[dict[str, Any]] = []
            for run in items:
                if run.status == "running":
                    continue
                if filter_status and run.status != filter_status:
                    continue
                runs.append(_format_run_summary(run, include_table_preview=False))
                if len(runs) >= limit:
                    break

            return [TextContent(type="text", text=json.dumps({"runs": runs, "count": len(runs)}, indent=2))]

        if name == "list_active_runs":
            active = []
            for run_id in sorted(active_runs):
                run = run_results.get(run_id)
                if not run:
                    continue
                active.append(
                    {
                        "run_id": run.run_id,
                        "started_at": run.started_at.isoformat(),
                        "command": run.command,
                        "input_path": run.input_path,
                    }
                )

            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "active_runs": active,
                            "count": len(active),
                            "max_concurrent": settings.max_concurrent,
                        },
                        indent=2,
                    ),
                )
            ]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as exc:
        logger.exception("Error executing tool %s: %s", name, exc)
        return [TextContent(type="text", text=f"Error: {exc}")]


@app.list_resources()
async def list_resources() -> list[Resource]:
    resources: list[Resource] = []
    for run_id, result in run_results.items():
        if result.status == "running":
            continue
        resources.append(
            Resource(
                uri=f"damlviewer://runs/{run_id}",
                name=f"DAML Viewer Run ({result.status})",
                description=f"Command: {' '.join(result.command)}",
                mimeType="application/json",
            )
        )
    return resources


@app.read_resource()
async def read_resource(uri: str) -> str:
    if uri.startswith("damlviewer://runs/"):
        run_id = uri.replace("damlviewer://runs/", "")
        result = run_results.get(run_id)
        if result:
            return json.dumps(
                _format_run_summary(
                    result,
                    include_stdout=True,
                    include_stderr=True,
                    include_table_preview=True,
                ),
                indent=2,
            )
    return json.dumps({"error": "Resource not found"})


async def main() -> None:
    logger.info("Starting daml-viewer MCP Server (stdio)")
    logger.info("Output directory: %s", settings.output_dir)
    logger.info("Upload directory: %s", settings.upload_dir)
    logger.info("Max concurrent: %s", settings.max_concurrent)
    logger.info("Path policy: %s", "allow-any" if settings.allow_any_path else "restricted")

    Path(settings.output_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
