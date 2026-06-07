/**
 * Expand `{{DATE:<format>}}` tokens (Obsidian/moment-style) before templating.
 * Ported from supermd/date_utils.py. Must run before nunjucks renders, since the
 * `:` inside the token is not valid template syntax.
 */

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];
const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

function pad(n: number, len = 2): string {
  return String(n).padStart(len, '0');
}

function isoWeek(d: Date): number {
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dayNum = (date.getUTCDay() + 6) % 7;
  date.setUTCDate(date.getUTCDate() - dayNum + 3);
  const firstThursday = new Date(Date.UTC(date.getUTCFullYear(), 0, 4));
  const diff = date.getTime() - firstThursday.getTime();
  return 1 + Math.round(diff / (7 * 24 * 3600 * 1000));
}

// Longest tokens first so e.g. "YYYY" matches before "YY".
const TOKENS = ['YYYY', 'MMMM', 'dddd', 'MMM', 'ddd', 'YY', 'MM', 'DD', 'HH', 'WW', 'mm', 'ss', 'M', 'D', 'H', 'W', 'm', 's', 'd'];

function tokenValue(token: string, d: Date): string {
  switch (token) {
    case 'YYYY': return String(d.getFullYear());
    case 'YY': return pad(d.getFullYear() % 100);
    case 'MMMM': return MONTHS[d.getMonth()];
    case 'MMM': return MONTHS[d.getMonth()].slice(0, 3);
    case 'MM': return pad(d.getMonth() + 1);
    case 'M': return String(d.getMonth() + 1);
    case 'DD': return pad(d.getDate());
    case 'D': return String(d.getDate());
    case 'dddd': return DAYS[d.getDay()];
    case 'ddd': return DAYS[d.getDay()].slice(0, 3);
    case 'd': return String(d.getDay());
    case 'HH': return pad(d.getHours());
    case 'H': return String(d.getHours());
    case 'mm': return pad(d.getMinutes());
    case 'm': return String(d.getMinutes());
    case 'ss': return pad(d.getSeconds());
    case 's': return String(d.getSeconds());
    case 'WW': return pad(isoWeek(d));
    case 'W': return String(isoWeek(d));
    default: return token;
  }
}

export function formatDate(d: Date, fmt: string): string {
  let out = '';
  let i = 0;
  while (i < fmt.length) {
    const ch = fmt[i];
    if (ch === '[') {
      const end = fmt.indexOf(']', i + 1);
      if (end >= 0) {
        out += fmt.slice(i + 1, end);
        i = end + 1;
        continue;
      }
    }
    const rest = fmt.slice(i);
    const token = TOKENS.find((t) => rest.startsWith(t));
    if (token) {
      out += tokenValue(token, d);
      i += token.length;
      continue;
    }
    out += ch;
    i += 1;
  }
  return out;
}

export function expandDateTokens(template: string, date: Date): string {
  return template.replace(/\{\{DATE:([^}]*)\}\}/g, (_m, fmt: string) => formatDate(date, fmt));
}
