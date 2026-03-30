# Rust Analyzer MCP Server

Analyzes Rust source code to identify fuzzable entry points, unsafe blocks, and known CVEs via cargo-audit.

## Tools

| Tool | Description |
|------|-------------|
| rust_analyze | Full static analysis of a Rust project |

## Usage

### Docker

```bash
docker build -t rust-analyzer-mcp .
docker run -i --rm -v /path/to/project:/project rust-analyzer-mcp
```

### Claude Desktop

```json
{
  "mcpServers": {
    "rust-analyzer": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/path/to/project:/project",
        "rust-analyzer-mcp:latest"
      ]
    }
  }
}
```

## License

MIT
