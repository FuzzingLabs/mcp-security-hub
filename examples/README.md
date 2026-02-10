# MCP Configuration Examples

Example configuration files for using MCP Security Hub with Claude Desktop and Claude Code.

## Prerequisites

Build the Docker images first:

```bash
cd mcp-security-hub
docker-compose build
```

## Claude Desktop Configuration

Copy `claude-desktop-config.json` to your Claude Desktop config location:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

Then customize the volume mount paths to match your system.

## Project-Level Configuration (Claude Code)

Copy `mcp-project.json` to your project root as `.mcp.json`:

```bash
cp examples/mcp-project.json /path/to/your/project/.mcp.json
```

This enables MCPs only for that specific project with the current directory mounted.

## Volume Mounts

MCPs run in isolated Docker containers. To give them access to files:

### Read-only access (recommended for scanning)

```json
"-v", "/host/path:/container/path:ro"
```

### Read-write access (for tools that generate output)

```json
"-v", "/host/path:/container/path"
```

### Common mount patterns

| MCP | Host Path | Container Path | Purpose |
|-----|-----------|----------------|---------|
| gitleaks | Your repos | `/app/target` | Scan for secrets |
| yara | Sample files | `/app/samples` | Malware scanning |
| yara | YARA rules | `/app/rules` | Custom rules |
| capa | Binaries | `/app/samples` | Capability detection |
| radare2 | Binaries | `/samples` | Reverse engineering |
| trivy | Code/images | `/app/target` | Vulnerability scanning |
| semgrep | Source code | `/app/target` | Static analysis |
| prowler | AWS creds | `/home/mcpuser/.aws` | Cloud auditing |

## Special Permissions

Some MCPs require additional Docker capabilities:

| MCP | Capability | Reason |
|-----|------------|--------|
| nmap | `--cap-add=NET_RAW` | Raw socket access for SYN scans |
| masscan | `--cap-add=NET_RAW` | Raw socket access for port scanning |
| trivy | Docker socket mount | Scan Docker images |

## Environment Variables

Some MCPs need API keys or configuration:

```json
{
  "command": "docker",
  "args": ["run", "-i", "--rm", "shodan-mcp:latest"],
  "env": {
    "SHODAN_API_KEY": "your-api-key-here"
  }
}
```

## Security Notes

1. **Use `:ro` mounts** - Always use read-only mounts unless the tool needs to write
2. **Don't mount secrets** - Never mount `~/.ssh`, `~/.gnupg`, or credential files
3. **Limit scope** - Mount only the specific directories needed
4. **Network isolation** - MCPs run with default Docker networking
5. **Non-root** - All MCPs run as non-root user (UID 1000)
