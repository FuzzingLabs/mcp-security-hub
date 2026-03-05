# Semgrep MCP Server

A clean MCP server wrapping the [Semgrep](https://github.com/semgrep/semgrep) CLI
for static code analysis. Follows the same pattern as every other
`mcp-security-hub` tool: a standalone `server.py` that calls the CLI via
`asyncio.create_subprocess_exec`.

> **Note:** The old [semgrep/mcp](https://github.com/semgrep/mcp) Docker image
> (`ghcr.io/semgrep/mcp`) is deprecated (all tags removed). This image uses the
> official `semgrep/semgrep:latest` base and wraps the CLI directly — no
> monkey-patching of semgrep internals.

## Tools

| Tool | Description |
|------|-------------|
| `get_supported_languages` | List programming languages supported by Semgrep |
| `get_abstract_syntax_tree` | Get the AST for code in any supported language |
| `semgrep_rule_schema` | Get the YAML schema for writing Semgrep rules |
| `semgrep_scan_with_custom_rule` | Scan code with an inline custom YAML rule |
| `semgrep_scan` | Scan code files with Semgrep registry rules (`--config auto`) |

## Transport

The image defaults to **streamable-http** on port 8000. You can also run it
in **stdio** mode by passing `stdio` as the first argument:

```bash
# HTTP (default)
docker run -d -p 8000:8000 semgrep-mcp

# Stdio
docker run -i semgrep-mcp stdio
```

## Usage

### Build & Run

```bash
docker build -t semgrep-mcp .
docker run -d -p 8000:8000 semgrep-mcp
```

### Test with curl

```bash
# Initialize
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'

# List tools
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

# Get supported languages
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_supported_languages","arguments":{}}}'

# Scan code with a custom rule
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"semgrep_scan_with_custom_rule","arguments":{"rule_yaml":"rules:\n  - id: test-eval\n    pattern: eval(...)\n    message: Do not use eval()\n    languages: [python]\n    severity: ERROR\n","code_files":{"test.py":"x = eval(input())"}}}}'
```

### Claude Desktop / MCP Client

```json
{
  "mcpServers": {
    "semgrep": {
      "command": "docker",
      "args": ["run", "-d", "-p", "8000:8000", "semgrep-mcp:latest"],
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SEMGREP_SEND_METRICS` | `off` | Semgrep metrics collection (`on`/`off`) |
| `SEMGREP_TIMEOUT` | `120` | Timeout in seconds for semgrep commands |
| `SEMGREP_MCP_HOST` | `0.0.0.0` | Server bind address |
| `SEMGREP_MCP_PORT` | `8000` | Server port |

## License

MIT
