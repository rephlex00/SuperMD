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
        python3 \
        make \
        g++ \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g obsidian-headless && npm cache clean --force

# Remove build tools no longer needed at runtime.
RUN apt-get purge -y --auto-remove python3 make g++ \
    && rm -rf /var/lib/apt/lists/*

RUN groupmod -n obsidian node && \
    usermod -l obsidian -d /home/obsidian -m node && \
    usermod -s /bin/sh obsidian

RUN mkdir -p /vault

COPY entrypoint.sh /entrypoint.sh
COPY sync.sh /sync.sh
RUN chmod +x /entrypoint.sh /sync.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/sync.sh"]
