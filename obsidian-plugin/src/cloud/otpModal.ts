/** Modal that collects the Supernote Cloud E1760 verification code. */
import { App, Modal, Setting } from 'obsidian';

export class OtpModal extends Modal {
  private value = '';
  private settled = false;
  private resolver: ((value: string | null) => void) | null = null;

  constructor(app: App) {
    super(app);
  }

  openAndWait(): Promise<string | null> {
    return new Promise((resolve) => {
      this.resolver = resolve;
      this.open();
    });
  }

  private settle(value: string | null): void {
    if (this.settled) return;
    this.settled = true;
    this.resolver?.(value);
  }

  onOpen(): void {
    const { contentEl } = this;
    contentEl.createEl('h3', { text: 'Supernote Cloud verification' });
    contentEl.createEl('p', {
      text: 'A new-device verification code was emailed to you. Enter it below.',
    });
    new Setting(contentEl).setName('Verification code').addText((text) => {
      text.inputEl.addClass('supermd-otp-input');
      text.onChange((v) => (this.value = v));
      text.inputEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') this.submit();
      });
    });
    new Setting(contentEl).addButton((btn) =>
      btn
        .setButtonText('Verify')
        .setCta()
        .onClick(() => this.submit()),
    );
  }

  private submit(): void {
    const code = this.value.trim();
    this.close();
    this.settle(code || null);
  }

  onClose(): void {
    this.contentEl.empty();
    this.settle(null); // closed without submitting
  }
}
