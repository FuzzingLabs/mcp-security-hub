# Crash Analyzer MCP Server

Analyzes crashes from cargo-fuzz: reproduces them for stack traces, classifies crash types, determines severity, and deduplicates by signature.

## Tools

| Tool | Description |
|------|-------------|
| crash_analyze | Analyze and triage fuzzer crash inputs |

## Usage

### Docker

```bash
docker build -t crash-analyzer-mcp .
docker run -i --rm -v /path/to/project:/project crash-analyzer-mcp
```

### Claude Desktop

```json
{
  "mcpServers": {
    "crash-analyzer": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/path/to/project:/project",
        "crash-analyzer-mcp:latest"
      ]
    }
  }
}
```

## License

MIT
