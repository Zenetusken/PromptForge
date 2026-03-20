import { describe, it, expect } from 'vitest';
import { DOMAIN_COLORS, domainColor, scoreColor } from './patterns';

describe('DOMAIN_COLORS', () => {
  it('has all 7 domains', () => {
    expect(Object.keys(DOMAIN_COLORS)).toEqual(
      expect.arrayContaining(['backend', 'frontend', 'database', 'security', 'devops', 'fullstack', 'general'])
    );
  });
});

describe('domainColor', () => {
  it('returns color for known domain', () => {
    expect(domainColor('backend')).toBe(DOMAIN_COLORS.backend);
  });
  it('returns general color for unknown domain', () => {
    expect(domainColor('unknown')).toBe(DOMAIN_COLORS.general);
  });
});

describe('scoreColor', () => {
  it('returns neon-green for high score (>= 7.5)', () => {
    expect(scoreColor(9.0)).toBe('var(--color-neon-green)');
    expect(scoreColor(7.5)).toBe('var(--color-neon-green)');
    expect(scoreColor(10)).toBe('var(--color-neon-green)');
  });
  it('returns neon-yellow for mid score (>= 5.0, < 7.5)', () => {
    expect(scoreColor(5.0)).toBe('var(--color-neon-yellow)');
    expect(scoreColor(7.0)).toBe('var(--color-neon-yellow)');
    expect(scoreColor(7.49)).toBe('var(--color-neon-yellow)');
  });
  it('returns neon-red for low score (> 0, < 5.0)', () => {
    expect(scoreColor(3.0)).toBe('var(--color-neon-red)');
    expect(scoreColor(4.99)).toBe('var(--color-neon-red)');
    expect(scoreColor(0.1)).toBe('var(--color-neon-red)');
  });
  it('returns text-dim for null score', () => {
    expect(scoreColor(null)).toBe('var(--color-text-dim)');
  });
  it('returns text-dim for zero or negative score', () => {
    expect(scoreColor(0)).toBe('var(--color-text-dim)');
    expect(scoreColor(-1)).toBe('var(--color-text-dim)');
  });
});
