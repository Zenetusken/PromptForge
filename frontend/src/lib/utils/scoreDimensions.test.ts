import { describe, it, expect } from 'vitest';
import { tagFinding, computeContribution, SCORE_WEIGHTS } from './scoreDimensions';

describe('tagFinding', () => {
	it('tags clarity-related findings', () => {
		expect(tagFinding('The instructions are ambiguous')).toContain('clarity');
		expect(tagFinding('Clear and explicit constraints')).toContain('clarity');
	});

	it('tags specificity-related findings', () => {
		expect(tagFinding('Too vague and general')).toContain('specificity');
		expect(tagFinding('Needs more specific details')).toContain('specificity');
	});

	it('tags structure-related findings', () => {
		expect(tagFinding('Well organized sections')).toContain('structure');
		expect(tagFinding('Poor formatting and layout')).toContain('structure');
	});

	it('tags faithfulness-related findings', () => {
		expect(tagFinding('Preserves original intent')).toContain('faithfulness');
		expect(tagFinding('Deviates from the scope')).toContain('faithfulness');
	});

	it('returns multiple dimensions for multi-topic findings', () => {
		const tags = tagFinding('The instructions lack specific structure and formatting');
		expect(tags).toContain('clarity');
		expect(tags).toContain('specificity');
		expect(tags).toContain('structure');
	});

	it('returns empty array for unmatched findings', () => {
		expect(tagFinding('Uses Python 3.12')).toEqual([]);
	});
});

describe('computeContribution', () => {
	it('computes weighted contribution correctly', () => {
		expect(computeContribution(95, 'clarity')).toBeCloseTo(23.75);
		expect(computeContribution(90, 'faithfulness')).toBeCloseTo(27);
		expect(computeContribution(100, 'structure')).toBeCloseTo(20);
	});

	it('returns 0 for score of 0', () => {
		expect(computeContribution(0, 'specificity')).toBe(0);
	});
});

describe('SCORE_WEIGHTS', () => {
	it('sums to 1.0', () => {
		const sum = Object.values(SCORE_WEIGHTS).reduce((a, b) => a + b, 0);
		expect(sum).toBeCloseTo(1.0);
	});
});
