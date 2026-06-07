/** Settings model, defaults, and the settings tab UI. */
import { App, PluginSettingTab, Setting, Notice } from 'obsidian';
import type SuperMDPlugin from './main';
import {
  DEFAULT_NOTE_TITLE_PROMPT,
  DEFAULT_OUTPUT_FILENAME_TEMPLATE,
  DEFAULT_PROMPT,
  DEFAULT_TEMPLATE,
  DEFAULT_TITLE_PROMPT,
} from './config/defaults';

export type AttachmentMode = 'embed-note' | 'extract-png';

export interface SuperMDSettings {
  // LLM
  baseUrl: string;
  model: string;
  prompt: string;
  template: string;
  titlePrompt: string;
  noteTitlePrompt: string;
  // Output
  outputFolder: string;
  outputFilenameTemplate: string;
  attachmentFolder: string;
  attachmentMode: AttachmentMode;
  cooldownMs: number;
  // Triggers
  autoConvert: boolean;
  watchFolder: string;
  // Cloud
  cloudEmail: string;
  cloudRemotePath: string;
  cloudLocalFolder: string;
  cloudAutoPoll: boolean;
  cloudPollIntervalMin: number;
}

export const DEFAULT_SETTINGS: SuperMDSettings = {
  baseUrl: 'https://api.openai.com/v1',
  model: 'gpt-4o-mini',
  prompt: DEFAULT_PROMPT,
  template: DEFAULT_TEMPLATE,
  titlePrompt: DEFAULT_TITLE_PROMPT,
  noteTitlePrompt: DEFAULT_NOTE_TITLE_PROMPT,
  outputFolder: 'SuperMD',
  outputFilenameTemplate: DEFAULT_OUTPUT_FILENAME_TEMPLATE,
  attachmentFolder: 'SuperMD/attachments',
  attachmentMode: 'embed-note',
  cooldownMs: 1000,
  autoConvert: false,
  watchFolder: '',
  cloudEmail: '',
  cloudRemotePath: '/Note',
  cloudLocalFolder: 'Supernote',
  cloudAutoPoll: false,
  cloudPollIntervalMin: 15,
};

