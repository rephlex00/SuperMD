FROM python:3.12-slim

# Install system dependencies
# PyMuPDF and Pillow might need build dependencies, though wheels often exist for slim.
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
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY config/docker-jobs.yaml ./config/docker-jobs.yaml

# Install the application
RUN pip install --no-cache-dir .

# Create directory structure for mounts
RUN mkdir -p /data/in /data/out /config

# Set environment variables
ENV SN2MD_DEFAULT_INPUT=/data/in
ENV SN2MD_DEFAULT_OUTPUT=/data/out
ENV PYTHONUNBUFFERED=1

# Default command
ENTRYPOINT ["sn2md-cli"]
CMD ["watch", "--config", "/app/config/docker-jobs.yaml", "--jobs", "1"]
