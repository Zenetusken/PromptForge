import { describe, it, expect, vi } from 'vitest';
import { formatScore, formatDelta, truncateText, copyToClipboard } from './formatting';

describe('formatScore', () => {
  it('formats a number with 1 decimal by default', () => {
    expect(formatScore(7.56)).toBe('7.6');
  });
  it('formats with custom decimals', () => {
    expect(formatScore(7.567, 2)).toBe('7.57');
  });
  it('returns dash for null', () => {
    expect(formatScore(null)).toBe('--');
  });
  it('returns dash for undefined', () => {
    expect(formatScore(undefined)).toBe('--');
  });
  it('handles zero', () => {
    expect(formatScore(0)).toBe('0.0');
  });
  it('handles 10', () => {
    expect(formatScore(10)).toBe('10.0');
  });
});

describe('formatDelta', () => {
  it('formats positive delta with + prefix', () => {
    expect(formatDelta(2.5)).toMatch(/^\+/);
  });
  it('formats negative delta with - prefix', () => {
    expect(formatDelta(-1.3)).toMatch(/^-/);
  });
  it('formats zero delta', () => {
    const result = formatDelta(0);
    expect(result).toContain('0');
  });
  it('respects custom decimals', () => {
    expect(formatDelta(2.567, 2)).toContain('2.57');
  });
});

describe('truncateText', () => {
  it('returns short text unchanged', () => {
    expect(truncateText('hello', 80)).toBe('hello');
  });
  it('truncates long text with ellipsis', () => {
    const long = 'a'.repeat(100);
    const result = truncateText(long, 80);
    expect(result.length).toBeLessThanOrEqual(83); // 80 + '...'
    expect(result).toContain('...');
  });
  it('uses default maxLen of 80', () => {
    const exactlyAt = 'a'.repeat(80);
    expect(truncateText(exactlyAt)).toBe(exactlyAt);
  });
});

describe('copyToClipboard', () => {
  it('copies text via clipboard API', async () => {
    const result = await copyToClipboard('hello');
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('hello');
    expect(result).toBe(true);
  });
  it('returns false on failure', async () => {
    vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValueOnce(new Error('fail'));
    // jsdom doesn't implement execCommand — mock it so the fallback path returns false
    const execCommand = vi.fn().mockReturnValue(false);
    document.execCommand = execCommand;
    const result = await copyToClipboard('hello');
    expect(result).toBe(false);
  });
});
