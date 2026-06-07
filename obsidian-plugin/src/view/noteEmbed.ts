/** Inline embed renderer: turns ![[file.note]] embeds into decoded page images. */
import { Plugin, TFile } from 'obsidian';
import { renderNoteToImages } from '../note/render';

export function registerNoteEmbeds(plugin: Plugin): void {
  plugin.registerMarkdownPostProcessor(async (el, ctx) => {
    const embeds = Array.from(el.querySelectorAll('.internal-embed')) as HTMLElement[];
    for (const node of embeds) {
      const src = node.getAttribute('src');
      if (!src || !src.toLowerCase().endsWith('.note')) continue;
      const dest = plugin.app.metadataCache.getFirstLinkpathDest(src, ctx.sourcePath);
      if (!(dest instanceof TFile)) continue;
      node.empty();
      node.addClass('supermd-note-embed');
      try {
        const bytes = await plugin.app.vault.readBinary(dest);
        for (const img of renderNoteToImages(bytes)) node.appendChild(img);
      } catch (e) {
        node.createDiv({ cls: 'supermd-error', text: `Failed to render ${src}: ${(e as Error).message}` });
      }
    }
  });
}
