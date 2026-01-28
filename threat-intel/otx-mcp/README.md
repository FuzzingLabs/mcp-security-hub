# OTX MCP Server

Wrapper for [mrwadams/otx-mcp](https://github.com/mrwadams/otx-mcp) - AlienVault Open Threat Exchange integration via MCP.

## Requirements

- AlienVault OTX API key (free at https://otx.alienvault.com/)

## Tools

| Tool | Description |
|------|-------------|
| Search indicators | Search for threat indicators |
| Get indicator details | Retrieve detailed info about specific IOCs |
| Get pulses | Access threat intelligence pulses |
| Submit URLs | Submit suspicious URLs for analysis |
| Monitor events | Track recent threat intelligence updates |

## Usage

### Docker

```bash
docker build -t otx-mcp .
docker run -it --rm -e OTX_API_KEY=your_key otx-mcp
```

### Claude Desktop

```json
{
  "mcpServers": {
    "otx": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "OTX_API_KEY=your_key",
        "ghcr.io/fuzzinglabs/otx-mcp:latest"
      ]
    }
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OTX_API_KEY` | (required) | AlienVault OTX API key |

## Security Notice

Use responsibly for authorized threat intelligence research.

## License

MIT
