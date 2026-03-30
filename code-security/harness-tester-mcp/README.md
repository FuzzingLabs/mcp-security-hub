# Harness Tester MCP Server

Tests and evaluates Rust fuzz harnesses by compiling, executing, and running short fuzzing trials. Produces actionable quality feedback for each harness.

## Tools

| Tool | Description |
|------|-------------|
| harness_test | Test all fuzz harnesses in a Rust project |

## Usage

### Docker

```bash
docker build -t harness-tester-mcp .
docker run -i --rm -v /path/to/project:/project harness-tester-mcp
```

### Claude Desktop

```json
{
  "mcpServers": {
    "harness-tester": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/path/to/project:/project",
        "harness-tester-mcp:latest"
      ]
    }
  }
}
```

## License

MIT
