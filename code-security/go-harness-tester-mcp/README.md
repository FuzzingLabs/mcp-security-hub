# Go Harness Tester MCP Server

Tests the quality of Go fuzz harnesses before committing to a full fuzzing run — checks compilation, seed execution, and short fuzzing trials.

## Features

- Verifies project compiles successfully
- Runs fuzz targets with seed corpus to catch immediate failures
- Executes short fuzzing trials (default 10s) to validate harness stability
- Computes a quality score (0–100) based on compilation, seed pass rate, trial results, and crash behavior

## Tools

| Tool | Description |
|------|-------------|
| `go_harness_test` | Test Go fuzz harness quality — compilation, seeds, and short trial |

## Usage

### Docker

```bash
docker build -t go-harness-tester-mcp .
docker run -i --rm -v /path/to/project:/app/uploads go-harness-tester-mcp
```

## License

MIT
