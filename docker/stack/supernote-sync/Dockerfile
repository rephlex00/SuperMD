# ── Supernote Cloud Sync ─────────────────────────────────────────────────────
# Periodically downloads .note files from Supernote Cloud using the unofficial
# sncloud Python library.  Authentication credentials are read from Docker
# secrets at /run/secrets/.
FROM python:3.12-slim

RUN pip install --no-cache-dir sncloud==0.2.1 \
    && apt-get update && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1000 sncloud && \
    useradd -u 1000 -g sncloud -s /bin/sh -d /home/sncloud -m sncloud

RUN mkdir -p /notes

COPY entrypoint.sh /entrypoint.sh
COPY sync.py /sync.py
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "-u", "/sync.py"]
