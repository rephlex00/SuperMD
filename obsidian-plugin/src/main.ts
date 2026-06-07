import { debounce, Menu, Notice, Plugin, TAbstractFile, TFile } from 'obsidian';
import { DEFAULT_SETTINGS, SuperMDSettings, SuperMDSettingTab } from './settings';
import { SecretStore } from './secret';
import { MetadataStore } from './store/metadata';
import { ConversionSkipped, ConvertOptions, convertNoteFile } from './pipeline/convert';
import { registerNoteEmbeds } from './view/noteEmbed';
import { NoteFileView, VIEW_TYPE_NOTE } from './view/noteView';
import { CloudError, SNClient } from './cloud/snclient';
import { syncCloudFolder } from './cloud/sync';
import { OtpModal } from './cloud/otpModal';

export default class SuperMDPlugin extends Plugin {
  settings!: SuperMDSettings;
  secrets!: SecretStore;
  meta!: MetadataStore;

  private pollHandle: number | null = null;
  private chain: Promise<void> = Promise.resolve();
  private pending = new Set<string>();
  private scheduleAuto = debounce(() => void this.flushAuto(), 1500, true);

  async onload(): Promise<void> {
    this.secrets = new SecretStore(this);
    this.meta = new MetadataStore(this);
    await this.loadSettings();
    await this.meta.load();

    // Direct .note viewing.
    this.registerView(VIEW_TYPE_NOTE, (leaf) => new NoteFileView(leaf));
    try {
      this.registerExtensions(['note'], VIEW_TYPE_NOTE);
    } catch {
      /* another plugin already owns the .note extension */
    }
    registerNoteEmbeds(this);

    // Manual triggers.
    this.addRibbonIcon('pencil', 'SuperMD: convert active .note', () => this.convertActive('transcribe'));
    this.addCommand({ id: 'convert-active', name: 'Convert active .note to Markdown', callback: () => this.convertActive('transcribe') });
    this.addCommand({ id: 'map-active', name: 'Map active .note for viewing only', callback: () => this.convertActive('view-only') });
    this.addCommand({ id: 'cloud-sync', name: 'Sync from Supernote Cloud', callback: () => void this.cloudSync(true) });

    this.registerEvent(
      this.app.workspace.on('file-menu', (menu: Menu, file: TAbstractFile) => {
        if (file instanceof TFile && file.extension === 'note') {
          menu.addItem((i) => i.setTitle('SuperMD: convert to Markdown').setIcon('pencil').onClick(() => void this.safeConvert(file, { mode: 'transcribe' })));
          menu.addItem((i) => i.setTitle('SuperMD: map for viewing only').setIcon('image').onClick(() => void this.safeConvert(file, { mode: 'view-only' })));
        }
      }),
    );

    // Auto-convert on vault changes (debounced).
    this.registerEvent(this.app.vault.on('create', (f) => this.onVaultChange(f)));
    this.registerEvent(this.app.vault.on('modify', (f) => this.onVaultChange(f)));

    this.addSettingTab(new SuperMDSettingTab(this.app, this));
    this.reschedulePoll();
  }

  onunload(): void {
    if (this.pollHandle != null) {
      window.clearInterval(this.pollHandle);
      this.pollHandle = null;
    }
  }

  async loadSettings(): Promise<void> {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
  }

  async saveSettings(): Promise<void> {
    await this.saveData(this.settings);
  }

  private inWatch(path: string): boolean {
    const w = this.settings.watchFolder.trim();
    return !w || path === w || path.startsWith(w.endsWith('/') ? w : w + '/');
  }

  private onVaultChange(file: TAbstractFile): void {
    if (!this.settings.autoConvert) return;
    if (!(file instanceof TFile) || file.extension !== 'note') return;
    if (!this.inWatch(file.path)) return;
    this.pending.add(file.path);
    this.scheduleAuto();
  }

