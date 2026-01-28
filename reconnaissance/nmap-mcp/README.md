# Nmap MCP Server

Network reconnaissance MCP server using [Nmap](https://nmap.org/).

## Tools

| Tool | Description |
|------|-------------|
| `port_scan` | Discover open ports on target |
| `service_scan` | Detect service versions |
| `os_detection` | Fingerprint operating system |
| `script_scan` | Run NSE scripts |
| `quick_scan` | Fast scan of common ports |
| `get_scan_results` | Retrieve previous results |
| `list_active_scans` | Show running scans |

## Usage

### Docker

```bash
docker build -t nmap-mcp .
docker run -it --rm --cap-add=NET_RAW --cap-add=NET_ADMIN nmap-mcp
```

### Claude Desktop

```json
{
  "mcpServers": {
    "nmap": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "--cap-add=NET_RAW", "--cap-add=NET_ADMIN", "nmap-mcp:latest"]
    }
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NMAP_OUTPUT_DIR` | `/app/output` | Directory for scan output |
| `NMAP_TIMEOUT` | `300` | Default scan timeout (seconds) |
| `NMAP_MAX_CONCURRENT` | `3` | Max concurrent scans |

## Examples

### Port Scan
```
Scan ports 22, 80, 443 on 192.168.1.1
```

### Service Detection
```
Detect service versions on example.com ports 80 and 443
```

### OS Detection
```
Fingerprint the OS of 10.0.0.1
```

### Script Scan
```
Run http-title and ssl-cert scripts on example.com
```

## Capabilities

The container requires `NET_RAW` and `NET_ADMIN` capabilities for:
- SYN scanning (half-open scan)
- OS fingerprinting
- Some NSE scripts

Without these capabilities, nmap falls back to connect() scans.

## License

MIT
