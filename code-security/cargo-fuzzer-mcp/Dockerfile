FROM python:3.12-slim

# Install system deps + Rust nightly + cargo-fuzz
RUN apt-get update && apt-get install -y --no-install-recommends \
        tini curl build-essential pkg-config libssl-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
    | sh -s -- -y --default-toolchain nightly
ENV PATH="/root/.cargo/bin:${PATH}"

RUN cargo install cargo-fuzz --locked || true

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

# cargo-fuzz needs write access, keep root
ENTRYPOINT ["tini", "--"]
CMD ["python", "server.py"]
