import { describe, it, expect } from 'vitest';
import { DIMENSION_LABELS, PHASE_LABELS, getPhaseLabel } from './dimensions';

describe('DIMENSION_LABELS', () => {
  it('has all 5 dimensions', () => {
    expect(Object.keys(DIMENSION_LABELS)).toEqual(
      expect.arrayContaining(['clarity', 'specificity', 'structure', 'faithfulness', 'conciseness'])
    );
  });
  it('values are non-empty strings', () => {
    Object.values(DIMENSION_LABELS).forEach((v) => {
      expect(typeof v).toBe('string');
      expect(v.length).toBeGreaterThan(0);
    });
  });
});

describe('PHASE_LABELS', () => {
  it('has labels for known phases', () => {
    expect(PHASE_LABELS).toHaveProperty('analyzing');
    expect(PHASE_LABELS).toHaveProperty('optimizing');
    expect(PHASE_LABELS).toHaveProperty('scoring');
  });
});

describe('getPhaseLabel', () => {
  it('returns label for known phase', () => {
    expect(getPhaseLabel('analyzing')).toBe(PHASE_LABELS.analyzing);
  });
  it('returns null for unknown phase', () => {
    expect(getPhaseLabel('unknown')).toBeNull();
  });
});
