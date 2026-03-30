#!/usr/bin/env python3
"""Harness Tester MCP Server.

Tests and evaluates Rust fuzz harnesses by compiling, executing, and running
short fuzzing trials. Produces actionable quality feedback for each harness.

Tools:
    - harness_test: Test all fuzz harnesses in a Rust project
"""

import asyncio
import json
import logging
import re
import shutil
import time
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
logger = logging.getLogger("harness-tester-mcp")


class Settings(BaseSettings):
    """Server configuration."""

    default_trial_duration: int = Field(default=30, alias="HARNESS_TESTER_TRIAL_DURATION")
    default_exec_timeout: int = Field(default=10, alias="HARNESS_TESTER_EXEC_TIMEOUT")

    class Config:
        env_prefix = "HARNESS_TESTER_"


settings = Settings()


# --- Feedback Models ---


class FeedbackSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class FeedbackCategory(str, Enum):
    COMPILATION = "compilation"
    EXECUTION = "execution"
    PERFORMANCE = "performance"
    COVERAGE = "coverage"
    STABILITY = "stability"
    CODE_QUALITY = "code_quality"


class FeedbackIssue(BaseModel):
    category: FeedbackCategory
    severity: FeedbackSeverity
    type: str
    message: str
    suggestion: str
    details: dict[str, Any] = Field(default_factory=dict)


class CompilationResult(BaseModel):
    success: bool
    time_ms: int | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    stderr: str | None = None


class ExecutionResult(BaseModel):
    success: bool
    runs_completed: int | None = None
    immediate_crash: bool = False
    timeout: bool = False
    crash_details: str | None = None


class CoverageMetrics(BaseModel):
    initial_edges: int = 0
    final_edges: int = 0
    new_edges_found: int = 0
    growth_rate: str = "none"
    percentage_estimate: float | None = None


class PerformanceMetrics(BaseModel):
    total_execs: int = 0
    execs_per_sec: float = 0.0
    performance_rating: str = "unknown"


class StabilityMetrics(BaseModel):
    status: str = "unknown"
    crashes_found: int = 0
    unique_crashes: int = 0
    crash_rate: float = 0.0


class FuzzingTrial(BaseModel):
    duration_seconds: int
    coverage: CoverageMetrics
    performance: PerformanceMetrics
    stability: StabilityMetrics
    trial_successful: bool


class QualityAssessment(BaseModel):
    score: int = Field(ge=0, le=100)
    verdict: str
    issues: list[FeedbackIssue] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class HarnessEvaluation(BaseModel):
    name: str
    path: str | None = None
    compilation: CompilationResult
    execution: ExecutionResult | None = None
    fuzzing_trial: FuzzingTrial | None = None
    quality: QualityAssessment


class EvaluationSummary(BaseModel):
    total_harnesses: int
    production_ready: int
    needs_improvement: int
    broken: int
    average_score: float
    recommended_action: str


class HarnessTestReport(BaseModel):
    harnesses: list[HarnessEvaluation]
    summary: EvaluationSummary
    test_configuration: dict[str, Any] = Field(default_factory=dict)


# --- Feedback Generator ---


