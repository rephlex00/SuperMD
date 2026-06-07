/**
 * Recursive Supernote Cloud → vault sync, ported from sync.py:sync_directory.
 * Downloads .note files into a vault folder, mirroring the remote structure,
 * skipping existing files and writing atomically (temp → rename).
 */
import { App, normalizePath } from 'obsidian';
import { CloudFile, SNClient } from './snclient';

export interface SyncResult {
  downloaded: number;
  skipped: number;
}

function isSuspicious(name: string): boolean {
  return name.includes('/') || name.includes('\\') || name.startsWith('.');
}

async function ensureFolder(app: App, path: string): Promise<void> {
  const p = normalizePath(path);
  if (!p || p === '.' || p === '/') return;
  if (!(await app.vault.adapter.exists(p))) {
    await app.vault.adapter.mkdir(p);
  }
}

function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  const ab = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(ab).set(bytes);
  return ab;
}

async function processItems(
  app: App,
  client: SNClient,
  items: CloudFile[],
  localFolder: string,
  result: SyncResult,
): Promise<void> {
  for (const item of items) {
    if (item.isFolder) {
      const childLocal = normalizePath(`${localFolder}/${item.name}`);
      await ensureFolder(app, childLocal);
      await processItems(app, client, await client.ls(item.id), childLocal, result);
      continue;
    }
    if (!item.name.toLowerCase().endsWith('.note') || isSuspicious(item.name)) continue;

    const target = normalizePath(`${localFolder}/${item.name}`);
    if (await app.vault.adapter.exists(target)) {
      result.skipped += 1;
      continue;
    }
    const bytes = await client.download(item.id);
    const tmp = normalizePath(`${localFolder}/.supermd-tmp-${Date.now()}-${item.name}`);
    await app.vault.adapter.writeBinary(tmp, toArrayBuffer(bytes));
    await app.vault.adapter.rename(tmp, target);
    result.downloaded += 1;
  }
}

export async function syncCloudFolder(
  app: App,
  client: SNClient,
  remotePath: string,
  localFolder: string,
): Promise<SyncResult> {
  const result: SyncResult = { downloaded: 0, skipped: 0 };
  await ensureFolder(app, localFolder);
  const rootItems = await client.lsPath(remotePath);
  await processItems(app, client, rootItems, localFolder, result);
  return result;
}
