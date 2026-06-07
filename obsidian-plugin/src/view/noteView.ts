/** Full-tab viewer: opens a `.note` file from the explorer as decoded page images. */
import { FileView, TFile, WorkspaceLeaf } from 'obsidian';
import { renderNoteToImages } from '../note/render';

export const VIEW_TYPE_NOTE = 'supermd-note-view';

export class NoteFileView extends FileView {
  constructor(leaf: WorkspaceLeaf) {
    super(leaf);
  }

  getViewType(): string {
    return VIEW_TYPE_NOTE;
  }

  getIcon(): string {
    return 'pencil';
  }

  getDisplayText(): string {
    return this.file?.name ?? 'Supernote';
  }

  canAcceptExtension(extension: string): boolean {
    return extension === 'note';
  }

  async onLoadFile(file: TFile): Promise<void> {
    const c = this.contentEl;
    c.empty();
    c.addClass('supermd-note-view');
    try {
      const bytes = await this.app.vault.readBinary(file);
      for (const img of renderNoteToImages(bytes)) c.appendChild(img);
    } catch (e) {
      c.createDiv({ cls: 'supermd-error', text: `Failed to render .note: ${(e as Error).message}` });
    }
  }

  async onUnloadFile(): Promise<void> {
    this.contentEl.empty();
  }
}