class FeedbackGenerator:
    """Generates actionable feedback from test results."""

    @staticmethod
    def analyze_compilation(comp: dict) -> tuple[list[FeedbackIssue], list[str]]:
        issues, strengths = [], []
        if not comp.get("success"):
            for error in comp.get("errors", []):
                if "cannot find" in error.lower():
                    issue_type, suggestion = "undefined_variable", "Check variable names match the function signature."
                elif "mismatched types" in error.lower():
                    issue_type, suggestion = "type_mismatch", "Convert fuzzer input to the correct type (e.g., &[u8] to &str with from_utf8)."
                elif "trait" in error.lower() and "not implemented" in error.lower():
                    issue_type, suggestion = "trait_not_implemented", "Ensure you're using the correct types with required trait implementations."
                else:
                    issue_type, suggestion = "compilation_error", "Review the error message and fix syntax/type issues."
                issues.append(FeedbackIssue(
                    category=FeedbackCategory.COMPILATION, severity=FeedbackSeverity.CRITICAL,
                    type=issue_type, message=f"Compilation error: {error}", suggestion=suggestion,
                    details={"error": error},
                ))
        else:
            strengths.append("Compiles successfully")
            for w in comp.get("warnings", [])[:3]:
                if "unused" in w.lower():
                    issues.append(FeedbackIssue(
                        category=FeedbackCategory.CODE_QUALITY, severity=FeedbackSeverity.INFO,
                        type="unused_variable", message=f"Code quality: {w}",
                        suggestion="Remove unused variables or use underscore prefix.",
                    ))
        return issues, strengths

    @staticmethod
    def analyze_execution(exec_res: dict) -> tuple[list[FeedbackIssue], list[str]]:
        issues, strengths = [], []
        if not exec_res.get("success"):
            if exec_res.get("immediate_crash"):
                details = exec_res.get("crash_details", "")
                if "stack overflow" in details.lower():
                    t, s = "stack_overflow", "Check for infinite recursion or large stack allocations."
                elif "panic" in details.lower():
                    t, s = "panic_on_start", "Check initialization code and input validation."
                else:
                    t, s = "immediate_crash", "Debug harness initialization. Add error handling."
                issues.append(FeedbackIssue(
                    category=FeedbackCategory.EXECUTION, severity=FeedbackSeverity.CRITICAL,
                    type=t, message=f"Harness crashes: {details[:200]}", suggestion=s,
                ))
            elif exec_res.get("timeout"):
                issues.append(FeedbackIssue(
                    category=FeedbackCategory.EXECUTION, severity=FeedbackSeverity.CRITICAL,
                    type="infinite_loop", message="Harness times out - likely infinite loop",
                    suggestion="Add iteration limits or timeout mechanisms.",
                ))
        else:
            strengths.append("Executes without crashing")
        return issues, strengths

    @staticmethod
    def analyze_coverage(cov: CoverageMetrics) -> tuple[list[FeedbackIssue], list[str]]:
        issues, strengths = [], []
        if cov.new_edges_found == 0:
            issues.append(FeedbackIssue(
                category=FeedbackCategory.COVERAGE, severity=FeedbackSeverity.CRITICAL,
                type="no_coverage", message="No coverage detected - harness may not use fuzzer input",
                suggestion="Ensure fuzzer-provided data is passed to the target function.",
            ))
        elif cov.growth_rate == "poor":
            issues.append(FeedbackIssue(
                category=FeedbackCategory.COVERAGE, severity=FeedbackSeverity.WARNING,
                type="low_coverage", message=f"Low coverage: {cov.percentage_estimate}%",
                suggestion="Try fuzzing multiple entry points or remove restrictive input validation.",
            ))
        elif cov.growth_rate in ("good", "excellent"):
            strengths.append(f"Good coverage: {cov.final_edges} edges, {cov.percentage_estimate}% estimated")
        return issues, strengths

    @staticmethod
    def analyze_performance(perf: PerformanceMetrics) -> tuple[list[FeedbackIssue], list[str]]:
        issues, strengths = [], []
        if perf.execs_per_sec < 10:
            issues.append(FeedbackIssue(
                category=FeedbackCategory.PERFORMANCE, severity=FeedbackSeverity.CRITICAL,
                type="extremely_slow", message=f"Extremely slow: {perf.execs_per_sec:.1f} execs/sec",
                suggestion="Remove file I/O, network ops, or expensive computations from harness loop.",
            ))
        elif perf.execs_per_sec < 100:
            issues.append(FeedbackIssue(
                category=FeedbackCategory.PERFORMANCE, severity=FeedbackSeverity.WARNING,
                type="slow_execution", message=f"Slow: {perf.execs_per_sec:.1f} execs/sec",
                suggestion="Optimize harness: avoid allocations in hot path, reuse buffers.",
            ))
        elif perf.execs_per_sec > 1000:
            strengths.append(f"Excellent performance: {perf.execs_per_sec:.0f} execs/sec")
        else:
            strengths.append(f"Good performance: {perf.execs_per_sec:.0f} execs/sec")
        return issues, strengths

    @staticmethod
    def analyze_stability(stab: StabilityMetrics) -> tuple[list[FeedbackIssue], list[str]]:
        issues, strengths = [], []
        if stab.status == "crashes_frequently":
            issues.append(FeedbackIssue(
                category=FeedbackCategory.STABILITY, severity=FeedbackSeverity.WARNING,
                type="unstable", message=f"Crashes frequently: {stab.crash_rate:.1f}/1000 execs",
                suggestion="Add error handling for edge cases or invalid inputs.",
            ))
        elif stab.status == "stable":
            strengths.append("Stable execution - no crashes or hangs")
        if stab.unique_crashes > 0 and stab.status != "crashes_frequently":
            strengths.append(f"Found {stab.unique_crashes} potential bugs during trial!")
        return issues, strengths

    @classmethod
    def calculate_score(
        cls, comp_ok: bool, exec_ok: bool,
        cov: CoverageMetrics | None, perf: PerformanceMetrics | None, stab: StabilityMetrics | None,
    ) -> int:
        if not comp_ok:
            return 0
        if not exec_ok:
            return 10
        score = 20
        if cov:
            score += {"excellent": 40, "good": 30, "poor": 10}.get(cov.growth_rate, 0)
        if perf:
            if perf.execs_per_sec > 1000:
                score += 25
            elif perf.execs_per_sec > 500:
                score += 20
            elif perf.execs_per_sec > 100:
                score += 10
            elif perf.execs_per_sec > 10:
                score += 5
        if stab:
            score += {"stable": 15, "unstable": 10, "crashes_frequently": 5}.get(stab.status, 0)
        return min(score, 100)

    @classmethod
    def assess(
        cls, comp: dict, exec_res: dict | None,
        cov: CoverageMetrics | None, perf: PerformanceMetrics | None, stab: StabilityMetrics | None,
    ) -> QualityAssessment:
        all_issues, all_strengths = [], []
        for analyzer, arg in [
            (cls.analyze_compilation, comp),
            (cls.analyze_execution, exec_res) if exec_res else (None, None),
        ]:
            if analyzer:
                iss, st = analyzer(arg)
                all_issues.extend(iss)
                all_strengths.extend(st)
        if cov:
            iss, st = cls.analyze_coverage(cov)
            all_issues.extend(iss)
            all_strengths.extend(st)
        if perf:
            iss, st = cls.analyze_performance(perf)
            all_issues.extend(iss)
            all_strengths.extend(st)
        if stab:
            iss, st = cls.analyze_stability(stab)
            all_issues.extend(iss)
            all_strengths.extend(st)

        score = cls.calculate_score(
            comp.get("success", False),
            exec_res.get("success", False) if exec_res else False,
            cov, perf, stab,
        )
        verdict = "production-ready" if score >= 70 else ("needs-improvement" if score >= 30 else "broken")

        actions = []
        crits = [i for i in all_issues if i.severity == FeedbackSeverity.CRITICAL]
        warns = [i for i in all_issues if i.severity == FeedbackSeverity.WARNING]
        if crits:
            actions.append(f"Fix {len(crits)} critical issue(s)")
        if warns:
            actions.append(f"Address {len(warns)} warning(s)")
        if verdict == "production-ready":
            actions.append("Harness is ready for production fuzzing")

        return QualityAssessment(
            score=score, verdict=verdict,
            issues=all_issues, strengths=all_strengths, recommended_actions=actions,
        )


