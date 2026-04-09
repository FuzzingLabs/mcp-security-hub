FROM python:3.12-alpine AS production

LABEL org.opencontainers.image.source="https://github.com/FuzzingLabs/mcp-security-hub"
LABEL org.opencontainers.image.description="ATR MCP Server - Agent Threat Rules scanner"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.vendor="FuzzingLabs"

RUN addgroup -g 1000 mcpuser && \
    adduser -D -u 1000 -G mcpuser mcpuser

RUN apk add --no-cache ca-certificates tini && rm -rf /var/cache/apk/*

WORKDIR /app

COPY --chown=mcpuser:mcpuser requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=mcpuser:mcpuser . .

USER mcpuser

ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f "python.*server.py" > /dev/null || exit 1

EXPOSE 3000

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["python", "server.py"]
