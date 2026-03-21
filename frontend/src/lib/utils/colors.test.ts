import { describe, it, expect } from 'vitest';
import { scoreColor, taxonomyColor } from './colors';

describe('scoreColor', () => {
  it('returns dim for null', () => {
    expect(scoreColor(null)).toBe('var(--color-text-dim)');
  });

  it('returns green for 9+', () => {
    expect(scoreColor(9.5)).toBe('var(--color-neon-green)');
  });

  it('returns cyan for 7-8.9', () => {
    expect(scoreColor(7.5)).toBe('var(--color-neon-cyan)');
  });

  it('returns yellow for 4-6.9', () => {
    expect(scoreColor(5.0)).toBe('var(--color-neon-yellow)');
  });

  it('returns red for below 4', () => {
    expect(scoreColor(2.0)).toBe('var(--color-neon-red)');
  });
});

describe('taxonomyColor', () => {
  it('returns provided color when present', () => {
    expect(taxonomyColor('#a855f7')).toBe('#a855f7');
  });

  it('returns fallback for null/undefined', () => {
    expect(taxonomyColor(null)).toBe('#7a7a9e');
    expect(taxonomyColor(undefined)).toBe('#7a7a9e');
  });
});
