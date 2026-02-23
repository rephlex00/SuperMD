FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libcairo2-dev \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    libtiff-dev \
    tk-dev \
    tcl-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy project specification
COPY pyproject.toml uv.lock ./

# Install dependencies (without the project itself)
RUN uv sync --frozen --no-install-project --no-dev

# Copy source code and config
COPY src/ ./src/
COPY config/ ./config/
COPY README.md ./
COPY entrypoint.sh /usr/local/bin/entrypoint.sh

# Install the project
RUN uv sync --frozen --no-dev --no-editable

# Create directory structure for mounts
RUN mkdir -p /data/in /data/out /config && \
    chmod +x /usr/local/bin/entrypoint.sh

# Document expected volumes
VOLUME ["/data/in", "/data/out", "/config"]

# Set environment variables
# OPENAI_API_KEY and OPENAI_MODEL are intentionally NOT set here.
# Pass them at runtime via env_file or docker-compose environment.
ENV SN2MD_DEFAULT_INPUT=/data/in
ENV SN2MD_DEFAULT_OUTPUT=/data/out
ENV SN2MD_WATCH_DELAY=30.0
ENV PYTHONUNBUFFERED=1
ENV PUID=1000
ENV PGID=1000

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Default command
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sn2md-cli", "watch", "--jobs", "1"]