# --- Core Testing Logic ---


def find_fuzz_harnesses(project_path: Path) -> list[Path]:
    """Find fuzz harnesses in project."""
    fuzz_dir = project_path / "fuzz" / "fuzz_targets"
    if not fuzz_dir.exists():
        return []
    return list(fuzz_dir.glob("*.rs"))


async def test_compilation(project_path: Path, harness_name: str) -> CompilationResult:
    """Test harness compilation."""
    start = time.time()
    try:
        proc = await asyncio.create_subprocess_exec(
            "cargo", "+nightly", "fuzz", "build", harness_name,
            cwd=str(project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=300)
        elapsed_ms = int((time.time() - start) * 1000)
        stderr = stderr_bytes.decode(errors="replace")

        if proc.returncode == 0:
            warnings = [l.strip() for l in stderr.split("\n") if "warning:" in l][:5]
            return CompilationResult(success=True, time_ms=elapsed_ms, warnings=warnings)
        else:
            errors = [l.strip() for l in stderr.split("\n") if "error:" in l or "error[" in l][:10]
            return CompilationResult(success=False, time_ms=elapsed_ms, errors=errors, stderr=stderr[:2000])
    except asyncio.TimeoutError:
        return CompilationResult(success=False, errors=["Compilation timed out after 5 minutes"])
    except Exception as e:
        return CompilationResult(success=False, errors=[f"Compilation failed: {e}"])


async def test_execution(project_path: Path, harness_name: str, timeout_sec: int) -> ExecutionResult:
    """Test harness execution with minimal input."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "cargo", "+nightly", "fuzz", "run", harness_name,
            "--", "-runs=10", f"-max_total_time={timeout_sec}",
            cwd=str(project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=float(timeout_sec + 5))
        stderr = stderr_bytes.decode(errors="replace")

        if "SUMMARY: libFuzzer: deadly signal" in stderr:
            # Extract crash context
            lines = stderr.split("\n")
            for i, line in enumerate(lines):
                if "SUMMARY:" in line or "deadly signal" in line:
                    crash_ctx = "\n".join(lines[max(0, i - 3): i + 5])
                    return ExecutionResult(success=False, immediate_crash=True, crash_details=crash_ctx)
            return ExecutionResult(success=False, immediate_crash=True, crash_details=stderr[:500])

        return ExecutionResult(success=True, runs_completed=10)
    except asyncio.TimeoutError:
        return ExecutionResult(success=False, timeout=True)
    except Exception as e:
        return ExecutionResult(success=False, immediate_crash=True, crash_details=str(e))


async def run_fuzzing_trial(project_path: Path, harness_name: str, duration_sec: int) -> FuzzingTrial | None:
    """Run short fuzzing trial to gather metrics."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "cargo", "+nightly", "fuzz", "run", harness_name,
            "--", f"-max_total_time={duration_sec}", "-print_final_stats=1",
            cwd=str(project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=float(duration_sec + 30))
        stderr = stderr_bytes.decode(errors="replace")
        lines = stderr.split("\n")

        # Parse stats
        stats: dict[str, Any] = {
            "total_execs": 0, "exec_per_sec": 0.0,
            "cov_edges": 0, "initial_edges": 0, "crashes": 0,
        }

        # Initial coverage from first few lines
        for line in lines[:20]:
            if "cov:" in line:
                try:
                    stats["initial_edges"] = int(line.split("cov:")[1].split()[0])
                    break
                except (IndexError, ValueError):
                    pass

        # Final stats from last lines
        for line in reversed(lines):
            if "#" in line and "cov:" in line and "exec/s:" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.startswith("#"):
                        stats["total_execs"] = int(part[1:])
                    elif part == "cov:":
                        stats["cov_edges"] = int(parts[i + 1])
                    elif part == "exec/s:":
                        stats["exec_per_sec"] = float(parts[i + 1])
                break

            if "crash-" in line or "leak-" in line:
                stats["crashes"] += 1

        new_edges = stats["cov_edges"] - stats["initial_edges"]
        if new_edges == 0:
            growth = "none"
        elif new_edges < 50:
            growth = "poor"
        elif new_edges < 200:
            growth = "good"
        else:
            growth = "excellent"

        eps = stats["exec_per_sec"]
        perf_rating = "excellent" if eps > 1000 else ("good" if eps > 100 else "poor")

        total_execs = stats["total_execs"]
        crashes = stats["crashes"]
        crash_rate = (crashes / total_execs) * 1000 if total_execs > 0 else 0.0
        if crash_rate > 10:
            stab_status = "crashes_frequently"
        elif crash_rate > 1:
            stab_status = "unstable"
        else:
            stab_status = "stable"

        cov_pct = min((stats["cov_edges"] / 2000) * 100, 100) if stats["cov_edges"] > 0 else 0.0

        return FuzzingTrial(
            duration_seconds=duration_sec,
            coverage=CoverageMetrics(
                initial_edges=stats["initial_edges"], final_edges=stats["cov_edges"],
                new_edges_found=new_edges, growth_rate=growth,
                percentage_estimate=round(cov_pct, 1),
            ),
            performance=PerformanceMetrics(
                total_execs=total_execs, execs_per_sec=eps, performance_rating=perf_rating,
            ),
            stability=StabilityMetrics(
                status=stab_status, crashes_found=crashes,
                unique_crashes=min(crashes, 10), crash_rate=round(crash_rate, 2),
            ),
            trial_successful=True,
        )
    except Exception as e:
        logger.warning(f"Fuzzing trial failed: {e}")
        return None


async def test_single_harness(
    project_path: Path, harness_path: Path,
    trial_duration: int, exec_timeout: int,
) -> HarnessEvaluation:
    """Test a single harness: compile, execute, fuzz trial."""
    name = harness_path.stem

    # Step 1: Compilation
    logger.info(f"Compiling harness: {name}")
    comp = await test_compilation(project_path, name)

    if not comp.success:
        quality = FeedbackGenerator.assess(comp.model_dump(), None, None, None, None)
        return HarnessEvaluation(name=name, path=str(harness_path), compilation=comp, quality=quality)

    # Step 2: Execution
    logger.info(f"Testing execution: {name}")
    execution = await test_execution(project_path, name, exec_timeout)

    if not execution.success:
        quality = FeedbackGenerator.assess(comp.model_dump(), execution.model_dump(), None, None, None)
        return HarnessEvaluation(
            name=name, path=str(harness_path),
            compilation=comp, execution=execution, quality=quality,
        )

    # Step 3: Fuzzing trial
    logger.info(f"Running fuzzing trial: {name} ({trial_duration}s)")
    trial = await run_fuzzing_trial(project_path, name, trial_duration)

    quality = FeedbackGenerator.assess(
        comp.model_dump(), execution.model_dump(),
        trial.coverage if trial else None,
        trial.performance if trial else None,
        trial.stability if trial else None,
    )
    return HarnessEvaluation(
        name=name, path=str(harness_path),
        compilation=comp, execution=execution, fuzzing_trial=trial, quality=quality,
    )


async def test_harnesses(
    project_path_str: str,
    trial_duration: int = 30,
    exec_timeout: int = 10,
    target_harness: str | None = None,
) -> dict[str, Any]:
    """Test all (or one) fuzz harnesses in a Rust project."""
    project_path = Path(project_path_str)

    if not (project_path / "Cargo.toml").exists():
        return {"error": f"No Cargo.toml found at {project_path}"}

    # Copy to writable workspace (input may be read-only bind mount)
    workspace = Path("/tmp/harness-workspace")
    if workspace.exists():
        shutil.rmtree(workspace)
    shutil.copytree(project_path, workspace)
    project_path = workspace

    harnesses = find_fuzz_harnesses(project_path)
    if not harnesses:
        return {"error": "No fuzz harnesses found in fuzz/fuzz_targets/"}

    if target_harness:
        harnesses = [h for h in harnesses if h.stem == target_harness]
        if not harnesses:
            return {"error": f"Harness '{target_harness}' not found"}

    evaluations: list[HarnessEvaluation] = []
    for harness in harnesses:
        ev = await test_single_harness(project_path, harness, trial_duration, exec_timeout)
        evaluations.append(ev)

    # Summary
    prod_ready = sum(1 for e in evaluations if e.quality.verdict == "production-ready")
    needs_imp = sum(1 for e in evaluations if e.quality.verdict == "needs-improvement")
    broken = sum(1 for e in evaluations if e.quality.verdict == "broken")
    avg_score = sum(e.quality.score for e in evaluations) / len(evaluations) if evaluations else 0

    if broken > 0:
        action = f"Fix {broken} broken harness(es) before proceeding."
    elif needs_imp > 0:
        action = f"Improve {needs_imp} harness(es) for better results."
    else:
        action = "All harnesses are production-ready!"

    report = HarnessTestReport(
        harnesses=evaluations,
        summary=EvaluationSummary(
            total_harnesses=len(evaluations),
            production_ready=prod_ready, needs_improvement=needs_imp,
            broken=broken, average_score=round(avg_score, 1),
            recommended_action=action,
        ),
        test_configuration={
            "trial_duration_sec": trial_duration,
            "execution_timeout_sec": exec_timeout,
        },
    )

    return report.model_dump()


# --- MCP Server ---


app = Server("harness-tester-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="harness_test",
            description=(
                "Test Rust fuzz harnesses by compiling, executing with minimal input, "
                "and running short fuzzing trials. Returns detailed quality assessments "
                "with actionable feedback including compilation errors, coverage metrics, "
                "performance ratings, and stability analysis. "
                "Requires the project to have a fuzz/ directory with cargo-fuzz targets."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Rust project directory containing Cargo.toml and fuzz/",
                    },
                    "target_harness": {
                        "type": "string",
                        "description": "Optional: test only this specific harness (by name, without .rs extension)",
                    },
                    "trial_duration": {
                        "type": "integer",
                        "description": "Duration for each fuzzing trial in seconds",
                        "default": 30,
                    },
                    "execution_timeout": {
                        "type": "integer",
                        "description": "Timeout for execution test in seconds",
                        "default": 10,
                    },
                },
                "required": ["project_path"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        if name == "harness_test":
            project_path = arguments["project_path"]

            if not Path(project_path).exists():
                return [TextContent(type="text", text=f"Project not found: {project_path}")]

            result = await test_harnesses(
                project_path_str=project_path,
                trial_duration=arguments.get("trial_duration", 30),
                exec_timeout=arguments.get("execution_timeout", 10),
                target_harness=arguments.get("target_harness"),
            )

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        logger.exception(f"Error in {name}: {e}")
        return [TextContent(type="text", text=f"Error: {e!s}")]


async def main():
    logger.info("Starting Harness Tester MCP Server")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
