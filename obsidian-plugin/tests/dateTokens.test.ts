import { describe, expect, it } from 'vitest';
import { expandDateTokens, formatDate } from '../src/pipeline/dateTokens';

describe('date tokens', () => {
  const d = new Date(2026, 5, 7, 9, 4, 5); // 2026-06-07 09:04:05 (June)

  it('formats common tokens', () => {
    expect(formatDate(d, 'YYYY-MM-DD')).toBe('2026-06-07');
    expect(formatDate(d, 'YY/M/D')).toBe('26/6/7');
    expect(formatDate(d, 'HH:mm:ss')).toBe('09:04:05');
    expect(formatDate(d, 'MMMM MMM')).toBe('June Jun');
  });

  it('honors [escaped] literals', () => {
    expect(formatDate(d, 'YYYY [at] HH')).toBe('2026 at 09');
  });

  it('expands {{DATE:...}} tokens in a template', () => {
    expect(expandDateTokens('created: {{DATE:YYYY/MM}}', d)).toBe('created: 2026/06');
  });
});
