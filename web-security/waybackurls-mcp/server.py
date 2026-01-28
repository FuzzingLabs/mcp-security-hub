#!/usr/bin/env python3
"""
Waybackurls MCP Server

A Model Context Protocol server that fetches all URLs from the Wayback Machine
for a given domain using waybackurls by @tomnomnom.

Tools:
    - fetch_wayback_urls: Fetch URLs for a domain from the Wayback Machine
    - get_fetch_results: Retrieve results from a previous fetch
    - list_active_fetches: Show currently running fetches
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    TextContent,
    Tool,
)
from pydantic import BaseModel, Field, ConfigDict
from pydantic_settings import BaseSettings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("waybackurls-mcp")


class Settings(BaseSettings):
    """Server configuration from environment variables."""

    model_config = ConfigDict(env_prefix="WAYBACKURLS_")

    output_dir: str = Field(default="/app/output", alias="WAYBACKURLS_OUTPUT_DIR")
    default_timeout: int = Field(default=300, alias="WAYBACKURLS_TIMEOUT")
    max_concurrent_fetches: int = Field(default=3, alias="WAYBACKURLS_MAX_CONCURRENT")


settings = Settings()


class FetchResult(BaseModel):
    """Model for fetch results."""

    fetch_id: str
    domain: str
    started_at: datetime
    completed_at: datetime | None = None
    status: str = "running"
    urls: list[str] = []
    total_urls: int = 0
    stats: dict[str, Any] = {}
    error: str | None = None


# In-memory storage for fetch results
fetch_results: dict[str, FetchResult] = {}
active_fetches: set[str] = set()


def analyze_urls(urls: list[str]) -> dict[str, Any]:
    """Analyze fetched URLs and generate statistics."""
    stats = {
        "total": len(urls),
        "by_extension": {},
        "by_subdomain": {},
        "by_path_depth": {},
        "protocols": {"http": 0, "https": 0},
        "with_params": 0,
    }

    for url in urls:
        try:
            parsed = urlparse(url)
            
            # Protocol stats
            if parsed.scheme == "http":
                stats["protocols"]["http"] += 1
            elif parsed.scheme == "https":
                stats["protocols"]["https"] += 1
            
            # Subdomain stats
            domain = parsed.netloc
            stats["by_subdomain"][domain] = stats["by_subdomain"].get(domain, 0) + 1
            
            # Extension stats
            path = parsed.path
            if "." in path:
                ext = path.split(".")[-1].split("?")[0].split("#")[0].lower()
                if ext and len(ext) <= 5:
                    stats["by_extension"][ext] = stats["by_extension"].get(ext, 0) + 1
            
            # Path depth
            depth = len([p for p in path.split("/") if p])
            stats["by_path_depth"][depth] = stats["by_path_depth"].get(depth, 0) + 1
            
            # Parameters
            if parsed.query:
                stats["with_params"] += 1
                
        except Exception as e:
            logger.debug(f"Error analyzing URL {url}: {e}")
            continue

    # Sort and limit top entries
    stats["by_extension"] = dict(sorted(
        stats["by_extension"].items(), 
        key=lambda x: x[1], 
        reverse=True
    )[:20])
    
    stats["by_subdomain"] = dict(sorted(
        stats["by_subdomain"].items(), 
        key=lambda x: x[1], 
        reverse=True
    )[:20])
    
    stats["by_path_depth"] = dict(sorted(
        stats["by_path_depth"].items(), 
        key=lambda x: x[0]
    ))

    return stats


async def run_waybackurls(
    domain: str,
    get_subs: bool = False,
    no_subs: bool = False,
    dates: bool = False,
    timeout: int | None = None,
) -> FetchResult:
    """Execute waybackurls asynchronously."""
    fetch_id = str(uuid.uuid4())[:8]
    output_file = Path(settings.output_dir) / f"wayback_{fetch_id}.txt"

    result = FetchResult(
        fetch_id=fetch_id,
        domain=domain,
        started_at=datetime.now(),
    )
    fetch_results[fetch_id] = result
    active_fetches.add(fetch_id)

    # Build waybackurls command
    # waybackurls accepts domains on stdin
    cmd = ["waybackurls"]
    
    if get_subs:
        cmd.append("-get-subs")
    if no_subs:
        cmd.append("-no-subs")
    if dates:
        cmd.append("-dates")

    logger.info(f"Starting waybackurls fetch {fetch_id} for domain: {domain}")
    logger.debug(f"Command: echo {domain} | {' '.join(cmd)}")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Send domain to stdin
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=domain.encode()),
            timeout=float(timeout or settings.default_timeout),
        )

        result.completed_at = datetime.now()

        # Parse output
        stdout_text = stdout.decode()
        if stdout_text.strip():
            urls = [line.strip() for line in stdout_text.split("\n") if line.strip()]
            result.urls = urls
            result.total_urls = len(urls)
            
            # Save to file
            output_file.write_text("\n".join(urls))
            
            # Generate statistics
            result.stats = analyze_urls(urls)

        stderr_text = stderr.decode()
        if stderr_text:
            logger.debug(f"Waybackurls stderr: {stderr_text}")

        if process.returncode == 0:
            result.status = "completed"
            logger.info(f"Fetch {fetch_id} completed: {result.total_urls} URLs found")
        else:
            if result.total_urls > 0:
                result.status = "completed"
            else:
                result.status = "failed"
                result.error = stderr_text or "No output from waybackurls"
                logger.error(f"Fetch {fetch_id} failed: {result.error}")

    except asyncio.TimeoutError:
        result.status = "timeout"
        result.error = f"Fetch timed out after {timeout or settings.default_timeout} seconds"
        result.completed_at = datetime.now()
        logger.error(f"Fetch {fetch_id} timed out")

    except Exception as e:
        result.status = "error"
        result.error = str(e)
        result.completed_at = datetime.now()
        logger.exception(f"Fetch {fetch_id} error: {e}")

    finally:
        active_fetches.discard(fetch_id)
        fetch_results[fetch_id] = result

    return result


def format_fetch_summary(result: FetchResult, include_urls: bool = False, limit: int = 100) -> dict[str, Any]:
    """Format fetch result for response."""
    summary = {
        "fetch_id": result.fetch_id,
        "domain": result.domain,
        "status": result.status,
        "total_urls": result.total_urls,
        "started_at": result.started_at.isoformat(),
        "completed_at": result.completed_at.isoformat() if result.completed_at else None,
        "stats": result.stats,
        "error": result.error,
    }
    
    if include_urls:
        summary["urls"] = result.urls[:limit]
        if len(result.urls) > limit:
            summary["urls_truncated"] = f"Showing {limit} of {len(result.urls)} URLs"
    
    return summary


# Create MCP server
app = Server("waybackurls-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="fetch_wayback_urls",
            description="Fetch all URLs from the Wayback Machine for a given domain. "
            "Returns historical URLs that were archived for the domain.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain to fetch URLs for (e.g., example.com)",
                    },
                    "get_subs": {
                        "type": "boolean",
                        "description": "Also fetch subdomains (e.g., *.example.com)",
                        "default": False,
                    },
                    "no_subs": {
                        "type": "boolean",
                        "description": "Don't include subdomains, only the exact domain",
                        "default": False,
                    },
                    "dates": {
                        "type": "boolean",
                        "description": "Show timestamps for when URLs were archived",
                        "default": False,
                    },
                    "include_urls": {
                        "type": "boolean",
                        "description": "Include the actual URLs in the response (default: true)",
                        "default": True,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of URLs to return in response (default: 100)",
                        "default": 100,
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds",
                        "default": 300,
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="get_fetch_results",
            description="Retrieve results from a previous waybackurls fetch by fetch ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "fetch_id": {
                        "type": "string",
                        "description": "Fetch ID returned from a previous fetch",
                    },
                    "include_urls": {
                        "type": "boolean",
                        "description": "Include the actual URLs in the response",
                        "default": True,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of URLs to return",
                        "default": 100,
                    },
                },
                "required": ["fetch_id"],
            },
        ),
        Tool(
            name="list_active_fetches",
            description="List currently running waybackurls fetches.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "fetch_wayback_urls":
            if len(active_fetches) >= settings.max_concurrent_fetches:
                return [
                    TextContent(
                        type="text",
                        text=f"Maximum concurrent fetches ({settings.max_concurrent_fetches}) reached. "
                        f"Please wait for active fetches to complete.",
                    )
                ]

            domain = arguments["domain"]
            # Clean domain input
            domain = domain.strip().lower()
            if domain.startswith("http://") or domain.startswith("https://"):
                domain = urlparse(domain).netloc

            result = await run_waybackurls(
                domain=domain,
                get_subs=arguments.get("get_subs", False),
                no_subs=arguments.get("no_subs", False),
                dates=arguments.get("dates", False),
                timeout=arguments.get("timeout"),
            )

            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        format_fetch_summary(
                            result,
                            include_urls=arguments.get("include_urls", True),
                            limit=arguments.get("limit", 100),
                        ),
                        indent=2,
                    ),
                )
            ]

        elif name == "get_fetch_results":
            fetch_id = arguments["fetch_id"]
            result = fetch_results.get(fetch_id)

            if result:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            format_fetch_summary(
                                result,
                                include_urls=arguments.get("include_urls", True),
                                limit=arguments.get("limit", 100),
                            ),
                            indent=2,
                        ),
                    )
                ]
            else:
                return [
                    TextContent(type="text", text=f"Fetch '{fetch_id}' not found")
                ]

        elif name == "list_active_fetches":
            active = [
                {
                    "fetch_id": fetch_id,
                    "domain": fetch_results[fetch_id].domain,
                    "started_at": fetch_results[fetch_id].started_at.isoformat(),
                }
                for fetch_id in active_fetches
                if fetch_id in fetch_results
            ]

            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "active_fetches": active,
                            "count": len(active),
                            "max_concurrent": settings.max_concurrent_fetches,
                        },
                        indent=2,
                    ),
                )
            ]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        logger.exception(f"Error executing tool {name}: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


@app.list_resources()
async def list_resources() -> list[Resource]:
    """List available resources."""
    resources = []

    for fetch_id, result in fetch_results.items():
        if result.status == "completed":
            resources.append(
                Resource(
                    uri=f"waybackurls://results/{fetch_id}",
                    name=f"Wayback URLs: {result.domain} ({result.total_urls} URLs)",
                    description=f"Fetched at {result.completed_at}",
                    mimeType="text/plain",
                )
            )

    return resources


@app.read_resource()
async def read_resource(uri: str) -> str:
    """Read a resource."""
    if uri.startswith("waybackurls://results/"):
        fetch_id = uri.replace("waybackurls://results/", "")
        result = fetch_results.get(fetch_id)
        if result:
            return "\n".join(result.urls)

    return json.dumps({"error": "Resource not found"})


async def main():
    """Run the MCP server."""
    logger.info("Starting Waybackurls MCP Server")
    logger.info(f"Output directory: {settings.output_dir}")

    # Ensure directories exist
    Path(settings.output_dir).mkdir(parents=True, exist_ok=True)

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
