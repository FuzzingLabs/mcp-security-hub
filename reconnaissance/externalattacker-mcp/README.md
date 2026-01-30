# ExternalAttacker MCP Server

Built from [MorDavid/ExternalAttacker-MCP](https://github.com/MorDavid/ExternalAttacker-MCP) - External attack surface mapping using ProjectDiscovery tools.

## Features

- Subdomain discovery with subfinder
- Port scanning with naabu
- HTTP analysis with httpx
- DNS enumeration with dnsx
- CDN detection with cdncheck
- TLS analysis with tlsx

## Tools

| Tool | Description |
|------|-------------|
| discover_subdomains | Find subdomains for a target domain |
| scan_ports | Scan for open ports on targets |
| analyze_http | Analyze HTTP responses and headers |
| enumerate_dns | Enumerate DNS records |
| check_cdn | Detect CDN providers |
| analyze_tls | Analyze TLS certificates |

## Usage

### Docker

```bash
docker build -t externalattacker-mcp .
docker run -i --rm externalattacker-mcp
```

### Claude Desktop

```json
{
  "mcpServers": {
    "externalattacker": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "externalattacker-mcp:latest"]
    }
  }
}
```

## Security Notice

Use responsibly for authorized reconnaissance and security research only.

## License

MIT
