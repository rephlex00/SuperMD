# Supernote Private Cloud + sn2md + Obsidian Integration

This stack deploys a fully self-hosted Supernote environment integrated with `sn2md` for automatic Note conversion and Obsidian for note management.

## Features

-   **Supernote Private Cloud**: Self-hosted cloud for syncing your Supernote device.
-   **sn2md**: Automatically watches your cloud files, converts `.note` files to Markdown, and saves them to Obsidian.
-   **Obsidian**: Runs Obsidian in a container (accessible via web browser) to inspect and manage your converted notes.
-   **Data Persistence**: All data is stored locally in the `data/` directory.

## Prerequisites

-   Docker & Docker Compose installed.
-   `openssl` (for generating self-signed certificates).

## Directory Structure

The stack uses the following directory structure in the project root:

```text
data/
├── files/          # User files (notes, pdfs). Mapped to Supernote Cloud & sn2md input.
├── cert/           # SSL Certificates for Supernote Cloud's Nginx.
└── supernote/      # System data (Database, Redis, logs, conversion tools).
```

## Setup Instructions

### 1. Prepare Directory Structure

Create the necessary folders:

```bash
mkdir -p data/{files,cert,supernote}
```

### 2. Download Database Initialization File

Download the official SQL initialization file into the supernote data directory:

```bash
curl -o data/supernote/supernotedb.sql https://supernote-private-cloud.supernote.com/cloud/supernotedb.sql
```

### 3. Generate self-signed SSL Certificates

The Supernote Private Cloud requires SSL certificates to start its Nginx server. Generate a self-signed certificate:

```bash
openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 \
  -subj "/C=US/ST=State/L=City/O=Supernote/CN=supernote.local" \
  -keyout data/cert/server.key -out data/cert/server.crt
```

### 4. Configuration

Review the `sn-cloud.env` file. It contains default passwords and port configurations. You can modify these if needed, but the defaults work out-of-the-box.

### 5. Start the Stack

Run the stack using the specific compose file and environment file:

```bash
docker-compose --env-file sn-cloud.env -f docker-compose.sn-cloud.yml up -d
```

## Accessing Services

Once the containers are running (give them ~1 minute to initialize), you can access:

| Service | URL | Description |
| :--- | :--- | :--- |
| **Supernote Web Management** | [http://localhost:19072](http://localhost:19072) | Manage files, view sync status. |
| **Supernote HTTPS** | [https://localhost:19443](https://localhost:19443) | Secure endpoint (accept self-signed warning). |
| **Obsidian (VNC)** | [http://localhost:3000](http://localhost:3000) | Full desktop Obsidian interface in browser. |

### Syncing Your Device

1.  On your Supernote device, go to **Settings > Sync**.
2.  Select **Supernote Cloud** (or custom cloud if available in your firmware version).
3.  Enter the server address: `http://<your-computer-ip>:19072` (Note: Use your computer's LAN IP, not `localhost`, so the device can reach it).
4.  Use the port `18072` if prompted for a dedicated sync port.

### Automatic Conversion

1.  Upload or Sync a `.note` file to the Supernote Cloud.
2.  The file will appear in `data/files`.
3.  `sn2md` will automatically detect the new file, convert it to Markdown, and save it to the Obsidian Vault (`apps/sn2md`).
4.  Open [http://localhost:3000](http://localhost:3000) to see your note in Obsidian.

## Data Management

-   **Backups**: Backup the `data/` directory to save all your notes, database state, and configuration.
-   **Logs**:
    -   `docker-compose -f docker-compose.sn-cloud.yml logs -f sn2md`: View conversion logs.
    -   `docker-compose -f docker-compose.sn-cloud.yml logs -f supernote-service`: View cloud service logs.

## Troubleshooting

-   **Service Unreachable**: Ensure `data/cert/server.crt` and `server.key` exist. Nginx will fail to start without them.
-   **Permission Errors**: If `sn2md` complains about permissions, ensure the container user (PUID 1000) has access to `data/`. The entrypoint handles ownership of `data/out` automatically.
-   **"Platform mismatch" warning**: You may see warnings about `linux/amd64` images on ARM chips (M1/M2/M3 Macs). This is normal; Docker's emulation handles it, though it may be slightly slower.
