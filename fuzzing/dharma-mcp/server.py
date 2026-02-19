#!/usr/bin/env python3
"""
Dharma MCP Server

A Model Context Protocol server for Dharma grammar-based fuzzing.
"""

import asyncio
import json
import logging
import os
import shlex
import tempfile
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
logger = logging.getLogger("dharma-mcp")


class Settings(BaseSettings):
    """Server configuration."""
    model_config = SettingsConfigDict(env_prefix="DHARMA_")
    
    grammar_dir: str = Field(default="/app/grammars")


settings = Settings()
app = Server("dharma-mcp")


async def run_dharma(grammar_path: str, count: int) -> tuple[str, str]:
    """
    Executes the dharma command asynchronously.
    """
    # Verify file exists
    p = Path(grammar_path)
    if not p.exists():
        # Try relative to grammar_dir
        p = Path(settings.grammar_dir) / grammar_path
        if not p.exists():
            return "", f"Grammar file not found: {grammar_path}"

    grammar_file = str(p)
    
    cmd = ["dharma", "-grammars", grammar_file, "-count", str(count)]
    
    logger.info(f"Executing: {' '.join(shlex.quote(c) for c in cmd)}")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=120.0
        )

        return stdout.decode(), stderr.decode()

    except asyncio.TimeoutError:
        return "", "Process timed out after 120 seconds."
    except Exception as e:
        return "", str(e)


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="dharma_generate",
            description="Generate test cases using a Dharma grammar file located on the server.",
            inputSchema={
                "type": "object",
                "properties": {
                    "grammar_path": {
                        "type": "string",
                        "description": "Absolute path to the grammar file (e.g. /app/grammars/json.dg)."
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of test cases to generate.",
                        "default": 1
                    }
                },
                "required": ["grammar_path"]
            },
        ),
        Tool(
            name="dharma_generate_custom",
            description="Generate test cases from a custom Dharma grammar provided as a string. Useful for dynamically generated grammars or quick testing without saving files.",
            inputSchema={
                "type": "object",
                "properties": {
                    "grammar_content": {
                        "type": "string",
                        "description": "The full content of the Dharma grammar file (plain text)."
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of test cases to generate.",
                        "default": 1
                    }
                },
                "required": ["grammar_content"]
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    
    if name == "dharma_generate":
        grammar_path = arguments.get("grammar_path")
        count = arguments.get("count", 1)

        if not grammar_path:
            return [TextContent(type="text", text="Error: 'grammar_path' is required.")]

        stdout, stderr = await run_dharma(grammar_path, count)

        if stderr and "error" in stderr.lower():
            return [TextContent(type="text", text=f"Error: {stderr}")]
        
        if not stdout and stderr:
             return [TextContent(type="text", text=f"Error: {stderr}")]

        return [TextContent(type="text", text=stdout)]

    elif name == "dharma_generate_custom":
        grammar_content = arguments.get("grammar_content")
        count = arguments.get("count", 1)

        if not grammar_content:
            return [TextContent(type="text", text="Error: 'grammar_content' is required.")]

        # Create a temporary file to store the custom grammar
        tmp_file_path = None
        try:
            # Create a temp file with .dg suffix so dharma recognizes it
            with tempfile.NamedTemporaryFile(mode='w', suffix='.dg', delete=False) as tmp:
                tmp.write(grammar_content)
                tmp_file_path = tmp.name
            
            logger.info(f"Generated temporary grammar file: {tmp_file_path}")

            # Run dharma using the temp file
            stdout, stderr = await run_dharma(tmp_file_path, count)

            if stderr and "error" in stderr.lower():
                return [TextContent(type="text", text=f"Error: {stderr}")]
            
            if not stdout and stderr:
                 return [TextContent(type="text", text=f"Error: {stderr}")]

            return [TextContent(type="text", text=stdout)]

        except Exception as e:
            logger.exception("Error processing custom grammar")
            return [TextContent(type="text", text=f"Error processing custom grammar: {str(e)}")]
        finally:
            # Clean up the temporary file
            if tmp_file_path and os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
                logger.info(f"Cleaned up temporary file: {tmp_file_path}")

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server."""
    logger.info("Starting Dharma MCP Server")
    logger.info(f"Grammar directory: {settings.grammar_dir}")
    
    Path(settings.grammar_dir).mkdir(parents=True, exist_ok=True)

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())