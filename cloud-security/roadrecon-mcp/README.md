# RoadRecon MCP Server

Built from [atomicchonk/roadrecon_mcp_server](https://github.com/atomicchonk/roadrecon_mcp_server) - Azure AD enumeration and security analysis.

## Requirements

- Running ROADRecon instance with collected Azure AD data

## Features

- Query Azure AD users, groups, and applications
- Analyze service principals and permissions
- Identify privileged accounts and risky configurations
- Natural language security analysis

## Tools

| Tool | Description |
|------|-------------|
| list_users | List Azure AD users |
| list_groups | List Azure AD groups |
| list_applications | List Azure AD applications |
| list_service_principals | List service principals |
| analyze_permissions | Analyze permission grants |
| find_privileged | Find privileged accounts |

## Usage

### Docker

```bash
docker build -t roadrecon-mcp .
docker run -i --rm -e ROADRECON_URL=http://your-roadrecon:5000 roadrecon-mcp
```

### Claude Desktop

```json
{
  "mcpServers": {
    "roadrecon": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "ROADRECON_URL=http://localhost:5000",
        "roadrecon-mcp:latest"
      ]
    }
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ROADRECON_URL` | http://localhost:5000 | ROADRecon server URL |

## Security Notice

Use responsibly for authorized Azure AD security assessments only.

## License

MIT
