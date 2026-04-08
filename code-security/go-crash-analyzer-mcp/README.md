# Go Crash Analyzer MCP Server

Analyzes crashes produced by Go fuzz testing — classifies crash type, parses stack traces, reproduces inputs, and deduplicates findings.

## Features

- Classifies crashes (panic, nil dereference, index out of range, timeout, OOM, etc.)
- Parses Go stack traces into structured frames
- Reproduces crashes by re-running the fuzz target with the crashing input
- Computes deduplication signatures from crash type + top stack frames
- Discovers crash files from `testdata/fuzz/` corpus directories

## Tools

| Tool | Description |
|------|-------------|
| `go_crash_analyze` | Analyze Go fuzzing crashes — classify, reproduce, and deduplicate |

## Usage

### Docker

```bash
docker build -t go-crash-analyzer-mcp .
docker run -i --rm -v /path/to/project:/app/uploads go-crash-analyzer-mcp
```

## License

MIT
