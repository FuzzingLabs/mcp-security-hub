# Go Fuzzer MCP Server

Runs `go test -fuzz` on Go projects with support for one-shot and continuous fuzzing modes.

## Features

- Discovers `Fuzz*` targets in test files automatically
- One-shot fuzzing: run for a fixed duration, collect results
- Continuous fuzzing: background sessions with round-based metrics and live status
- Collects crash inputs from `testdata/fuzz/` and copies them to output
- Parses fuzzer output for execution count, coverage, and crash stats

## Tools

| Tool | Description |
|------|-------------|
| `go_fuzz_run` | Run go test -fuzz on project targets for a fixed duration |
| `go_fuzz_start` | Start continuous background fuzzing session |
| `go_fuzz_status` | Get status and metrics of a continuous session |
| `go_fuzz_stop` | Stop a continuous fuzzing session and collect results |

## Usage

### Docker

```bash
docker build -t go-fuzzer-mcp .
docker run -i --rm -v /path/to/project:/app/uploads go-fuzzer-mcp
```

## License

MIT
