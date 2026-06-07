/**
 * Conversion metadata store (skip/protect), ported from supermd/metadata_db.py.
 * Persists a JSON map keyed by input file path in the plugin dir.
 */
import { Plugin } from 'obsidian';
import { sha1Hex } from '../util/hash';

export interface MetaEntry {
  inputPath: string;
  outputPath: string;
  inputHash: string;
  outputHash: string;
  images: string[];
}

export class MetadataStore {
  private data: Record<string, MetaEntry> = {};

  constructor(private plugin: Plugin) {}

  private dir(): string {
    return this.plugin.manifest.dir ?? `${this.plugin.app.vault.configDir}/plugins/${this.plugin.manifest.id}`;
  }

  private path(): string {
    return `${this.dir()}/metadata.json`;
  }

  async load(): Promise<void> {
    try {
      const adapter = this.plugin.app.vault.adapter;
      if (await adapter.exists(this.path())) {
        this.data = JSON.parse(await adapter.read(this.path()));
      }
    } catch {
      this.data = {};
    }
  }

  private async save(): Promise<void> {
    try {
      await this.plugin.app.vault.adapter.write(this.path(), JSON.stringify(this.data));
    } catch {
      /* ignore */
    }
  }

  get(inputPath: string): MetaEntry | undefined {
    return this.data[inputPath];
  }

  async set(entry: MetaEntry): Promise<void> {
    this.data[entry.inputPath] = entry;
    await this.save();
  }

  hash(input: ArrayBuffer | Uint8Array): Promise<string> {
    return sha1Hex(input);
  }
}
