# Nuclei MCP Server

Custom MCP server wrapping ProjectDiscovery's [Nuclei](https://github.com/projectdiscovery/nuclei) vulnerability scanner.

## Tools

| Tool | Description |
|------|-------------|
| `nuclei_scan` | Comprehensive vulnerability scan with templates |
| `quick_scan` | Fast scan (high/critical only) |
| `template_scan` | Scan with specific template categories |
| `list_templates` | List available template categories |
| `get_scan_results` | Retrieve previous scan results |
| `list_active_scans` | Show running scans |

## Usage

### Docker

```bash
docker build -t nuclei-mcp .
docker run -it --rm nuclei-mcp
```

### Claude Desktop

```json
{
  "mcpServers": {
    "nuclei": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "nuclei-mcp:latest"]
    }
  }
}
```

### With Custom Templates

```json
{
  "mcpServers": {
    "nuclei": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/path/to/templates:/home/mcpuser/nuclei-templates:ro",
        "nuclei-mcp:latest"
      ]
    }
  }
}
```

## Template Categories

- `cves` - Known CVE vulnerabilities
- `vulnerabilities` - General vulnerabilities
- `exposures` - Exposed files/data
- `misconfiguration` - Security misconfigurations
- `technologies` - Technology detection
- `default-logins` - Default credentials
- `takeovers` - Subdomain takeover checks
- `network` - Network service vulnerabilities
- `ssl` - SSL/TLS issues
- `dns` - DNS vulnerabilities

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NUCLEI_TEMPLATES_PATH` | `/home/mcpuser/nuclei-templates` | Templates directory |
| `NUCLEI_OUTPUT_DIR` | `/app/output` | Scan output directory |
| `NUCLEI_TIMEOUT` | `600` | Default scan timeout (seconds) |
| `NUCLEI_MAX_CONCURRENT` | `2` | Maximum concurrent scans |
| `NUCLEI_RATE_LIMIT` | `150` | Requests per second |

## Security Notice

Always obtain **written authorization** before scanning targets.

## License

MIT
