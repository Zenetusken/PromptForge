import { describe, it, expect } from 'vitest';
import { DIMENSION_LABELS, PHASE_LABELS, getPhaseLabel } from './dimensions';

describe('DIMENSION_LABELS', () => {
  it('has all 5 dimensions with correct labels', () => {
    expect(DIMENSION_LABELS).toEqual({
      clarity: 'Clarity',
      specificity: 'Specificity',
      structure: 'Structure',
      faithfulness: 'Faithfulness',
      conciseness: 'Conciseness',
    });
  });
});

describe('PHASE_LABELS', () => {
  it('has correct labels for all phases', () => {
    expect(PHASE_LABELS).toEqual({
      analyzing: 'Analyzing',
      optimizing: 'Optimizing',
      scoring: 'Scoring',
      passthrough: 'Passthrough',
    });
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
