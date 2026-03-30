# Rust Analyzer MCP Server
# Static analysis of Rust source code for fuzz target identification

FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/FuzzingLabs/mcp-security-hub"
LABEL org.opencontainers.image.description="Rust Analyzer MCP Server - Identifies fuzzable entry points, unsafe blocks, and CVEs"
LABEL org.opencontainers.image.licenses="MIT"

RUN groupadd -g 1000 mcpuser && \
    useradd -u 1000 -g mcpuser -m mcpuser

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    tini \
    curl \
    build-essential \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Rust stable toolchain (globally accessible)
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH="/usr/local/cargo/bin:${PATH}"
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    --default-toolchain stable --profile minimal \
    && chmod -R a+rX /usr/local/rustup /usr/local/cargo

# Install cargo-audit
RUN cargo install cargo-audit --locked \
    && chmod -R a+rX /usr/local/cargo

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=mcpuser:mcpuser server.py .

RUN mkdir -p /data && chown -R mcpuser:mcpuser /data /app

USER mcpuser

ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD pgrep -f "python.*server.py" > /dev/null || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "server.py"]