export class SuperMDSettingTab extends PluginSettingTab {
  constructor(app: App, private plugin: SuperMDPlugin) {
    super(app, plugin);
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();
    const s = this.plugin.settings;

    containerEl.createEl('h2', { text: 'LLM' });

    new Setting(containerEl)
      .setName('API base URL')
      .setDesc('OpenAI-compatible endpoint (works with OpenAI, Anthropic-compatible gateways, local servers).')
      .addText((t) => t.setValue(s.baseUrl).onChange(async (v) => { s.baseUrl = v.trim(); await this.plugin.saveSettings(); }));

    new Setting(containerEl)
      .setName('Model')
      .addText((t) => t.setValue(s.model).onChange(async (v) => { s.model = v.trim(); await this.plugin.saveSettings(); }));

    new Setting(containerEl)
      .setName('API key')
      .setDesc(this.plugin.secrets.usingKeychain ? 'Stored in your OS keychain.' : 'Stored locally (keychain unavailable).')
      .addText((t) => {
        t.inputEl.type = 'password';
        t.setPlaceholder('sk-…');
        this.plugin.secrets.get('llm.apiKey').then((v) => t.setValue(v ? '••••••••' : ''));
        t.onChange(async (v) => { if (v && v !== '••••••••') await this.plugin.secrets.set('llm.apiKey', v.trim()); });
      });

    new Setting(containerEl)
      .setName('Page prompt')
      .setDesc('Use {context} for the rolling previous-page context.')
      .addTextArea((t) => { t.setValue(s.prompt); t.inputEl.rows = 6; t.onChange(async (v) => { s.prompt = v; await this.plugin.saveSettings(); }); });

    new Setting(containerEl)
      .setName('Note-title prompt (optional)')
      .setDesc('If set, generates a {{title}} from the transcription. Use {markdown} for the content.')
      .addTextArea((t) => { t.setValue(s.noteTitlePrompt); t.inputEl.rows = 2; t.onChange(async (v) => { s.noteTitlePrompt = v; await this.plugin.saveSettings(); }); });

    new Setting(containerEl)
      .setName('Cooldown (ms)')
      .setDesc('Delay between page LLM calls to avoid rate limits.')
      .addText((t) => t.setValue(String(s.cooldownMs)).onChange(async (v) => { s.cooldownMs = Math.max(0, Number(v) || 0); await this.plugin.saveSettings(); }));

    containerEl.createEl('h2', { text: 'Output' });

    new Setting(containerEl)
      .setName('Attachment mode')
      .setDesc('Embed the original .note (rendered live), or extract per-page PNG attachments.')
      .addDropdown((d) =>
        d
          .addOption('embed-note', 'Embed original .note')
          .addOption('extract-png', 'Extract PNG attachments')
          .setValue(s.attachmentMode)
          .onChange(async (v) => { s.attachmentMode = v as AttachmentMode; await this.plugin.saveSettings(); }),
      );

    new Setting(containerEl)
      .setName('Output folder')
      .setDesc('Vault folder for generated .md files (template tokens allowed).')
      .addText((t) => t.setValue(s.outputFolder).onChange(async (v) => { s.outputFolder = v.trim(); await this.plugin.saveSettings(); }));

    new Setting(containerEl)
      .setName('Output filename template')
      .addText((t) => t.setValue(s.outputFilenameTemplate).onChange(async (v) => { s.outputFilenameTemplate = v.trim(); await this.plugin.saveSettings(); }));

    new Setting(containerEl)
      .setName('Attachment folder')
      .setDesc('Used only in extract-PNG mode.')
      .addText((t) => t.setValue(s.attachmentFolder).onChange(async (v) => { s.attachmentFolder = v.trim(); await this.plugin.saveSettings(); }));

    containerEl.createEl('h2', { text: 'Auto-convert' });

    new Setting(containerEl)
      .setName('Auto-convert new/changed .note files')
      .addToggle((t) => t.setValue(s.autoConvert).onChange(async (v) => { s.autoConvert = v; await this.plugin.saveSettings(); }));

    new Setting(containerEl)
      .setName('Watch folder')
      .setDesc('Limit auto-convert to this vault folder (blank = whole vault).')
      .addText((t) => t.setValue(s.watchFolder).onChange(async (v) => { s.watchFolder = v.trim(); await this.plugin.saveSettings(); }));

    containerEl.createEl('h2', { text: 'Supernote Cloud' });

    new Setting(containerEl)
      .setName('Account email')
      .addText((t) => t.setValue(s.cloudEmail).onChange(async (v) => { s.cloudEmail = v.trim(); await this.plugin.saveSettings(); }));

    new Setting(containerEl)
      .setName('Password')
      .setDesc('Stored in your OS keychain (used to obtain/refresh the access token).')
      .addText((t) => {
        t.inputEl.type = 'password';
        this.plugin.secrets.get('cloud.password').then((v) => t.setValue(v ? '••••••••' : ''));
        t.onChange(async (v) => { if (v && v !== '••••••••') await this.plugin.secrets.set('cloud.password', v); });
      });

    new Setting(containerEl)
      .setName('Remote path')
      .addText((t) => t.setValue(s.cloudRemotePath).onChange(async (v) => { s.cloudRemotePath = v.trim() || '/Note'; await this.plugin.saveSettings(); }));

    new Setting(containerEl)
      .setName('Local folder')
      .setDesc('Vault folder where downloaded .note files are saved.')
      .addText((t) => t.setValue(s.cloudLocalFolder).onChange(async (v) => { s.cloudLocalFolder = v.trim(); await this.plugin.saveSettings(); }));

    new Setting(containerEl)
      .setName('Auto-poll')
      .setDesc('Periodically sync while Obsidian is open.')
      .addToggle((t) => t.setValue(s.cloudAutoPoll).onChange(async (v) => { s.cloudAutoPoll = v; await this.plugin.saveSettings(); this.plugin.reschedulePoll(); }));

    new Setting(containerEl)
      .setName('Poll interval (minutes)')
      .addText((t) => t.setValue(String(s.cloudPollIntervalMin)).onChange(async (v) => { s.cloudPollIntervalMin = Math.max(1, Number(v) || 15); await this.plugin.saveSettings(); this.plugin.reschedulePoll(); }));

    new Setting(containerEl)
      .setName('Sync now')
      .setDesc('Log in if needed and pull .note files from Supernote Cloud.')
      .addButton((b) => b.setButtonText('Sync from Supernote Cloud').setCta().onClick(async () => {
        b.setDisabled(true);
        try { await this.plugin.cloudSync(true); } catch (e) { new Notice(`SuperMD: ${(e as Error).message}`); } finally { b.setDisabled(false); }
      }));

    new Setting(containerEl)
      .setName('Sign out')
      .setDesc('Clear the stored Supernote Cloud access token.')
      .addButton((b) => b.setButtonText('Clear token').onClick(async () => {
        await this.plugin.secrets.set('cloud.token', '');
        new Notice('SuperMD: cleared Supernote Cloud token.');
      }));
  }
}
