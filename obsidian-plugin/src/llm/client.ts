/** LLM client over Obsidian's requestUrl (bypasses CORS; works on mobile). Ports ai_utils.py. */
import { requestUrl } from 'obsidian';

export interface LlmConfig {
  baseUrl: string;
  apiKey: string;
  model: string;
}

type Content =
  | { type: 'text'; text: string }
  | { type: 'image_url'; image_url: { url: string } };

function chatUrl(baseUrl: string): string {
  const b = baseUrl.replace(/\/+$/, '');
  return /\/v\d+$/.test(b) ? `${b}/chat/completions` : `${b}/v1/chat/completions`;
}

async function chat(cfg: LlmConfig, content: Content[]): Promise<string> {
  if (!cfg.apiKey) throw new Error('No LLM API key configured (set one in SuperMD settings).');
  const res = await requestUrl({
    url: chatUrl(cfg.baseUrl),
    method: 'POST',
    contentType: 'application/json',
    headers: { Authorization: `Bearer ${cfg.apiKey}` },
    body: JSON.stringify({ model: cfg.model, messages: [{ role: 'user', content }] }),
    throw: false,
  });
  if (res.status >= 400) {
    throw new Error(`LLM HTTP ${res.status}: ${(res.text || '').slice(0, 300)}`);
  }
  const json = res.json as { choices?: Array<{ message?: { content?: string } }> };
  return (json?.choices?.[0]?.message?.content ?? '').trim();
}

/** Transcribe a single page image (data URL) to markdown. */
export function transcribeImage(cfg: LlmConfig, prompt: string, dataUrl: string): Promise<string> {
  return chat(cfg, [
    { type: 'text', text: prompt },
    { type: 'image_url', image_url: { url: dataUrl } },
  ]);
}

/** Text-only completion (e.g. note-title generation). */
export function generateText(cfg: LlmConfig, prompt: string): Promise<string> {
  return chat(cfg, [{ type: 'text', text: prompt }]);
}
