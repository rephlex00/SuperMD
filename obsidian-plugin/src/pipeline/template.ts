/** Nunjucks template rendering with a {{DATE:...}} pre-pass (Jinja2 parity). */
import nunjucks from 'nunjucks';
import { expandDateTokens } from './dateTokens';

const env = new nunjucks.Environment(undefined, { autoescape: false });

/** Render a template string with the given context, after expanding date tokens. */
export function renderTemplate(template: string, context: Record<string, unknown>, date: Date): string {
  const expanded = expandDateTokens(template, date);
  return env.renderString(expanded, context);
}
