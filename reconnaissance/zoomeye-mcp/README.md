# ZoomEye MCP Server

Wrapper for [zoomeye-ai/mcp_zoomeye](https://github.com/zoomeye-ai/mcp_zoomeye) - ZoomEye cyberspace search engine integration via MCP.

## Requirements

- ZoomEye API key (free 7-day trial at https://www.zoomeye.org/)

## Tools

| Tool | Description |
|------|-------------|
| Host search | Search for internet-connected hosts and devices |
| Web search | Search for web applications and services |
| Domain search | Query domain and subdomain information |
| IP search | Get detailed information about IP addresses |

## Features

- Query global internet assets using ZoomEye dorks
- Access protocol-level data (HTTP headers, SSL certs, SSH banners)
- Operating system and application detection
- Geolocation and ISP information
- Response caching to reduce API consumption

## Usage

### Docker

```bash
docker build -t zoomeye-mcp .
docker run -it --rm -e ZOOMEYE_API_KEY=your_key zoomeye-mcp
```

### Claude Desktop

```json
{
  "mcpServers": {
    "zoomeye": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "ZOOMEYE_API_KEY=your_key",
        "ghcr.io/fuzzinglabs/zoomeye-mcp:latest"
      ]
    }
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ZOOMEYE_API_KEY` | (required) | ZoomEye API key |

## Security Notice

Use responsibly for authorized reconnaissance and security research only.

## License

MIT
