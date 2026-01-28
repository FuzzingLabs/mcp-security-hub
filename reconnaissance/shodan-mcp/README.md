# Shodan MCP Server

Docker wrapper around [BurtTheCoder/mcp-shodan](https://github.com/BurtTheCoder/mcp-shodan).

## Tools

| Tool | Description |
|------|-------------|
| `shodan_ip_lookup` | Get info about an IP address |
| `shodan_search` | Search Shodan database |
| `shodan_cve_lookup` | Look up CVE details |
| `shodan_dns_lookup` | DNS lookup for domain |
| `shodan_reverse_dns` | Reverse DNS lookup |
| `shodan_cpe_lookup` | Search CPE entries |
| `shodan_cves_by_product` | Find CVEs for a product |

## Usage

### Docker

```bash
docker build -t shodan-mcp .
docker run -it --rm -e SHODAN_API_KEY=your_key shodan-mcp
```

### Claude Desktop

```json
{
  "mcpServers": {
    "shodan": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-e", "SHODAN_API_KEY=your_key", "shodan-mcp:latest"]
    }
  }
}
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SHODAN_API_KEY` | Yes | Your Shodan API key |

Get your API key at https://account.shodan.io/

## Credits

This is a Docker wrapper around [@burtthecoder/mcp-shodan](https://github.com/BurtTheCoder/mcp-shodan).

## License

MIT (wrapper) - Upstream also MIT