  private async flushAuto(): Promise<void> {
    const paths = [...this.pending];
    this.pending.clear();
    for (const p of paths) {
      const f = this.app.vault.getAbstractFileByPath(p);
      if (f instanceof TFile) await this.safeConvert(f, { mode: 'transcribe', notify: false });
    }
  }

  private convertActive(mode: 'transcribe' | 'view-only'): void {
    const f = this.app.workspace.getActiveFile();
    if (!f || f.extension !== 'note') {
      new Notice('SuperMD: open a .note file first.');
      return;
    }
    void this.safeConvert(f, { mode });
  }

  /** Serialize conversions so LLM calls and vault writes don't overlap. */
  safeConvert(file: TFile, opts: ConvertOptions): Promise<void> {
    this.chain = this.chain.then(async () => {
      try {
        const apiKey = await this.secrets.get('llm.apiKey');
        const out = await convertNoteFile(this.app, this.settings, apiKey, this.meta, file, opts);
        if (out === null && opts.notify !== false) new Notice(`SuperMD: ${file.name} unchanged — skipped.`);
      } catch (e) {
        if (e instanceof ConversionSkipped) {
          new Notice(`SuperMD: ${e.message}`);
        } else {
          console.error('SuperMD conversion error', e);
          new Notice(`SuperMD: failed to convert ${file.name}: ${(e as Error).message}`);
        }
      }
    });
    return this.chain;
  }

  reschedulePoll(): void {
    if (this.pollHandle != null) {
      window.clearInterval(this.pollHandle);
      this.pollHandle = null;
    }
    if (this.settings.cloudAutoPoll) {
      const ms = Math.max(1, this.settings.cloudPollIntervalMin) * 60000;
      this.pollHandle = window.setInterval(() => void this.cloudSync(false), ms);
      this.registerInterval(this.pollHandle);
    }
  }

  private async ensureCloudClient(interactive: boolean): Promise<SNClient | null> {
    const token = await this.secrets.get('cloud.token');
    if (token) return new SNClient(token);

    const email = this.settings.cloudEmail;
    const password = await this.secrets.get('cloud.password');
    if (!email || !password) {
      if (interactive) new Notice('SuperMD: set your Supernote Cloud email & password in settings.');
      return null;
    }

    const client = new SNClient();
    try {
      const t = await client.login(email, password);
      await this.secrets.set('cloud.token', t);
      return client;
    } catch (e) {
      if (e instanceof CloudError && e.code === 'E1760') {
        const timestamp = String(e.message).split(':')[1] ?? '';
        let validCodeKey = '';
        try {
          validCodeKey = await client.sendVerificationCode(email, timestamp);
        } catch {
          /* code may already have been sent */
        }
        const otp = await new OtpModal(this.app).openAndWait();
        if (!otp) return null;
        const t = await client.verifyOtp(email, otp, validCodeKey, timestamp);
        await this.secrets.set('cloud.token', t);
        return client;
      }
      throw e;
    }
  }

  async cloudSync(interactive: boolean): Promise<void> {
    let client = await this.ensureCloudClient(interactive);
    if (!client) return;
    const run = async (c: SNClient): Promise<void> => {
      const r = await syncCloudFolder(this.app, c, this.settings.cloudRemotePath, this.settings.cloudLocalFolder);
      if (interactive || r.downloaded) {
        new Notice(`SuperMD: cloud sync — ${r.downloaded} downloaded, ${r.skipped} skipped.`);
      }
    };
    try {
      await run(client);
    } catch (e) {
      const expired = e instanceof CloudError && (e.code === 'NO_TOKEN' || /401|403|token/i.test(e.message));
      if (expired) {
        await this.secrets.set('cloud.token', '');
        client = await this.ensureCloudClient(interactive);
        if (!client) return;
        try {
          await run(client);
        } catch (e2) {
          new Notice(`SuperMD cloud sync failed: ${(e2 as Error).message}`);
        }
      } else {
        new Notice(`SuperMD cloud sync failed: ${(e as Error).message}`);
      }
    }
  }
}
