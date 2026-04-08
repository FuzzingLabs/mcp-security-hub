# Go Analyzer MCP Server

Static analysis of Go projects for fuzzable targets and known vulnerabilities.

## Features

- Discovers fuzzable entry points (exported functions accepting `[]byte`, `string`, `io.Reader`, etc.)
- Finds existing `Fuzz*` test functions
- Detects unsafe/cgo/reflection usage
- Runs `govulncheck` for known CVEs
- Parses `go.mod` for module and Go version info

## Tools

| Tool | Description |
|------|-------------|
| `go_analyze` | Analyze a Go project for fuzzable targets, unsafe usage, and known vulnerabilities |

## Usage

### Docker

```bash
docker build -t go-analyzer-mcp .
docker run -i --rm -v /path/to/project:/app/uploads go-analyzer-mcp
```

## License

MIT
