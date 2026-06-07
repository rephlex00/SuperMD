/**
 * Secret storage wrapper. Prefers Obsidian's SecretStorage (OS keychain) when
 * available; otherwise falls back to a JSON file in the plugin dir (documented as
 * plaintext). Used for the LLM API key and the Supernote Cloud password/token.
 *
 * NOTE: the exact SecretStorage API is accessed defensively — verify against the
 * installed Obsidian version; the fallback keeps the plugin working regardless.
 */
import { Plugin } from 'obsidian';

interface SecretStorageLike {
  getSecret(key: string): Promise<string | null | undefined>;
  setSecret(key: string, value: string): Promise<void>;
  deleteSecret?(key: string): Promise<void>;
}

export class SecretStore {
  constructor(private plugin: Plugin) {}

  private get backend(): SecretStorageLike | null {
    const app = this.plugin.app as unknown as { secretStorage?: SecretStorageLike };
    return app.secretStorage && typeof app.secretStorage.getSecret === 'function'
      ? app.secretStorage
      : null;
  }

  get usingKeychain(): boolean {
    return this.backend !== null;
  }

  private dir(): string {
    return this.plugin.manifest.dir ?? `${this.plugin.app.vault.configDir}/plugins/${this.plugin.manifest.id}`;
  }

  private fallbackPath(): string {
    return `${this.dir()}/secrets.json`;
  }

  async get(key: string): Promise<string> {
    const backend = this.backend;
    if (backend) {
      try {
        const v = await backend.getSecret(`supermd:${key}`);
        if (v != null) return v;
      } catch {
        /* fall through to file */
      }
    }
    const data = await this.readFallback();
    return data[key] ?? '';
  }

  async set(key: string, value: string): Promise<void> {
    const backend = this.backend;
    if (backend) {
      try {
        await backend.setSecret(`supermd:${key}`, value);
        return;
      } catch {
        /* fall through to file */
      }
    }
    const data = await this.readFallback();
    data[key] = value;
    await this.writeFallback(data);
  }

  private async readFallback(): Promise<Record<string, string>> {
    try {
      const adapter = this.plugin.app.vault.adapter;
      const path = this.fallbackPath();
      if (await adapter.exists(path)) return JSON.parse(await adapter.read(path));
    } catch {
      /* ignore */
    }
    return {};
  }

  private async writeFallback(data: Record<string, string>): Promise<void> {
    try {
      await this.plugin.app.vault.adapter.write(this.fallbackPath(), JSON.stringify(data));
    } catch {
      /* ignore */
    }
  }
}
