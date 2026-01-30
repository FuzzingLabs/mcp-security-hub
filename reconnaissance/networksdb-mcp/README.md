# NetworksDB MCP Server

Built from [MorDavid/NetworksDB-MCP](https://github.com/MorDavid/NetworksDB-MCP) - Query IP addresses, ASN, and DNS records using natural language.

## Requirements

- NetworksDB API key (get at https://networksdb.io/)

## Features

- IP address lookups with geolocation
- ASN (Autonomous System Number) queries
- DNS record lookups
- Organization and network range information

## Tools

| Tool | Description |
|------|-------------|
| ip_lookup | Get detailed information about an IP address |
| asn_lookup | Query ASN details and associated networks |
| dns_lookup | Retrieve DNS records for a domain |
| org_lookup | Find networks owned by an organization |

## Usage

### Docker

```bash
docker build -t networksdb-mcp .
docker run -i --rm -e NETWORKSDB_API_KEY=your_key networksdb-mcp
```

### Claude Desktop

```json
{
  "mcpServers": {
    "networksdb": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "NETWORKSDB_API_KEY=your_key",
        "networksdb-mcp:latest"
      ]
    }
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NETWORKSDB_API_KEY` | (required) | NetworksDB API key |

## License

MIT
