# Gitleaks MCP Server

Custom MCP server wrapping [Gitleaks](https://github.com/gitleaks/gitleaks) for detecting secrets and credentials in git repositories and files.

## Tools

| Tool | Description |
|------|-------------|
| `gitleaks_scan_repo` | Scan a git repository including commit history |
| `gitleaks_scan_dir` | Scan a directory without git history |
| `gitleaks_detect` | Quick scan text content for secrets |
| `get_scan_results` | Retrieve previous scan results |
| `list_active_scans` | Show running scans |

## Usage

### Docker

```bash
docker build -t gitleaks-mcp .
docker run -it --rm gitleaks-mcp
```

### Claude Desktop

```json
{
  "mcpServers": {
    "gitleaks": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "ghcr.io/fuzzinglabs/gitleaks-mcp:latest"]
    }
  }
}
```

### Scan Local Repository

```json
{
  "mcpServers": {
    "gitleaks": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/path/to/repos:/repos:ro",
        "ghcr.io/fuzzinglabs/gitleaks-mcp:latest"
      ]
    }
  }
}
```

## What Gitleaks Detects

- API keys (AWS, GCP, Azure, Stripe, etc.)
- Passwords and tokens
- Private keys (SSH, PGP)
- Database connection strings
- OAuth secrets
- JWT tokens
- And 150+ other secret patterns

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLEAKS_OUTPUT_DIR` | `/app/output` | Scan output directory |
| `GITLEAKS_TIMEOUT` | `300` | Default scan timeout (seconds) |
| `GITLEAKS_MAX_CONCURRENT` | `2` | Maximum concurrent scans |

## Security Notes

- Secrets in output are automatically masked (first 4 chars visible)
- Always obtain **written authorization** before scanning repositories
- Be careful with scan outputs - they may contain partial secrets

## License

MIT
