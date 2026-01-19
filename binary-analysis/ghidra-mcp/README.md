# Ghidra MCP Server (Headless)

A Model Context Protocol server for [Ghidra](https://ghidra-sre.org/), the NSA's open-source reverse engineering framework. This version runs completely headless - no GUI required.

> **Note**: This MCP server wraps [clearbluejar/pyghidra-mcp](https://github.com/clearbluejar/pyghidra-mcp).

## Tools

| Tool | Description |
|------|-------------|
| `decompile_function` | Decompile a function to pseudo-C code |
| `search_symbols_by_name` | Search for symbols by name |
| `search_code` | Search code using semantic queries (ChromaDB) |
| `list_project_binaries` | List all binaries in the project |
| `list_project_binary_metadata` | Get metadata for a binary |
| `list_exports` | List exported symbols |
| `list_imports` | List imported symbols |
| `list_cross_references` | Find cross-references |
| `search_strings` | Search for strings in binary |
| `read_bytes` | Read raw bytes at address |
| `gen_callgraph` | Generate function call graph |
| `import_binary` | Import a new binary into project |
| `delete_project_binary` | Remove binary from project |

## Features

- **Headless Operation**: Runs entirely from CLI, no GUI required
- **Multi-Binary Analysis**: Analyze entire projects with multiple binaries
- **Decompilation**: Get pseudo-C code from binary functions
- **Semantic Search**: Find code using natural language queries via ChromaDB
- **Cross-References**: Track data and code references
- **Call Graphs**: Generate function relationship graphs
- **String Search**: Find embedded strings

## Docker

### Build

```bash
docker build -t ghidra-mcp .
```

### Run

Mount your binaries directory and specify the target binary:

```bash
# Analyze a single binary
docker run --rm -i \
  -v "$(pwd):/binaries" \
  ghidra-mcp \
  /binaries/target_binary

# Analyze multiple binaries in a project
docker run --rm -i \
  -v "/path/to/bins:/binaries" \
  ghidra-mcp \
  /binaries/lib1.so /binaries/lib2.so /binaries/main
```

## Claude Desktop Configuration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ghidra": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "/path/to/binaries:/binaries",
        "ghidra-mcp",
        "/binaries/target.exe"
      ]
    }
  }
}
```

## Security Notice

This tool is designed for authorized reverse engineering and security research only.

## License

Apache-2.0
