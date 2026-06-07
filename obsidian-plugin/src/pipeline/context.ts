/** Template-context assembly, ported from supermd/context.py. */
import { ParsedNote } from '../note/fileformat';

export interface ImageRef {
  name: string;
  link: string;
}

export interface KeywordRef {
  page_number: number;
  content: string;
}

export interface LinkRef {
  page_number: number;
  type: number;
  inout: number;
  name: string;
}

export interface TemplateContext {
  llm_output: string;
  markdown: string;
  images: ImageRef[];
  keywords: KeywordRef[];
  links: LinkRef[];
  noteEmbed: string;
  title: string;
  file_basename: string;
  file_name: string;
  [key: string]: unknown;
}

/** Parse a creation date from a Supernote filename, falling back to mtime. */
export function parseDateFromName(basename: string, mtimeMs: number): Date {
  const full = basename.match(/(\d{4})(\d{2})(\d{2})_(\d{6})/);
  if (full) {
    const t = full[4];
    return new Date(
      Number(full[1]),
      Number(full[2]) - 1,
      Number(full[3]),
      Number(t.slice(0, 2)),
      Number(t.slice(2, 4)),
      Number(t.slice(4, 6)),
    );
  }
  const dateOnly = basename.match(/(\d{4})(\d{2})(\d{2})/);
  if (dateOnly) {
    return new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]));
  }
  return new Date(mtimeMs);
}

/** Map parsed notebook metadata into template-friendly keyword/link arrays. */
export function notebookContext(note: ParsedNote): { keywords: KeywordRef[]; links: LinkRef[] } {
  return {
    keywords: note.keywords.map((k) => ({ page_number: k.pageNumber, content: k.text })),
    links: note.links.map((l) => ({
      page_number: l.pageNumber,
      type: l.type,
      inout: l.inout,
      name: l.name,
    })),
  };
}
