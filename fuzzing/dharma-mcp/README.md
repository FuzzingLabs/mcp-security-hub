# Dharma MCP Server

Model Context Protocol (MCP) server for **Dharma grammar-based fuzzing**. This server exposes Dharma’s grammar-based test case generation capabilities via MCP, enabling integration with tools like Claude Desktop.

Transport: **stdio** (no HTTP server).

---

## Tools

| Tool                     | Description                                                                                     |
|--------------------------|-------------------------------------------------------------------------------------------------|
| `dharma_generate`        | Generate test cases using a Dharma grammar file located on the server.                          |
| `dharma_generate_custom` | Generate test cases from a custom Dharma grammar provided as a string. Useful for dynamically generated grammars or quick testing without saving files. |

---

## Docker

### Build

```bash
docker build -t dharma-mcp .
```

### Run

```bash
docker run --rm -i dharma-mcp
```

### With Volumes

Mount your grammar files under `/app/grammars` and collect generated outputs under `/app/output`:

```bash
docker run --rm -i \
  -v /path/to/grammars:/app/grammars\:ro \
  -v /path/to/output:/app/output \
  dharma-mcp
```

---

## Claude Desktop Configuration

To integrate with Claude Desktop, add the following to your configuration:

```json
{
  "mcpServers": {
    "dharma": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "/path/to/grammars:/app/grammars\:ro",
        "-v", "/path/to/output:/app/output",
        "dharma-mcp\:latest"
      ]
    }
  }
}
```

---

## Environment Variables

| Variable               | Default          | Description                                      |
|------------------------|------------------|--------------------------------------------------|
| `DHARMA_GRAMMAR_DIR`   | `/app/grammars`  | Directory containing Dharma grammar files.       |

---

## Example Usage

### Generate Test Cases from a File

```plaintext
Generate 10 test cases using the grammar at /app/grammars/json.dg
```

### Generate Test Cases from a Custom Grammar

```plaintext
Run dharma_generate_custom with grammar_content="<grammar content here>" and count=5
```

### With Explicit Output

```plaintext
Run dharma_generate with grammar_path=/app/grammars/json.dg and count=5
```
