# Cargo Fuzzer MCP Server

Runs [cargo-fuzz](https://github.com/rust-fuzz/cargo-fuzz) (libFuzzer) on Rust fuzz targets for a configurable duration, collects crashes and execution statistics.

## Tools

| Tool | Description |
|------|-------------|
| cargo_fuzz_run | Run cargo-fuzz on one or all targets (blocking, fixed duration) |
| cargo_fuzz_start | Start continuous fuzzing in background (non-blocking) |
| cargo_fuzz_status | Get live metrics from a running fuzzing session |
| cargo_fuzz_stop | Stop a running fuzzing session and collect final results |

## Usage

### Docker

```bash
docker build -t cargo-fuzzer-mcp .
docker run -i --rm -v /path/to/project:/project cargo-fuzzer-mcp
```

### Claude Desktop

```json
{
  "mcpServers": {
    "cargo-fuzzer": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/path/to/project:/project",
        "cargo-fuzzer-mcp:latest"
      ]
    }
  }
}
```

## License

MIT
