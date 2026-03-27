# ── Stage 1: builder ─────────────────────────────────────────────────────────
# Compiles C extensions and installs all Python packages.
# Build tools (gcc, libcairo2-dev, pkg-config, uv) never reach the final image.
FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/

# pycairo (via svglib → rlpycairo → pycairo) must be compiled from source on
# aarch64 — no pre-built wheel exists. gcc + libcairo2-dev + pkg-config are
# only needed here; libcairo2 (the runtime .so) is installed in the final stage.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libcairo2-dev \
        pkg-config \
    && uv pip install --system --no-cache . \
    && rm -rf /var/lib/apt/lists/*

# Install LLM provider plugins. llm-ollama is already a package dependency.
# OpenAI is supported natively by llm without a plugin.
RUN llm install llm-gemini llm-claude-3

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim

# Runtime shared libraries only — build tools stay in the builder stage.
#   libpotrace0  required by potracer (supernotelib dependency)
#   libcairo2    required by pycairo at runtime
#   gosu         used by entrypoint.sh to drop privileges at startup
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpotrace0 \
    libcairo2 \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages and CLI entry points from the builder.
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/supermd /usr/local/bin/supermd
COPY --from=builder /usr/local/bin/llm /usr/local/bin/llm

# Create the supermd user. The actual UID/GID are applied at runtime by
# entrypoint.sh using the PUID/PGID environment variables, so the values
# here are just defaults that are immediately overwritten on first start.
RUN groupadd -g 1000 supermd && \
    useradd -u 1000 -g supermd -s /bin/sh -d /home/supermd -m supermd

# Default mount points — matched by config/supermd.docker.yaml
RUN mkdir -p /input /output /config

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# GUI port (only used when running the gui subcommand)
EXPOSE 8734

# Container starts as root so entrypoint.sh can adjust UID/GID, then drops
# to the supermd user before executing the main command.
ENTRYPOINT ["/entrypoint.sh"]

# Watch for new notes and convert them as they arrive.
# For one-shot batch processing, override with: supermd --config /config/supermd.yaml run
CMD ["supermd", "--config", "/config/supermd.yaml", "watch"]
