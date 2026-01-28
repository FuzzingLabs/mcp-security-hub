# Radare2 MCP Server

Docker wrapper around official [radareorg/radare2-mcp](https://github.com/radareorg/radare2-mcp).

## Features

- Binary analysis with radare2
- Disassembly and decompilation
- Function analysis
- Cross-references
- Read-only sandbox mode
- Written in C using native r2 APIs

## Usage

### Docker

```bash
docker build -t radare2-mcp .
docker run -it --rm -v /path/to/samples:/home/mcpuser/samples radare2-mcp
```

### Claude Desktop

```json
{
  "mcpServers": {
    "radare2": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/path/to/samples:/home/mcpuser/samples:ro",
        "radare2-mcp:latest"
      ]
    }
  }
}
```

## Security

- Runs as non-root user
- Sample files mounted read-only recommended
- Sandbox mode enabled by default

## Credits

This is a Docker wrapper around the official [radareorg/radare2-mcp](https://github.com/radareorg/radare2-mcp).

## License

MIT (wrapper) - Upstream also MIT
