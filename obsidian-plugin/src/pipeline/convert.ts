/**
 * Single-file conversion orchestration, ported from supermd/converter.py.
 * Reads a .note from the vault, transcribes pages (rolling 50-char context +
 * cooldown), renders the template, and writes the .md (+ attachments or .note
 * embed) with skip/protect via the metadata store.
 */
import { App, normalizePath, Notice, TFile } from 'obsidian';
import { parseNote } from '../note/parser';
import { pageToDataUrl, pageToPngBytes } from '../note/render';
import { LlmConfig, generateText, transcribeImage } from '../llm/client';
import { renderTemplate } from './template';
import { ImageRef, notebookContext, parseDateFromName, TemplateContext } from './context';
import { MetadataStore } from '../store/metadata';
import { SuperMDSettings } from '../settings';

export class ConversionSkipped extends Error {}

export interface ConvertOptions {
  /** 'transcribe' runs the LLM; 'view-only' writes a mapped stub embedding the .note. */
  mode: 'transcribe' | 'view-only';
  force?: boolean;
  notify?: boolean;
}

const sleep = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms));

async function ensureFolder(app: App, path: string): Promise<void> {
  const p = normalizePath(path);
  if (!p || p === '.' || p === '/') return;
  if (!(await app.vault.adapter.exists(p))) await app.vault.adapter.mkdir(p);
}

async function ensureParent(app: App, filePath: string): Promise<void> {
  const idx = filePath.lastIndexOf('/');
  if (idx > 0) await ensureFolder(app, filePath.slice(0, idx));
}

function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  const ab = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(ab).set(bytes);
  return ab;
}

export async function convertNoteFile(
  app: App,
  settings: SuperMDSettings,
  apiKey: string,
  meta: MetadataStore,
  file: TFile,
  opts: ConvertOptions,
): Promise<string | null> {
  const bytes = await app.vault.readBinary(file);
  const inputHash = await meta.hash(bytes);
  const existing = meta.get(file.path);
  if (!opts.force && existing && existing.inputHash === inputHash) {
    return null; // input unchanged → skip
  }

  const note = parseNote(bytes);
  const date = parseDateFromName(file.basename, file.stat.mtime);

  // 1. Transcribe (per-page, rolling 50-char context, cooldown).
  let llmOutput = '';
  if (opts.mode === 'transcribe') {
    const cfg: LlmConfig = { baseUrl: settings.baseUrl, apiKey, model: settings.model };
    let context = '';
    for (let p = 0; p < note.pages.length; p++) {
      if (p > 0 && settings.cooldownMs > 0) await sleep(settings.cooldownMs);
      const { dataUrl } = pageToDataUrl(note, p);
      const prompt = settings.prompt.replace('{context}', context);
      const pageMd = await transcribeImage(cfg, prompt, dataUrl);
      llmOutput += (llmOutput ? '\n\n' : '') + pageMd;
      context = llmOutput.slice(-50);
    }
  }

  // 2. Attachments / embed.
  const images: ImageRef[] = [];
  let noteEmbed = '';
  if (settings.attachmentMode === 'extract-png' && opts.mode === 'transcribe') {
    await ensureFolder(app, settings.attachmentFolder || 'attachments');
    for (let p = 0; p < note.pages.length; p++) {
      const png = await pageToPngBytes(note, p);
      const name = `${file.basename}-${p + 1}.png`;
      const path = normalizePath(`${settings.attachmentFolder || 'attachments'}/${name}`);
      if (await app.vault.adapter.exists(path)) await app.vault.adapter.writeBinary(path, toArrayBuffer(png));
      else await app.vault.createBinary(path, toArrayBuffer(png));
      images.push({ name, link: path });
    }
  } else {
    noteEmbed = `![[${file.path}]]`; // rendered live by the embed processor
  }

  // 3. Optional note title.
  let title = file.basename;
  if (opts.mode === 'transcribe' && settings.noteTitlePrompt.trim()) {
    try {
      const t = await generateText(
        { baseUrl: settings.baseUrl, apiKey, model: settings.model },
        settings.noteTitlePrompt.replace('{markdown}', llmOutput),
      );
      if (t) title = t;
    } catch {
      /* title is best-effort */
    }
  }

  // 4. Build context + render.
  const nb = notebookContext(note);
  const ctx: TemplateContext = {
    llm_output: llmOutput,
    markdown: llmOutput,
    images,
    keywords: nb.keywords,
    links: nb.links,
    noteEmbed,
    title,
    file_basename: file.basename,
    file_name: file.name,
  };
  const body = renderTemplate(settings.template, ctx, date);

  const folderPart = renderTemplate(settings.outputFolder || '', ctx, date).trim();
  const fileName = renderTemplate(settings.outputFilenameTemplate, ctx, date).trim();
  const outPath = normalizePath([folderPart, fileName].filter(Boolean).join('/'));

  // 5. Skip/protect, then write.
  const outFile = app.vault.getAbstractFileByPath(outPath);
  if (outFile instanceof TFile) {
    const current = await app.vault.read(outFile);
    const currentHash = await meta.hash(new TextEncoder().encode(current));
    const ignoreLock = /^ignoresnlock:\s*true/im.test(current);
    if (!opts.force && existing && existing.outputHash && currentHash !== existing.outputHash && !ignoreLock) {
      throw new ConversionSkipped(
        `"${outPath}" was edited since last conversion — skipping (add "ignoresnlock: true" to overwrite).`,
      );
    }
    await app.vault.modify(outFile, body);
  } else {
    await ensureParent(app, outPath);
    await app.vault.create(outPath, body);
  }

  const outputHash = await meta.hash(new TextEncoder().encode(body));
  await meta.set({
    inputPath: file.path,
    outputPath: outPath,
    inputHash,
    outputHash,
    images: images.map((i) => i.name),
  });

  if (opts.notify !== false) new Notice(`SuperMD: converted ${file.name}`);
  return outPath;
}
