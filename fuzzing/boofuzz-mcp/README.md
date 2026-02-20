# Boofuzz MCP Server

Model Context Protocol (MCP) server for **network protocol fuzzing using Boofuzz**. This server allows you to create, run, and manage Boofuzz fuzzing scripts remotely via MCP, with support for asynchronous execution, result retrieval, and script management.

Transport: **stdio** (no HTTP server).

---

## Tools

| Tool                     | Description                                                                                     |
|--------------------------|-------------------------------------------------------------------------------------------------|
| `boofuzz_create_script`  | Create and save a Boofuzz Python script on the server. The script should accept `target_host` and `target_port` as arguments or environment variables. |
| `boofuzz_run_fuzzer`     | Execute a saved Boofuzz fuzzer script against a target. Runs asynchronously with a timeout.     |
| `boofuzz_list_scripts`   | List all saved fuzzer scripts.                                                                   |
| `boofuzz_get_results`    | Retrieve the crash log or audit results from a fuzzing session.                                |

---

## Docker

### Build

```bash
docker build -t boofuzz-mcp .
```

### Run

```bash
docker run --rm -i boofuzz-mcp
```

### With Volumes

Mount your script and results directories for persistence:

```bash
docker run --rm -i \
  -v /path/to/scripts:/app/scripts \
  -v /path/to/results:/app/results \
  boofuzz-mcp
```

---

## Claude Desktop Configuration

To integrate with Claude Desktop, add the following to your configuration:

```json
{
  "mcpServers": {
    "boofuzz": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "/path/to/scripts:/app/scripts",
        "-v", "/path/to/results:/app/results",
        "boofuzz-mcp\:latest"
      ]
    }
  }
}
```

---

## Environment Variables

| Variable               | Default          | Description                                      |
|------------------------|------------------|--------------------------------------------------|
| `BOOFUZZ_SCRIPT_DIR`   | `/app/scripts`   | Directory for storing Boofuzz fuzzer scripts.    |
| `BOOFUZZ_RESULTS_DIR`  | `/app/results`   | Directory for storing fuzzing session results.   |

---

## Example Usage

### Create a Fuzzer Script

```plaintext
Run boofuzz_create_script with script_name="ftp_fuzzer", script_content="<your_boofuzz_script_here>", and description="Fuzzes an FTP server."
```

### Run a Fuzzer Script

```plaintext
Run boofuzz_run_fuzzer with script_name="ftp_fuzzer", target_host="192.168.1.100", target_port=21, and timeout=120
```

### List Saved Scripts

```plaintext
Run boofuzz_list_scripts
```

### Retrieve Results

```plaintext
Run boofuzz_get_results with session_id="abc12345"
```

---

## Notes

- Scripts must accept `TARGET_HOST` and `TARGET_PORT` as environment variables or arguments.
- Results are saved in the `results_dir` and can be retrieved using the `session_id` returned by `boofuzz_run_fuzzer`.
- The server sanitizes script names to prevent path traversal.
