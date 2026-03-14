# ── Obsidian Headless Sync ───────────────────────────────────────────────────
# Runs the official obsidian-headless CLI to continuously sync a vault via
# Obsidian Sync.  Includes gnome-keyring and D-Bus for the keychain workaround
# required on headless Linux (the ob CLI stores credentials in libsecret).
FROM node:22-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        gosu \
        gnome-keyring \
        dbus-x11 \
        libsecret-1-0 \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g obsidian-headless && npm cache clean --force

RUN groupadd -g 1000 obsidian && \
    useradd -u 1000 -g obsidian -s /bin/sh -d /home/obsidian -m obsidian

RUN mkdir -p /vault

COPY entrypoint.sh /entrypoint.sh
COPY sync.sh /sync.sh
RUN chmod +x /entrypoint.sh /sync.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/sync.sh"]
