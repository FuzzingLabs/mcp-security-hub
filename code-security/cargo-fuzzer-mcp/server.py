#!/usr/bin/env python3
"""Cargo Fuzzer MCP Server.

Runs cargo-fuzz (libFuzzer) on Rust fuzz targets for a configurable duration,
collects crashes and execution statistics.

Tools:
    - cargo_fuzz_run:    Run cargo-fuzz on one or all targets (blocking, fixed duration)
    - cargo_fuzz_start:  Start continuous fuzzing in background (non-blocking)
    - cargo_fuzz_status: Get live metrics from a running fuzzing session
    - cargo_fuzz_stop:   Stop a running fuzzing session and collect final results
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import time
from datetime import datetime, timezone
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
logger = logging.getLogger("cargo-fuzzer-mcp")


class Settings(BaseSettings):
    """Server configuration."""

    default_duration: int = Field(default=60, alias="CARGO_FUZZER_DURATION")

    class Config:
        env_prefix = "CARGO_FUZZER_"


settings = Settings()

# --- Continuous session tracking ---

# Active fuzzing sessions keyed by session_id
_sessions: dict[str, "ContinuousSession"] = {}


class ContinuousSession:
    """Tracks a running continuous fuzzing session."""

    def __init__(
        self,
        session_id: str,
        workspace: Path,
        targets: list[str],
        jobs: int,
    ) -> None:
        self.session_id = session_id
        self.workspace = workspace
        self.targets = targets
        self.jobs = jobs
        self.started_at = datetime.now(tz=timezone.utc)
        self.status = "starting"
        self.process: asyncio.subprocess.Process | None = None
        self.task: asyncio.Task[None] | None = None

        # Live metrics (updated by the background reader)
        self.current_target: str = ""
        self.current_round: int = 0
        self.total_executions: int = 0
        self._round_executions: int = 0  # accumulates per-round, flushed at round end
        self.coverage_edges: int = 0
        self.corpus_size: int = 0
        self.crash_files: list[dict[str, Any]] = []
        self.output_lines: list[str] = []  # last N lines of output
        self._max_output_lines: int = 100

    @property
    def elapsed_seconds(self) -> int:
        return int((datetime.now(tz=timezone.utc) - self.started_at).total_seconds())

    @property
    def elapsed_human(self) -> str:
        s = self.elapsed_seconds
        if s < 60:
            return f"{s}s"
        if s < 3600:
            return f"{s // 60}m {s % 60}s"
        return f"{s // 3600}h {(s % 3600) // 60}m {s % 60}s"

    def append_output(self, line: str) -> None:
        self.output_lines.append(line)
        if len(self.output_lines) > self._max_output_lines:
            self.output_lines = self.output_lines[-self._max_output_lines:]

    def update_from_line(self, line: str) -> None:
        """Parse a libFuzzer output line and update live metrics.

        In fork mode (-fork=1), per-job lines show cov/corp/exec_s as 0.
        Real stats come from:
        - ``#N`` job counter → tracks round-level progress
        - ``stat::number_of_executed_units: N`` → actual fuzzer executions
        - ``stat::average_exec_per_sec: N`` → real throughput
        - ``MERGE-OUTER: ... new features`` → corpus growth
        """
        self.append_output(line)

        # Fork-mode stat lines (printed with -print_final_stats=1)
        stat_match = re.match(r"stat::([\w_]+):\s*(\d+)", line)
        if stat_match:
            key, val = stat_match.group(1), int(stat_match.group(2))
            if key == "number_of_executed_units":
                self._round_executions = max(self._round_executions, val)
            return

        # Fork-mode job counter: "#N: cov: ... job: N"
        job_match = re.search(r"#(\d+).*job:\s*(\d+)", line)
        if job_match:
            job_num = int(job_match.group(1))
            self._round_executions = max(self._round_executions, job_num)
            return

        # Standard (non-fork) libFuzzer status line: "#N ... cov: X ... corp: Y ... exec/s: Z"
        exec_match = re.search(r"#(\d+)", line)
        if exec_match and "job:" not in line:
            self._round_executions = max(self._round_executions, int(exec_match.group(1)))

        cov_match = re.search(r"cov:\s*(\d+)", line)
        if cov_match and "job:" not in line:
            val = int(cov_match.group(1))
            if val > 0:
                self.coverage_edges = max(self.coverage_edges, val)

        corp_match = re.search(r"corp:\s*(\d+)", line)
        if corp_match and "job:" not in line:
            val = int(corp_match.group(1))
            if val > 0:
                self.corpus_size = max(self.corpus_size, val)

        # MERGE-OUTER summary: "MERGE-OUTER: N files, M in the initial corpus, K new files (J new features)"
        merge_match = re.search(r"MERGE-OUTER:\s*(\d+)\s+files", line)
        if merge_match:
            self.corpus_size = max(self.corpus_size, int(merge_match.group(1)))

    def flush_round(self) -> None:
        """Accumulate round executions into the total and reset round counter."""
        self.total_executions += self._round_executions
        self._round_executions = 0

    @property
    def executions_per_second(self) -> int:
        """Calculate average exec/s from total executions and elapsed time."""
        elapsed = self.elapsed_seconds
        current_total = self.total_executions + self._round_executions
        return int(current_total / elapsed) if elapsed > 0 else 0

    @property
    def total_crashes(self) -> int:
        """Crash count derived from deduplicated crash files."""
        return len(self.crash_files)

    def to_status_dict(self) -> dict[str, Any]:
        current_total = self.total_executions + self._round_executions
        return {
            "session_id": self.session_id,
            "status": self.status,
            "targets": self.targets,
            "current_target": self.current_target,
            "current_round": self.current_round,
            "started_at": self.started_at.isoformat(),
            "elapsed_seconds": self.elapsed_seconds,
            "elapsed_human": self.elapsed_human,
            "metrics": {
                "total_executions": current_total,
                "executions_per_second": self.executions_per_second,
                "coverage_edges": self.coverage_edges,
                "corpus_size": self.corpus_size,
                "total_crashes": self.total_crashes,
            },
            "crash_files": self.crash_files,
            "recent_output": self.output_lines[-20:],
        }


# --- Models ---


class FuzzingStats(BaseModel):
    total_executions: int = 0
    executions_per_second: int = 0
    coverage_edges: int = 0
    corpus_size: int = 0
    error: str = ""


class CrashInfo(BaseModel):
    file_path: str
    input_hash: str
    input_size: int = 0


class TargetResult(BaseModel):
    target: str
    crashes: list[CrashInfo] = Field(default_factory=list)
    stats: FuzzingStats = Field(default_factory=FuzzingStats)


class FuzzingReport(BaseModel):
    targets_fuzzed: int = 0
    total_crashes: int = 0
    total_executions: int = 0
    duration_seconds: int = 0
    results: list[TargetResult] = Field(default_factory=list)


# --- Core Fuzzing Logic ---


def find_fuzz_targets(fuzz_project: Path) -> list[str]:
    """Find fuzz targets in project."""
    targets_dir = fuzz_project / "fuzz" / "fuzz_targets"
    if not targets_dir.is_dir():
        # Maybe fuzz_project IS the fuzz/ dir
        targets_dir = fuzz_project / "fuzz_targets"
        if not targets_dir.is_dir():
            return []
    return [f.stem for f in targets_dir.glob("*.rs")]


def setup_workspace(project_path: Path) -> Path:
    """Copy project to writable workspace."""
    workspace = Path("/tmp/fuzz-work") / project_path.name
    if workspace.exists():
        shutil.rmtree(workspace)
    shutil.copytree(project_path, workspace)
    return workspace


def parse_fuzzer_output(output: str) -> FuzzingStats:
    """Parse libFuzzer statistics from output."""
    stats = FuzzingStats()

    exec_match = re.search(r"#(\d+)", output)
    if exec_match:
        stats.total_executions = int(exec_match.group(1))

    cov_match = re.search(r"cov:\s*(\d+)", output)
    if cov_match:
        stats.coverage_edges = int(cov_match.group(1))

    corp_match = re.search(r"corp:\s*(\d+)", output)
    if corp_match:
        stats.corpus_size = int(corp_match.group(1))

    exec_s_match = re.search(r"exec/s:\s*(\d+)", output)
    if exec_s_match:
        stats.executions_per_second = int(exec_s_match.group(1))

    return stats


def collect_crashes(fuzz_project: Path, target: str, output_dir: Path) -> list[CrashInfo]:
    """Collect crash files from fuzzing artifacts."""
    crashes: list[CrashInfo] = []
    seen: set[str] = set()

    search_dirs = [
        fuzz_project / "artifacts" / target,
        fuzz_project / "artifacts",
        fuzz_project / "fuzz" / "artifacts" / target,
        fuzz_project / "fuzz" / "artifacts",
    ]

    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue
        for crash_file in search_dir.rglob("crash-*"):
            if not crash_file.is_file() or crash_file.name in seen:
                continue
            seen.add(crash_file.name)

            dest_dir = output_dir / target
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / crash_file.name
            shutil.copy2(crash_file, dest)

            crash_data = crash_file.read_bytes()
            crashes.append(CrashInfo(
                file_path=str(dest),
                input_hash=crash_file.name,
                input_size=len(crash_data),
            ))

    return crashes


async def fuzz_target(
    project_path: Path, target: str, duration: int, crashes_dir: Path,
    jobs: int = 1,
) -> TargetResult:
    """Fuzz a single target for the given duration."""
    logger.info(f"Fuzzing target: {target} for {duration}s")

    # Ensure corpus dir exists
    corpus_dir = project_path / "fuzz" / "corpus" / target
    if not corpus_dir.exists():
        corpus_dir = project_path / "corpus" / target
    corpus_dir.mkdir(parents=True, exist_ok=True)

    cmd = ["cargo", "+nightly", "fuzz", "run", target, "--"]
    if duration > 0:
        cmd.append(f"-max_total_time={duration}")
    cmd.extend(["-fork=1", "-ignore_crashes=1", "-print_final_stats=1"])
    if jobs > 1:
        cmd.append(f"-jobs={jobs}")

    env = os.environ.copy()
    env["CARGO_INCREMENTAL"] = "0"

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )

        stdout_bytes, _ = await asyncio.wait_for(
            proc.communicate(),
            timeout=float(duration + 60),
        )
        output = stdout_bytes.decode(errors="replace") if stdout_bytes else ""

        stats = parse_fuzzer_output(output)
        crashes = collect_crashes(project_path, target, crashes_dir)

        logger.info(f"Target {target}: {stats.total_executions} execs, {len(crashes)} crashes")
        return TargetResult(target=target, crashes=crashes, stats=stats)

    except asyncio.TimeoutError:
        logger.warning(f"Fuzzer timeout for target {target}")
        crashes = collect_crashes(project_path, target, crashes_dir)
        stats = FuzzingStats(error="timeout")
        return TargetResult(target=target, crashes=crashes, stats=stats)

    except FileNotFoundError:
        stats = FuzzingStats(error="cargo-fuzz not installed")
        return TargetResult(target=target, stats=stats)

    except Exception as e:
        logger.exception(f"Fuzzing error for {target}: {e}")
        stats = FuzzingStats(error=str(e))
        return TargetResult(target=target, stats=stats)


async def run_fuzzing(
    project_path_str: str,
    duration: int = 60,
    targets: list[str] | None = None,
    jobs: int = 1,
) -> dict[str, Any]:
    """Run cargo-fuzz on project targets."""
    project_path = Path(project_path_str)

    if not (project_path / "Cargo.toml").exists():
        return {"error": f"No Cargo.toml found at {project_path}"}

    # Copy to writable workspace
    workspace = setup_workspace(project_path)

    available_targets = find_fuzz_targets(workspace)
    if not available_targets:
        return {"error": "No fuzz targets found in fuzz/fuzz_targets/"}

    # Filter targets if specified
    if targets:
        selected = [t for t in available_targets if t in targets]
        if not selected:
            return {
                "error": f"None of the requested targets found. Available: {available_targets}"
            }
        available_targets = selected

    duration_per_target = duration // max(len(available_targets), 1)
    crashes_dir = Path("/app/output/crashes") if Path("/app/output").exists() else Path("/tmp/fuzz-crashes")
    crashes_dir.mkdir(parents=True, exist_ok=True)

    results: list[TargetResult] = []
    for target in available_targets:
        result = await fuzz_target(workspace, target, duration_per_target, crashes_dir, jobs)
        results.append(result)

    total_crashes = sum(len(r.crashes) for r in results)
    total_execs = sum(r.stats.total_executions for r in results)

    report = FuzzingReport(
        targets_fuzzed=len(results),
        total_crashes=total_crashes,
        total_executions=total_execs,
        duration_seconds=duration,
        results=results,
    )

    return report.model_dump()


# --- Continuous Fuzzing Logic ---


async def _fuzz_target_continuous(
    session: ContinuousSession,
    target: str,
    duration_per_round: int,
) -> None:
    """Fuzz a single target for one round, updating session metrics live."""
    session.current_target = target

    corpus_dir = session.workspace / "fuzz" / "corpus" / target
    if not corpus_dir.exists():
        corpus_dir = session.workspace / "corpus" / target
    corpus_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "cargo", "+nightly", "fuzz", "run", target, "--",
        f"-max_total_time={duration_per_round}",
        "-fork=1", "-ignore_crashes=1", "-print_final_stats=1",
    ]
    if session.jobs > 1:
        cmd.append(f"-jobs={session.jobs}")

    env = os.environ.copy()
    env["CARGO_INCREMENTAL"] = "0"

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(session.workspace),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
    )
    session.process = proc

    # Stream output line-by-line for live metrics
    assert proc.stdout is not None
    while True:
        line_bytes = await proc.stdout.readline()
        if not line_bytes:
            break
        line = line_bytes.decode(errors="replace").rstrip()
        if line:
            session.update_from_line(line)

    await proc.wait()

    # Collect crashes produced this round
    crashes_dir = Path("/app/output/crashes") if Path("/app/output").exists() else Path("/tmp/fuzz-crashes")
    crashes_dir.mkdir(parents=True, exist_ok=True)
    new_crashes = collect_crashes(session.workspace, target, crashes_dir)
    for crash in new_crashes:
        crash_dict = crash.model_dump()
        # Avoid duplicates
        if not any(c["input_hash"] == crash_dict["input_hash"] for c in session.crash_files):
            session.crash_files.append(crash_dict)

    # Flush round execution count into the cumulative total
    session.flush_round()


async def _continuous_loop(session: ContinuousSession) -> None:
    """Run fuzzing targets in rounds until cancelled."""
    duration_per_target = 60  # 60 seconds per target per round

    try:
        session.status = "running"
        round_num = 0

        while True:
            round_num += 1
            session.current_round = round_num
            logger.info(f"Session {session.session_id}: starting round {round_num}")

            for target in session.targets:
                await _fuzz_target_continuous(session, target, duration_per_target)

    except asyncio.CancelledError:
        logger.info(f"Session {session.session_id}: cancelled")
        session.status = "stopped"
    except Exception as e:
        logger.exception(f"Session {session.session_id}: error: {e}")
        session.status = "error"
        session.append_output(f"ERROR: {e}")


async def start_continuous_fuzzing(
    project_path_str: str,
    targets: list[str] | None = None,
    jobs: int = 1,
) -> dict[str, Any]:
    """Start continuous fuzzing in background. Returns immediately."""
    project_path = Path(project_path_str)

    if not (project_path / "Cargo.toml").exists():
        return {"error": f"No Cargo.toml found at {project_path}"}

    workspace = setup_workspace(project_path)
    available_targets = find_fuzz_targets(workspace)
    if not available_targets:
        return {"error": "No fuzz targets found in fuzz/fuzz_targets/"}

    if targets:
        selected = [t for t in available_targets if t in targets]
        if not selected:
            return {"error": f"None of the requested targets found. Available: {available_targets}"}
        available_targets = selected

    # Generate session ID
    session_id = hashlib.md5(
        f"{project_path_str}-{time.time()}".encode()
    ).hexdigest()[:8]

    session = ContinuousSession(
        session_id=session_id,
        workspace=workspace,
        targets=available_targets,
        jobs=jobs,
    )
    _sessions[session_id] = session

    # Launch background task
    session.task = asyncio.create_task(_continuous_loop(session))

    return {
        "session_id": session_id,
        "status": "starting",
        "targets": available_targets,
        "message": (
            f"Continuous fuzzing started on {len(available_targets)} targets. "
            f"Use cargo_fuzz_status('{session_id}') to monitor progress. "
            f"Use cargo_fuzz_stop('{session_id}') to stop and collect results."
        ),
    }


def get_session_status(session_id: str) -> dict[str, Any]:
    """Get current status of a fuzzing session."""
    session = _sessions.get(session_id)
    if not session:
        return {"error": f"Unknown session: {session_id}"}
    return session.to_status_dict()


async def stop_continuous_fuzzing(session_id: str) -> dict[str, Any]:
    """Stop a running continuous fuzzing session."""
    session = _sessions.get(session_id)
    if not session:
        return {"error": f"Unknown session: {session_id}"}

    if session.task and not session.task.done():
        session.task.cancel()
        try:
            await session.task
        except asyncio.CancelledError:
            pass

    # Kill the fuzzer process if still running
    if session.process and session.process.returncode is None:
        session.process.terminate()
        try:
            await asyncio.wait_for(session.process.wait(), timeout=10)
        except asyncio.TimeoutError:
            session.process.kill()
            await session.process.wait()

    session.status = "stopped"

    # Flush any in-progress round executions
    session.flush_round()
    final_total = session.total_executions

    return {
        "session_id": session_id,
        "status": "stopped",
        "final_metrics": {
            "total_executions": final_total,
            "executions_per_second": session.executions_per_second,
            "coverage_edges": session.coverage_edges,
            "corpus_size": session.corpus_size,
            "total_crashes": session.total_crashes,
            "rounds_completed": session.current_round,
        },
        "crash_files": session.crash_files,
        "elapsed": session.elapsed_human,
        "message": f"Fuzzing stopped after {session.elapsed_human}, {session.current_round} rounds.",
    }


# --- MCP Server ---


app = Server("cargo-fuzzer-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="cargo_fuzz_run",
            description=(
                "Run cargo-fuzz (libFuzzer) on Rust fuzz targets for a fixed duration. "
                "Collects crash inputs and execution statistics (coverage edges, exec/s, "
                "corpus size). The project must have a fuzz/ directory with cargo-fuzz targets. "
                "Returns crash file paths and fuzzing metrics for each target. "
                "This is a BLOCKING call — use cargo_fuzz_start for continuous mode."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Rust project directory containing Cargo.toml",
                    },
                    "duration": {
                        "type": "integer",
                        "description": "Total fuzzing duration in seconds (split across targets)",
                        "default": 60,
                    },
                    "targets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: specific target names to fuzz (default: all)",
                    },
                    "jobs": {
                        "type": "integer",
                        "description": "Number of parallel fuzzing jobs",
                        "default": 1,
                    },
                },
                "required": ["project_path"],
            },
        ),
        Tool(
            name="cargo_fuzz_start",
            description=(
                "Start continuous cargo-fuzz fuzzing in the background. "
                "Returns immediately with a session_id. The fuzzer runs in rounds "
                "(60s per target per round) indefinitely until stopped. "
                "Use cargo_fuzz_status to monitor and cargo_fuzz_stop to stop. "
                "The MCP server process must remain running between calls "
                "(e.g., via Docker stdio transport without --rm)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Rust project directory containing Cargo.toml",
                    },
                    "targets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: specific target names to fuzz (default: all)",
                    },
                    "jobs": {
                        "type": "integer",
                        "description": "Number of parallel fuzzing jobs",
                        "default": 1,
                    },
                },
                "required": ["project_path"],
            },
        ),
        Tool(
            name="cargo_fuzz_status",
            description=(
                "Get live status and metrics from a running continuous fuzzing session. "
                "Returns current target, round number, execution count, coverage, "
                "crashes found, and recent output lines. "
                "Call periodically (every 10-30s) to monitor progress."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID returned by cargo_fuzz_start",
                    },
                },
                "required": ["session_id"],
            },
        ),
        Tool(
            name="cargo_fuzz_stop",
            description=(
                "Stop a running continuous fuzzing session and collect final results. "
                "Returns final metrics summary including total executions, crashes found, "
                "and crash file paths. The fuzzer process is gracefully terminated."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID of the session to stop",
                    },
                },
                "required": ["session_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        if name == "cargo_fuzz_run":
            project_path = arguments["project_path"]
            if not Path(project_path).exists():
                return [TextContent(type="text", text=f"Project not found: {project_path}")]
            result = await run_fuzzing(
                project_path_str=project_path,
                duration=arguments.get("duration", 60),
                targets=arguments.get("targets"),
                jobs=arguments.get("jobs", 1),
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "cargo_fuzz_start":
            project_path = arguments["project_path"]
            if not Path(project_path).exists():
                return [TextContent(type="text", text=f"Project not found: {project_path}")]
            result = await start_continuous_fuzzing(
                project_path_str=project_path,
                targets=arguments.get("targets"),
                jobs=arguments.get("jobs", 1),
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "cargo_fuzz_status":
            session_id = arguments["session_id"]
            result = get_session_status(session_id)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "cargo_fuzz_stop":
            session_id = arguments["session_id"]
            result = await stop_continuous_fuzzing(session_id)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        logger.exception(f"Error in {name}: {e}")
        return [TextContent(type="text", text=f"Error: {e!s}")]


async def main():
    logger.info("Starting Cargo Fuzzer MCP Server")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
