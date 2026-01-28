# SQLMap MCP Server

SQL injection detection and exploitation MCP server using [SQLMap](https://sqlmap.org/).

## Tools

| Tool | Description |
|------|-------------|
| `sql_scan` | Scan URL for SQL injection vulnerabilities |
| `sql_enumerate` | Enumerate databases, tables, columns |
| `sql_dump` | Dump data from database tables |
| `sql_test` | Quick injection test for a parameter |
| `get_scan_results` | Retrieve previous results |
| `list_active_scans` | Show running scans |

## Usage

### Docker

```bash
docker build -t sqlmap-mcp .
docker run -it --rm sqlmap-mcp
```

### Claude Desktop

```json
{
  "mcpServers": {
    "sqlmap": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "sqlmap-mcp:latest"]
    }
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SQLMAP_OUTPUT_DIR` | `/app/output` | Directory for scan output |
| `SQLMAP_TIMEOUT` | `300` | Default scan timeout (seconds) |
| `SQLMAP_MAX_CONCURRENT` | `2` | Max concurrent scans |
| `SQLMAP_LEVEL` | `1` | Default test level (1-5) |
| `SQLMAP_RISK` | `1` | Default risk level (1-3) |

## Examples

### Basic Scan
```
Scan http://example.com/page?id=1 for SQL injection
```

### Enumerate Databases
```
List databases on http://example.com/page?id=1
```

### Dump Table
```
Dump the users table from the main database
```

## Security Notice

**For authorized testing only.** SQL injection testing should only be performed on systems you own or have explicit permission to test.

## License

MIT
