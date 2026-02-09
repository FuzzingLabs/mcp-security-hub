# MCP-Scan

Built from [invariantlabs-ai/mcp-scan](https://github.com/invariantlabs-ai/mcp-scan) - Scan MCP servers for security vulnerabilities.

## Features

- Static and dynamic security scanning of MCP servers
- Detect prompt injection vulnerabilities
- Identify tool poisoning attacks
- Find toxic data flows
- Runtime monitoring via proxy

## Vulnerabilities Detected

| Vulnerability | Description |
|---------------|-------------|
| Prompt Injection | Malicious prompts in tool responses |
| Tool Poisoning | Compromised tool definitions |
| Toxic Flows | Dangerous data flow patterns |
| Information Disclosure | Sensitive data leaks |

## Usage

### Docker

```bash
docker build -t mcp-scan .

# Scan an MCP server configuration
docker run -i --rm -v /path/to/config:/config mcp-scan mcp-scan /config/mcp.json

# Run as proxy for runtime monitoring
docker run -i --rm -p 8080:8080 mcp-scan mcp-scan proxy --port 8080
```

### Claude Desktop

This tool is typically run standalone to audit MCP configurations, not as an MCP server itself.

```bash
# Scan your Claude Desktop config
mcp-scan ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

## Commands

| Command | Description |
|---------|-------------|
| `mcp-scan <config>` | Scan MCP configuration file |
| `mcp-scan proxy` | Run as monitoring proxy |
| `mcp-scan --help` | Show help |

## License

Apache 2.0
