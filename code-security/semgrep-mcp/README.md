# Semgrep MCP Server

Wrapper for [semgrep/mcp](https://github.com/semgrep/mcp) - Static code analysis for security vulnerabilities.

## Features

- 5000+ security rules out of the box
- Supports 30+ programming languages
- Fast, deterministic static analysis
- Custom rule support

## Tools

| Tool | Description |
|------|-------------|
| security_check | Quick security scan of code |
| semgrep_scan | Full Semgrep scan with configurable rules |
| semgrep_scan_with_custom_rule | Scan with custom YAML rules |
| get_abstract_syntax_tree | Get AST for code analysis |
| semgrep_findings | Get findings from previous scans |
| supported_languages | List supported languages |

## Usage

### Docker

```bash
docker build -t semgrep-mcp .
docker run -i --rm -v /path/to/code:/code semgrep-mcp
```

### Claude Desktop

```json
{
  "mcpServers": {
    "semgrep": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/path/to/code:/code",
        "semgrep-mcp:latest"
      ]
    }
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SEMGREP_APP_TOKEN` | (optional) | Semgrep Cloud token for additional rules |

## License

MIT
