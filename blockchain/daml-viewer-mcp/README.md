# daml-viewer MCP Server

Model Context Protocol server that exposes the
[daml-viewer](https://github.com/FuzzingLabs/daml-viewer) CLI for DAML
access-control table generation.

Transport: stdio (no HTTP server).

## Tools

| Tool | Description |
|------|-------------|
| `damlviewer_generate_table` | Generate a DAML access-control markdown table from a project directory or `.daml` file |
| `get_run_results` | Retrieve results from a previous run |
| `list_runs` | List completed runs |
| `list_active_runs` | List currently running jobs |

## Docker

### Build

```bash
docker build -t daml-viewer-mcp .
```

Optional: pin a specific `daml-viewer` branch/tag/commit:

```bash
docker build -t daml-viewer-mcp --build-arg DAML_VIEWER_REF=master .
```

### Run

```bash
docker run --rm -i daml-viewer-mcp
```

### With volumes

Mount input DAML projects under `/app/uploads` and collect outputs under `/app/output`:

```bash
docker run --rm -i \
  -v /path/to/daml-projects:/app/uploads:ro \
  -v /path/to/output:/app/output \
  daml-viewer-mcp
```

## Claude Desktop Configuration

```json
{
  "mcpServers": {
    "damlviewer": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "/path/to/daml-projects:/app/uploads:ro",
        "-v", "/path/to/output:/app/output",
        "daml-viewer-mcp:latest"
      ]
    }
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DAML_VIEWER_OUTPUT_DIR` | `/app/output` | Directory for per-run output |
| `DAML_VIEWER_UPLOAD_DIR` | `/app/uploads` | Directory for mounted input projects/files |
| `DAML_VIEWER_TIMEOUT` | `120` | Default command timeout in seconds |
| `DAML_VIEWER_MAX_CONCURRENT` | `3` | Maximum concurrent runs |
| `DAML_VIEWER_MAX_FILE_SIZE` | `104857600` | Max allowed input file size (100 MB) |
| `DAML_VIEWER_ALLOW_ANY_PATH` | `0` | If `1`, disables path restrictions |
| `DAML_VIEWER_BIN` | `daml-viewer` | Path to the `daml-viewer` executable |
| `DAML_VIEWER_MAX_TEXT_OUTPUT` | `20000` | Max chars stored from stdout/stderr |
| `DAML_VIEWER_MAX_TABLE_PREVIEW` | `20000` | Max chars returned for table preview |

## Example Usage

Analyze a DAML project mounted under uploads:

```
Generate a DAML table for /app/uploads/my-daml-project and show me a preview
```

Generate cleared output and store it explicitly:

```
Run damlviewer_generate_table on /app/uploads/my-daml-project with cleared=true and output=/app/output/my-report.md
```
