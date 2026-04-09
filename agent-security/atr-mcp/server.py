#!/usr/bin/env python3
"""
ATR MCP Server

A Model Context Protocol server that scans text content against
Agent Threat Rules (ATR) regex patterns to detect prompt injection,
jailbreak, data exfiltration, and other AI agent threats.

Tools:
    - atr_scan_text: Scan arbitrary text against ATR rules
    - atr_scan_mcp_config: Scan a full MCP config JSON for threats
    - atr_list_rules: List all loaded ATR rules
    - atr_rule_info: Get details for a specific rule
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("atr-mcp")


class ATRRule(BaseModel):
    """Model for a single ATR detection rule."""

    id: str
    title: str
    severity: str
    category: str
    threat_category: str = ""
    patterns: list[str] = Field(default_factory=list)


class Finding(BaseModel):
    """Model for a single scan finding."""

    rule_id: str
    title: str
    severity: str
    category: str
    threat_category: str
    matched_text: str
    position: int


class ScanResult(BaseModel):
    """Model for scan results."""

    text_length: int
    context: str
    findings: list[Finding] = Field(default_factory=list)
    rules_evaluated: int = 0
    threat_detected: bool = False


class ConfigScanResult(BaseModel):
    """Model for MCP config scan results."""

    tools_scanned: int = 0
    tools_with_threats: int = 0
    total_findings: int = 0
    per_tool_findings: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


def load_rules(rules_path: Path) -> list[ATRRule]:
    """Load ATR rules from JSON file."""
    if not rules_path.exists():
        logger.error(f"Rules file not found: {rules_path}")
        return []

    try:
        raw = json.loads(rules_path.read_text(encoding="utf-8"))
        rules = [ATRRule(**entry) for entry in raw]
        logger.info(f"Loaded {len(rules)} ATR rules from {rules_path}")
        return rules
    except Exception as exc:
        logger.exception(f"Failed to load rules: {exc}")
        return []


def compile_patterns(rules: list[ATRRule]) -> dict[str, list[re.Pattern[str]]]:
    """Pre-compile regex patterns for all rules."""
    compiled: dict[str, list[re.Pattern[str]]] = {}
    for rule in rules:
        compiled_list: list[re.Pattern[str]] = []
        for pattern_str in rule.patterns:
            try:
                compiled_list.append(re.compile(pattern_str, re.IGNORECASE | re.DOTALL))
            except re.error as exc:
                logger.warning(f"Invalid regex in {rule.id}: {exc}")
        compiled[rule.id] = compiled_list
    return compiled


# Rules that produce high false-positive rates when scanning SKILL.md content.
# These are excluded when context="skill" to reduce noise.
SKILL_CONTEXT_DENYLIST: set[str] = {
    "ATR-2026-00006",  # System Prompt Extraction — common in skill docs
    "ATR-2026-00016",  # Hidden Instructions via Encoding — hex/unicode in docs
    "ATR-2026-00017",  # Social Engineering - Urgency — common phrasing in docs
    "ATR-2026-00020",  # Base64 Encoded Payload — base64 examples in docs
}


def scan_text_against_rules(
    text: str,
    rules: list[ATRRule],
    compiled: dict[str, list[re.Pattern[str]]],
    context: str = "general",
) -> ScanResult:
    """Scan text against all ATR rules and return findings.

    When context is "skill", rules in SKILL_CONTEXT_DENYLIST are skipped
    to reduce false positives on SKILL.md content.
    """
    findings: list[Finding] = []
    seen_rule_ids: set[str] = set()

    applicable_rules = rules
    if context == "skill":
        applicable_rules = [r for r in rules if r.id not in SKILL_CONTEXT_DENYLIST]

    for rule in applicable_rules:
        patterns = compiled.get(rule.id, [])
        for pattern in patterns:
            match = pattern.search(text)
            if match and rule.id not in seen_rule_ids:
                seen_rule_ids.add(rule.id)
                matched_text = match.group(0)
                # Truncate long matches for readability
                display_text = matched_text[:200] + "..." if len(matched_text) > 200 else matched_text
                findings.append(
                    Finding(
                        rule_id=rule.id,
                        title=rule.title,
                        severity=rule.severity,
                        category=rule.category,
                        threat_category=rule.threat_category,
                        matched_text=display_text,
                        position=match.start(),
                    )
                )

    return ScanResult(
        text_length=len(text),
        context=context,
        findings=findings,
        rules_evaluated=len(applicable_rules),
        threat_detected=len(findings) > 0,
    )


# ---------------------------------------------------------------------------
# Load rules at module level
# ---------------------------------------------------------------------------
RULES_PATH = Path(__file__).parent / "rules.json"
RULES: list[ATRRule] = load_rules(RULES_PATH)
COMPILED_PATTERNS: dict[str, list[re.Pattern[str]]] = compile_patterns(RULES)

# Index rules by id for quick lookup
RULES_BY_ID: dict[str, ATRRule] = {rule.id: rule for rule in RULES}

# Create MCP server
app = Server("atr-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="atr_scan_text",
            description="Scan arbitrary text (tool description, SKILL.md, prompt) "
            "against Agent Threat Rules to detect prompt injection, jailbreak, "
            "data exfiltration, and other AI agent threats. Returns matched findings.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text content to scan for threats",
                    },
                    "context": {
                        "type": "string",
                        "description": "Scan context: 'mcp' for MCP tool descriptions, "
                        "'skill' for SKILL.md content (excludes high-FP rules), "
                        "or any other value for general scanning",
                        "default": "general",
                    },
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="atr_scan_mcp_config",
            description="Scan a full MCP configuration JSON (e.g. claude_desktop_config.json) "
            "for threats. Extracts tool descriptions and args from each server entry "
            "and scans them against ATR rules.",
            inputSchema={
                "type": "object",
                "properties": {
                    "config_json": {
                        "type": "string",
                        "description": "The MCP configuration JSON string to scan",
                    },
                },
                "required": ["config_json"],
            },
        ),
        Tool(
            name="atr_list_rules",
            description="List all loaded ATR detection rules with id, title, severity, "
            "and category. Optionally filter by category.",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Optional category to filter rules by (e.g. 'prompt-injection', "
                        "'jailbreak', 'data-exfiltration', 'tool-poisoning')",
                    },
                },
            },
        ),
        Tool(
            name="atr_rule_info",
            description="Get full details for a specific ATR rule by its ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "rule_id": {
                        "type": "string",
                        "description": "The ATR rule ID (e.g. 'ATR-2026-00001')",
                    },
                },
                "required": ["rule_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "atr_scan_text":
            text = arguments.get("text", "")
            if not text.strip():
                return [TextContent(type="text", text='{"error": "Text cannot be empty"}')]

            context = arguments.get("context", "general")
            result = scan_text_against_rules(text, RULES, COMPILED_PATTERNS, context)

            return [
                TextContent(
                    type="text",
                    text=json.dumps(result.model_dump(), indent=2),
                )
            ]

        elif name == "atr_scan_mcp_config":
            config_json = arguments.get("config_json", "")
            if not config_json.strip():
                return [TextContent(type="text", text='{"error": "Config JSON cannot be empty"}')]

            try:
                config = json.loads(config_json)
            except json.JSONDecodeError as exc:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": f"Invalid JSON: {exc}"}, indent=2),
                    )
                ]

            # Extract server entries from MCP config
            servers = config.get("mcpServers", config.get("servers", {}))
            if not isinstance(servers, dict):
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {"error": "No 'mcpServers' or 'servers' key found in config"},
                            indent=2,
                        ),
                    )
                ]

            config_result = ConfigScanResult()
            for server_name, server_config in servers.items():
                config_result.tools_scanned += 1

                # Build scannable text from command + args (not env values,
                # which are secrets and would trigger credential-exposure FPs).
                # json.dumps already includes args/env, so we only scan a
                # config copy with env values redacted.
                config_for_scan = dict(server_config)
                env_vars = config_for_scan.get("env", {})
                if isinstance(env_vars, dict):
                    # Only keep env var names for scanning, redact values
                    config_for_scan["env"] = {
                        k: "REDACTED" for k in env_vars
                    }

                scannable_text = json.dumps(config_for_scan, indent=2)

                scan = scan_text_against_rules(
                    scannable_text, RULES, COMPILED_PATTERNS, "mcp"
                )

                if scan.findings:
                    config_result.tools_with_threats += 1
                    config_result.total_findings += len(scan.findings)
                    config_result.per_tool_findings[server_name] = [
                        f.model_dump() for f in scan.findings
                    ]

            return [
                TextContent(
                    type="text",
                    text=json.dumps(config_result.model_dump(), indent=2),
                )
            ]

        elif name == "atr_list_rules":
            category_filter = arguments.get("category")
            rules_list = RULES

            if category_filter:
                rules_list = [r for r in rules_list if r.category == category_filter]

            output = [
                {
                    "id": r.id,
                    "title": r.title,
                    "severity": r.severity,
                    "category": r.category,
                }
                for r in rules_list
            ]

            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {"total": len(output), "rules": output}, indent=2
                    ),
                )
            ]

        elif name == "atr_rule_info":
            rule_id = arguments.get("rule_id", "")
            rule = RULES_BY_ID.get(rule_id)

            if not rule:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {"error": f"Rule not found: {rule_id}"}, indent=2
                        ),
                    )
                ]

            return [
                TextContent(
                    type="text",
                    text=json.dumps(rule.model_dump(), indent=2),
                )
            ]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as exc:
        logger.exception(f"Error executing tool {name}: {exc}")
        return [TextContent(type="text", text=json.dumps({"error": str(exc)}, indent=2))]


async def main() -> None:
    """Run the MCP server."""
    logger.info("Starting ATR MCP Server")
    logger.info(f"Loaded {len(RULES)} rules from {RULES_PATH}")

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
