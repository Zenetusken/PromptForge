import { describe, it, expect } from 'vitest';
import { tagFinding, computeContribution, SCORE_WEIGHTS, SUPPLEMENTARY_META, ALL_SUPPLEMENTARY } from './scoreDimensions';

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

	it('tags conciseness-related findings', () => {
		expect(tagFinding('The prompt is verbose and bloated')).toContain('conciseness');
		expect(tagFinding('Redundant tokens add length without value')).toContain('conciseness');
		expect(tagFinding('Compact and efficient wording')).toContain('conciseness');
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
		// clarity: 95 × 0.20 = 19.0
		expect(computeContribution(95, 'clarity')).toBeCloseTo(19.0);
		// faithfulness: 90 × 0.25 = 22.5
		expect(computeContribution(90, 'faithfulness')).toBeCloseTo(22.5);
		// structure: 100 × 0.15 = 15.0
		expect(computeContribution(100, 'structure')).toBeCloseTo(15.0);
		// conciseness: 80 × 0.20 = 16.0
		expect(computeContribution(80, 'conciseness')).toBeCloseTo(16.0);
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

describe('SUPPLEMENTARY_META', () => {
	it('has metadata for framework_adherence', () => {
		const meta = SUPPLEMENTARY_META.framework_adherence;
		expect(meta.label).toBe('Strategy Fit');
		expect(meta.color).toBe('neon-orange');
		expect(meta.abbrev).toBe('ADH');
		expect(meta.tooltip).toBeTruthy();
	});
});

describe('ALL_SUPPLEMENTARY', () => {
	it('contains framework_adherence', () => {
		expect(ALL_SUPPLEMENTARY).toContain('framework_adherence');
	});

	it('has exactly one entry', () => {
		expect(ALL_SUPPLEMENTARY).toHaveLength(1);
	});
});
