# Waybackurls MCP Server

A Model Context Protocol server that fetches URLs from the Wayback Machine using [waybackurls](https://github.com/tomnomnom/waybackurls) by @tomnomnom.

## Tools

| Tool | Description |
|------|-------------|
| `fetch_wayback_urls` | Fetch all archived URLs for a domain from the Wayback Machine |
| `get_fetch_results` | Retrieve results from a previous fetch |
| `list_active_fetches` | Show currently running fetches |

## Features

- **Historical URL Discovery**: Find all URLs that were ever archived for a domain
- **Subdomain Support**: Optionally include or exclude subdomains
- **Statistics**: Automatic analysis of discovered URLs (extensions, subdomains, path depth)
- **Timestamp Support**: Show when URLs were archived (optional)
- **Efficient Storage**: Results are cached and can be retrieved later

## Use Cases

- **Reconnaissance**: Discover old endpoints and paths that may still exist
- **Asset Discovery**: Find forgotten subdomains and resources
- **Attack Surface Mapping**: Identify historical attack vectors
- **Content Discovery**: Locate archived files and directories
- **API Enumeration**: Find old API endpoints that may still be active

## Docker

### Build

```bash
docker build -t waybackurls-mcp .
```

### Run

```bash
docker run --rm -i waybackurls-mcp
```

### With persistent storage

```bash
docker run --rm -i \
  -v /path/to/output:/app/output \
  waybackurls-mcp
```

## Claude Desktop Configuration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "waybackurls": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "waybackurls-mcp"]
    }
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WAYBACKURLS_OUTPUT_DIR` | `/app/output` | Results directory |
| `WAYBACKURLS_TIMEOUT` | `300` | Default timeout (seconds) |
| `WAYBACKURLS_MAX_CONCURRENT` | `3` | Max concurrent fetches |

## Example Usage

### Basic URL fetch

```
Fetch wayback machine URLs for example.com
```

### With subdomains

```
Fetch wayback URLs for example.com including all subdomains
```

### Exclude subdomains

```
Fetch wayback URLs for example.com but exclude subdomains
```

### With timestamps

```
Fetch wayback URLs for example.com with archive dates
```

### Get previous results

```
Get the results of fetch abc12345 with URLs included
```

## Tool Details

### fetch_wayback_urls

Fetches all URLs from the Wayback Machine for a given domain.

**Parameters:**
- `domain` (required): Domain to fetch URLs for (e.g., example.com)
- `get_subs`: Also fetch subdomains (*.example.com)
- `no_subs`: Don't include subdomains, only exact domain
- `dates`: Show timestamps for when URLs were archived
- `include_urls`: Include actual URLs in response (default: true)
- `limit`: Maximum URLs to return (default: 100)
- `timeout`: Timeout in seconds (default: 300)

**Returns:**
- `fetch_id`: Unique identifier for this fetch
- `domain`: Domain that was fetched
- `status`: completed, running, failed, timeout, or error
- `total_urls`: Total number of URLs found
- `stats`: URL analysis including:
  - Extensions breakdown
  - Subdomains breakdown
  - Path depth distribution
  - HTTP vs HTTPS count
  - URLs with parameters count
- `urls`: Array of discovered URLs (if include_urls=true)

### get_fetch_results

Retrieve results from a previous fetch.

**Parameters:**
- `fetch_id` (required): Fetch ID from a previous operation
- `include_urls`: Include URLs in response
- `limit`: Maximum URLs to return

### list_active_fetches

Lists currently running fetches with their start times.

## Statistics

The server automatically analyzes discovered URLs and provides:

- **By Extension**: Count of URLs by file type (php, html, js, etc.)
- **By Subdomain**: Distribution of URLs across subdomains
- **By Path Depth**: How deep URLs are nested
- **Protocols**: HTTP vs HTTPS breakdown
- **Parameters**: Count of URLs with query parameters

## Security Notice

Waybackurls fetches publicly available data from the Internet Archive's Wayback Machine. This tool is designed for reconnaissance and OSINT activities. Always ensure you have permission to test the targets you discover.

## Common Patterns

### Finding old admin panels

```
Fetch wayback URLs for target.com and look for admin, login, or dashboard paths
```

### Discovering API endpoints

```
Fetch wayback URLs for api.example.com to find historical API routes
```

### Subdomain enumeration

```
Fetch wayback URLs for example.com with subdomains enabled
```

## Tips

1. **Large domains**: May return thousands of URLs and take several minutes
2. **Timeout**: Increase timeout for large domains (e.g., 600 seconds)
3. **Filtering**: Use the statistics to identify interesting URL patterns
4. **Subdomains**: Enable `get_subs` to discover forgotten subdomains
5. **Timestamps**: Use `dates=true` to see when content was archived

## Limitations

- Depends on what the Wayback Machine has archived
- Some domains may have robots.txt blocking archival
- Rate limited by the Wayback Machine API
- Very large domains may take significant time

## Credit

This MCP server wraps the excellent [waybackurls](https://github.com/tomnomnom/waybackurls) tool by [@tomnomnom](https://twitter.com/tomnomnom).

## License

MIT
