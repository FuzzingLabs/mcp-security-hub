#!/usr/bin/env python3
"""
Boofuzz MCP Server

A Model Context Protocol server for network protocol fuzzing using Boofuzz.
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
from mcp.types import TextContent, Tool
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("boofuzz-mcp")


class Settings(BaseSettings):
    """Server configuration."""
    model_config = SettingsConfigDict(env_prefix="BOOFUZZ_")
    
    script_dir: str = Field(default="/app/scripts")
    results_dir: str = Field(default="/app/results")


settings = Settings()
app = Server("boofuzz-mcp")

# In-memory tracking of running processes
active_processes: dict[str, asyncio.subprocess.Process] = {}


def sanitize_filename(name: str) -> str:
    """Sanitize a filename to prevent path traversal."""
    safe = "".join(c for c in name if c.isalnum() or c in ('_', '-')).rstrip()
    return safe if safe else "unnamed"


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="boofuzz_create_script",
            description="Create and save a Boofuzz Python script on the server. The script should accept 'target_host' and 'target_port' as arguments or environment variables.",
            inputSchema={
                "type": "object",
                "properties": {
                    "script_name": {
                        "type": "string",
                        "description": "A short name for the script (e.g., 'ftp_fuzzer')."
                    },
                    "script_content": {
                        "type": "string",
                        "description": "The full Python code for the Boofuzz script."
                    },
                    "description": {
                        "type": "string",
                        "description": "A brief description of what the script does."
                    }
                },
                "required": ["script_name", "script_content"]
            },
        ),
        Tool(
            name="boofuzz_run_fuzzer",
            description="Execute a saved Boofuzz fuzzer script against a target. Runs asynchronously with a timeout.",
            inputSchema={
                "type": "object",
                "properties": {
                    "script_name": {
                        "type": "string",
                        "description": "Name of the previously saved script."
                    },
                    "target_host": {
                        "type": "string",
                        "description": "IP address or hostname of the target."
                    },
                    "target_port": {
                        "type": "integer",
                        "description": "Port number of the target service."
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Maximum execution time in seconds.",
                        "default": 60
                    }
                },
                "required": ["script_name", "target_host", "target_port"]
            },
        ),
        Tool(
            name="boofuzz_list_scripts",
            description="List all saved fuzzer scripts.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="boofuzz_get_results",
            description="Retrieve the crash log or audit results from a fuzzing session.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "The session ID returned by boofuzz_run_fuzzer."
                    }
                },
                "required": ["session_id"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    
    if name == "boofuzz_create_script":
        script_name = sanitize_filename(arguments.get("script_name", "unnamed"))
        script_content = arguments.get("script_content")
        description = arguments.get("description", "")

        if not script_content:
            return [TextContent(type="text", text="Error: 'script_content' is required.")]

        try:
            script_path = Path(settings.script_dir) / f"{script_name}.py"
            script_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Add metadata header
            full_content = f"# Description: {description}\n# Created: {datetime.now().isoformat()}\n\n{script_content}"
            
            with open(script_path, "w") as f:
                f.write(full_content)
            
            return [TextContent(type="text", text=f"Script saved successfully: {script_path}")]
        
        except Exception as e:
            logger.exception("Failed to save script")
            return [TextContent(type="text", text=f"Error saving script: {str(e)}")]

    elif name == "boofuzz_run_fuzzer":
        script_name = sanitize_filename(arguments.get("script_name"))
        target_host = arguments.get("target_host")
        target_port = arguments.get("target_port")
        timeout = arguments.get("timeout", 60)

        script_path = Path(settings.script_dir) / f"{script_name}.py"
        if not script_path.exists():
            return [TextContent(type="text", text=f"Error: Script '{script_name}' not found.")]

        session_id = str(uuid.uuid4())[:8]
        result_path = Path(settings.results_dir) / session_id
        result_path.mkdir(parents=True, exist_ok=True)

        # Environment variables to pass target info to the script
        env = os.environ.copy()
        env["TARGET_HOST"] = str(target_host)
        env["TARGET_PORT"] = str(target_port)
        env["SESSION_ID"] = session_id
        env["RESULTS_DIR"] = str(result_path)

        cmd = [sys.executable, str(script_path)]
        
        logger.info(f"Starting fuzzer {session_id}: {' '.join(cmd)}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            active_processes[session_id] = process

            # Wait for completion or timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=timeout
                )
                
                # Save output
                with open(result_path / "stdout.log", "w") as f:
                    f.write(stdout.decode())
                with open(result_path / "stderr.log", "w") as f:
                    f.write(stderr.decode())

                output_summary = stdout.decode()[-2000:] # Last 2000 chars
                error_summary = stderr.decode()[-500:]

                result_text = (
                    f"Fuzzing session {session_id} completed.\n"
                    f"Exit Code: {process.returncode}\n"
                    f"Results saved to: {result_path}\n"
                    f"Output snippet:\n{output_summary}\n"
                )
                if error_summary:
                    result_text += f"\nErrors:\n{error_summary}"

                return [TextContent(type="text", text=result_text)]

            except asyncio.TimeoutError:
                process.kill()
                return [TextContent(type="text", text=f"Fuzzing session {session_id} timed out after {timeout}s. Process killed. Check partial results in {result_path}.")]

        except Exception as e:
            logger.exception("Execution failed")
            return [TextContent(type="text", text=f"Execution error: {str(e)}")]
        finally:
            active_processes.pop(session_id, None)

    elif name == "boofuzz_list_scripts":
        scripts_path = Path(settings.script_dir)
        scripts = []
        if scripts_path.exists():
            for f in scripts_path.glob("*.py"):
                # Read first line description
                desc = "No description"
                try:
                    with open(f, 'r') as file:
                        first_line = file.readline()
                        if first_line.startswith("# Description:"):
                            desc = first_line.split(":", 1)[1].strip()
                except: pass
                
                scripts.append({
                    "name": f.stem,
                    "file": str(f),
                    "description": desc
                })
        
        return [TextContent(type="text", text=json.dumps(scripts, indent=2))]

    elif name == "boofuzz_get_results":
        session_id = arguments.get("session_id")
        result_path = Path(settings.results_dir) / session_id
        
        if not result_path.exists():
            return [TextContent(type="text", text=f"Session {session_id} not found.")]

        results = {"session_id": session_id, "files": {}}
        for f in result_path.glob("*"):
            try:
                results["files"][f.name] = f.read_text()[:5000] # Limit size
            except: pass
        
        return [TextContent(type="text", text=json.dumps(results, indent=2))]

    return [TextContent(type="text", text="Unknown tool.")]


async def main():
    """Run the MCP server."""
    logger.info("Starting Boofuzz MCP Server")
    
    Path(settings.script_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.results_dir).mkdir(parents=True, exist_ok=True)

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())