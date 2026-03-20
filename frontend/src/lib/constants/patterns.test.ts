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
  it('returns correct token for high score', () => {
    const color = scoreColor(9.0);
    expect(typeof color).toBe('string');
    expect(color.length).toBeGreaterThan(0);
  });
  it('returns correct token for low score', () => {
    const color = scoreColor(3.0);
    expect(typeof color).toBe('string');
  });
  it('handles null score', () => {
    const color = scoreColor(null);
    expect(typeof color).toBe('string');
  });
  it('handles boundary values (0, 5, 7, 10)', () => {
    for (const s of [0, 5, 7, 10]) {
      expect(typeof scoreColor(s)).toBe('string');
    }
  });
});
