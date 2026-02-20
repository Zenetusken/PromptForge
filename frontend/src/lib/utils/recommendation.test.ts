import { describe, it, expect } from 'vitest';
import {
	buildTaskFrequency,
	computeAffinityScore,
	computeGapScore,
	computeDiversityScore,
	computeConfidenceWeight,
	computeSecondaryFamiliarityScore,
	computeTagAffinityBoost,
	computeFrequencyScore,
	computeReachScore,
	computeSynergyScore,
	computeSecondaryComposite,
	computeCompositeScore,
	computeComboScore,
	classifyConfidence,
	generateSecondaryInsights,
	selectTopPerformer,
	computeRecommendations,
	buildTriedStrategyBestFor,
	DEFAULT_WEIGHTS,
	DEFAULT_SECONDARY_WEIGHTS,
} from './recommendation';
import type {
	RecommendationInput,
	RecommendationWeights,
	ScoredStrategy,
	SecondaryProcessorWeights,
} from './recommendation';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a minimal ScoredStrategy for confidence classification tests. */
function makeScoredStrategy(overrides: Partial<ScoredStrategy>): ScoredStrategy {
	return {
		name: 'chain-of-thought',
		label: 'Chain of Thought',
		motivation: 'test',
		affinityScore: 0,
		gapScore: 0,
		diversityScore: 0,
		secondaryFamiliarityScore: 0,
		tagAffinityBoost: 0,
		frequencyScore: 0,
		reachScore: 0,
		synergyScore: 0,
		secondaryComposite: 0,
		secondaryInfluencePct: 0,
		confidenceWeight: 0,
		compositeScore: 0,
		...overrides,
	};
}

// ---------------------------------------------------------------------------
// buildTaskFrequency
// ---------------------------------------------------------------------------

describe('buildTaskFrequency', () => {
	it('flattens per-strategy task types into global frequency map', () => {
		const result = buildTaskFrequency({
			'chain-of-thought': { reasoning: 5, coding: 2 },
			'co-star': { writing: 3, reasoning: 1 },
		});
		expect(result.freq).toEqual({ reasoning: 6, coding: 2, writing: 3 });
		expect(result.total).toBe(11);
	});

	it('returns empty map and zero total for empty input', () => {
		const result = buildTaskFrequency({});
		expect(result.freq).toEqual({});
		expect(result.total).toBe(0);
	});

	it('handles single strategy with single task type', () => {
		const result = buildTaskFrequency({ 'step-by-step': { math: 7 } });
		expect(result.freq).toEqual({ math: 7 });
		expect(result.total).toBe(7);
	});
});

// ---------------------------------------------------------------------------
// computeAffinityScore
// ---------------------------------------------------------------------------

describe('computeAffinityScore', () => {
	it('returns proportion of user work matching bestFor', () => {
		// bestFor = [coding, math], freq: coding=8, writing=4, math=3 → (8+3)/15 = 0.733
		const score = computeAffinityScore(
			['coding', 'math'],
			{ coding: 8, writing: 4, math: 3 },
			15,
		);
		expect(score).toBeCloseTo(11 / 15, 5);
	});

	it('returns 0 when no bestFor types match user task types', () => {
		const score = computeAffinityScore(
			['classification', 'extraction'],
			{ coding: 10, writing: 5 },
			15,
		);
		expect(score).toBe(0);
	});

	it('returns 0 when totalFreq is 0', () => {
		expect(computeAffinityScore(['coding'], { coding: 5 }, 0)).toBe(0);
	});

	it('returns 0 for empty bestFor', () => {
		expect(computeAffinityScore([], { coding: 5 }, 5)).toBe(0);
	});

	it('returns 1.0 when all user work matches bestFor', () => {
		const score = computeAffinityScore(
			['coding', 'writing'],
			{ coding: 5, writing: 5 },
			10,
		);
		expect(score).toBeCloseTo(1.0, 5);
	});
});

// ---------------------------------------------------------------------------
// buildTriedStrategyBestFor
// ---------------------------------------------------------------------------

describe('buildTriedStrategyBestFor', () => {
	it('maps tried strategy names to their bestFor arrays', () => {
		const result = buildTriedStrategyBestFor({ 'chain-of-thought': 5, 'co-star': 3 });
		expect(result['chain-of-thought']).toEqual(['reasoning', 'analysis', 'math']);
		expect(result['co-star']).toEqual(['writing', 'creative', 'reasoning']);
	});

	it('skips unknown strategy names', () => {
		const result = buildTriedStrategyBestFor({ 'unknown-strategy': 2 });
		expect(result).toEqual({});
	});
});

// ---------------------------------------------------------------------------
// computeGapScore
// ---------------------------------------------------------------------------

describe('computeGapScore', () => {
	it('returns 1.0 when all bestFor types are completely uncovered', () => {
		// bestFor = [classification, extraction], no tried strategies target these
		const score = computeGapScore(
			['classification', 'extraction'],
			{ 'co-star': ['writing', 'creative', 'reasoning'] },
			{ 'co-star': 0.8 },
			{ 'co-star': 5 },
			0.7,
		);
		expect(score).toBe(1.0);
	});

	it('returns 0 when tried strategies outperform global average on all types', () => {
		// bestFor = [writing], co-star targets writing with score 0.9 > avg 0.7
		const score = computeGapScore(
			['writing'],
			{ 'co-star': ['writing', 'creative', 'reasoning'] },
			{ 'co-star': 0.9 },
			{ 'co-star': 5 },
			0.7,
		);
		expect(score).toBe(0);
	});

	it('returns partial gap when tried strategies underperform', () => {
		// bestFor = [coding], step-by-step targets coding with score 0.5 < avg 0.7
		// gap = 1 - 0.5/0.7 ≈ 0.286
		const score = computeGapScore(
			['coding'],
			{ 'step-by-step': ['math', 'coding'] },
			{ 'step-by-step': 0.5 },
			{ 'step-by-step': 10 },
			0.7,
		);
		expect(score).toBeCloseTo(1 - 0.5 / 0.7, 3);
	});

	it('returns 0 when globalAvgScore is null', () => {
		const score = computeGapScore(
			['coding'],
			{ 'step-by-step': ['math', 'coding'] },
			{ 'step-by-step': 0.5 },
			{ 'step-by-step': 10 },
			null,
		);
		expect(score).toBe(0);
	});

	it('returns 0 for empty bestFor', () => {
		expect(computeGapScore([], {}, {}, {}, 0.7)).toBe(0);
	});

	it('returns 0 when tried strategies cover the type but have no score data', () => {
		// bestFor = [writing], co-star targets writing but has no score → can't assess gap
		const score = computeGapScore(
			['writing'],
			{ 'co-star': ['writing', 'creative', 'reasoning'] },
			{},
			{ 'co-star': 5 },
			0.7,
		);
		expect(score).toBe(0);
	});

	it('returns mixed gap when some types are uncovered and some have no score data', () => {
		// bestFor = [writing, classification]
		// co-star covers writing (no score → gap=0), nobody covers classification (gap=1.0)
		// average = (0 + 1.0) / 2 = 0.5
		const score = computeGapScore(
			['writing', 'classification'],
			{ 'co-star': ['writing', 'creative', 'reasoning'] },
			{},
			{ 'co-star': 5 },
			0.7,
		);
		expect(score).toBe(0.5);
	});

	it('computes weighted average across multiple tried strategies for same type', () => {
		// bestFor = [writing], two tried strategies target writing:
		// co-star: score 0.8, count 6 → weighted 4.8
		// risen: score 0.4, count 4 → weighted 1.6
		// weightedAvg = 6.4/10 = 0.64, globalAvg = 0.7
		// gap = 1 - 0.64/0.7 ≈ 0.086
		const score = computeGapScore(
			['writing'],
			{
				'co-star': ['writing', 'creative', 'reasoning'],
				'risen': ['general', 'writing'],
			},
			{ 'co-star': 0.8, 'risen': 0.4 },
			{ 'co-star': 6, 'risen': 4 },
			0.7,
		);
		expect(score).toBeCloseTo(1 - 0.64 / 0.7, 3);
	});
});

// ---------------------------------------------------------------------------
// computeDiversityScore
// ---------------------------------------------------------------------------

describe('computeDiversityScore', () => {
	it('returns 1.0 when no bestFor types are well-served', () => {
		// bestFor = [classification, extraction], no tried strategies target these
		const score = computeDiversityScore(
			['classification', 'extraction'],
			{ 'co-star': ['writing', 'creative', 'reasoning'] },
			{ 'co-star': 0.8 },
			0.7,
		);
		expect(score).toBe(1.0);
	});

	it('returns 0 when all bestFor types are well-served', () => {
		// bestFor = [writing], co-star targets writing with score 0.8 >= avg 0.7
		const score = computeDiversityScore(
			['writing'],
			{ 'co-star': ['writing', 'creative', 'reasoning'] },
			{ 'co-star': 0.8 },
			0.7,
		);
		expect(score).toBe(0);
	});

	it('returns partial diversity when some types are served', () => {
		// bestFor = [writing, coding], co-star serves writing (0.8 >= 0.7), nobody serves coding
		const score = computeDiversityScore(
			['writing', 'coding'],
			{ 'co-star': ['writing', 'creative', 'reasoning'] },
			{ 'co-star': 0.8 },
			0.7,
		);
		expect(score).toBe(0.5);
	});

	it('counts underperforming tried strategies as not well-served', () => {
		// bestFor = [writing], co-star targets writing but scores 0.5 < avg 0.7 → not well-served
		const score = computeDiversityScore(
			['writing'],
			{ 'co-star': ['writing', 'creative', 'reasoning'] },
			{ 'co-star': 0.5 },
			0.7,
		);
		expect(score).toBe(1.0);
	});

	it('returns 0 for empty bestFor', () => {
		expect(computeDiversityScore([], {}, {}, 0.7)).toBe(0);
	});

	it('treats null globalAvgScore as all types unserved', () => {
		const score = computeDiversityScore(
			['writing'],
			{ 'co-star': ['writing', 'creative', 'reasoning'] },
			{ 'co-star': 0.8 },
			null,
		);
		expect(score).toBe(1.0);
	});
});

// ---------------------------------------------------------------------------
// computeConfidenceWeight
// ---------------------------------------------------------------------------

describe('computeConfidenceWeight', () => {
	it('returns 0 for 0 optimizations', () => {
		expect(computeConfidenceWeight(0)).toBe(0);
	});

	it('returns 0 for negative input', () => {
		expect(computeConfidenceWeight(-5)).toBe(0);
	});

	it('returns ~0.50 at the midpoint (10 optimizations)', () => {
		expect(computeConfidenceWeight(10)).toBeCloseTo(0.5, 5);
	});

	it('increases monotonically', () => {
		const v5 = computeConfidenceWeight(5);
		const v10 = computeConfidenceWeight(10);
		const v50 = computeConfidenceWeight(50);
		const v100 = computeConfidenceWeight(100);
		expect(v5).toBeLessThan(v10);
		expect(v10).toBeLessThan(v50);
		expect(v50).toBeLessThan(v100);
	});

	it('approaches 1.0 for large values', () => {
		expect(computeConfidenceWeight(1000)).toBeGreaterThan(0.99);
	});
});

// ---------------------------------------------------------------------------
// computeSecondaryFamiliarityScore
// ---------------------------------------------------------------------------

describe('computeSecondaryFamiliarityScore', () => {
	it('returns 0 when strategy has no secondary usage', () => {
		expect(computeSecondaryFamiliarityScore('step-by-step', { 'constraint-injection': 9 })).toBe(0);
	});

	it('returns 0 for empty secondary distribution', () => {
		expect(computeSecondaryFamiliarityScore('step-by-step', {})).toBe(0);
	});

	it('returns 1.0 for strategy with max secondary count', () => {
		const dist = { 'constraint-injection': 9, 'structured-output': 5, 'risen': 2 };
		expect(computeSecondaryFamiliarityScore('constraint-injection', dist)).toBeCloseTo(1.0, 5);
	});

	it('normalizes relative to max secondary count', () => {
		const dist = { 'constraint-injection': 9, 'structured-output': 5, 'risen': 2 };
		expect(computeSecondaryFamiliarityScore('structured-output', dist)).toBeCloseTo(5 / 9, 3);
		expect(computeSecondaryFamiliarityScore('risen', dist)).toBeCloseTo(2 / 9, 3);
	});

	it('handles single-entry distribution', () => {
		expect(computeSecondaryFamiliarityScore('co-star', { 'co-star': 3 })).toBeCloseTo(1.0, 5);
	});
});

// ---------------------------------------------------------------------------
// computeTagAffinityBoost
// ---------------------------------------------------------------------------

describe('computeTagAffinityBoost', () => {
	it('returns 0 for empty bestFor', () => {
		expect(computeTagAffinityBoost([], { 'chain-of-thought': { coding: 5 } })).toBe(0);
	});

	it('returns 0 for empty tagsByStrategy', () => {
		expect(computeTagAffinityBoost(['coding', 'analysis'], {})).toBe(0);
	});

	it('computes proportion of tags matching bestFor types', () => {
		// tags: coding=5, backend=3 → total=8
		// bestFor: [coding, analysis, math] → coding matches (5/8 = 0.625)
		const tags = { 'chain-of-thought': { coding: 5, backend: 3 } };
		expect(computeTagAffinityBoost(['coding', 'analysis', 'math'], tags)).toBeCloseTo(5 / 8, 3);
	});

	it('matches tags case-insensitively', () => {
		const tags = { 'chain-of-thought': { Coding: 5, ANALYSIS: 3 } };
		expect(computeTagAffinityBoost(['coding', 'analysis'], tags)).toBeCloseTo(1.0, 5);
	});

	it('aggregates tags across multiple strategies', () => {
		// chain-of-thought: coding=5, constraint-injection: coding=3, safety=2 → total=10
		// bestFor: [coding] → coding total = 8, boost = 8/10 = 0.8
		const tags = {
			'chain-of-thought': { coding: 5 },
			'constraint-injection': { coding: 3, safety: 2 },
		};
		expect(computeTagAffinityBoost(['coding'], tags)).toBeCloseTo(8 / 10, 3);
	});

	it('returns 0 when no bestFor types appear as tags', () => {
		const tags = { 'chain-of-thought': { backend: 5, api: 3 } };
		expect(computeTagAffinityBoost(['writing', 'creative'], tags)).toBe(0);
	});
});

// ---------------------------------------------------------------------------
// computeFrequencyScore
// ---------------------------------------------------------------------------

describe('computeFrequencyScore', () => {
	it('returns 0 when totalOptimizations is 0', () => {
		expect(computeFrequencyScore('step-by-step', { 'step-by-step': 5 }, 0)).toBe(0);
	});

	it('computes ratio of secondary count to total', () => {
		// 5 secondary uses out of 20 total → 0.25
		expect(computeFrequencyScore('step-by-step', { 'step-by-step': 5 }, 20)).toBeCloseTo(0.25, 5);
	});

	it('caps at 1.0 when count exceeds total', () => {
		// edge case: secondary count could exceed total in theory
		expect(computeFrequencyScore('step-by-step', { 'step-by-step': 30 }, 20)).toBe(1);
	});

	it('returns 0 for missing strategy in distribution', () => {
		expect(computeFrequencyScore('co-star', { 'step-by-step': 5 }, 20)).toBe(0);
	});
});

// ---------------------------------------------------------------------------
// computeReachScore
// ---------------------------------------------------------------------------

describe('computeReachScore', () => {
	it('returns 0 when strategy has no secondary usage', () => {
		expect(computeReachScore('co-star', { 'step-by-step': 5 }, 3)).toBe(0);
	});

	it('caps at 1.0 when count exceeds numTriedPrimaries', () => {
		// count=10, K=3 → min(10,3)/3 = 1.0
		expect(computeReachScore('step-by-step', { 'step-by-step': 10 }, 3)).toBeCloseTo(1.0, 5);
	});

	it('returns fractional value when count < K', () => {
		// count=2, K=5 → 2/5 = 0.4
		expect(computeReachScore('step-by-step', { 'step-by-step': 2 }, 5)).toBeCloseTo(0.4, 5);
	});

	it('uses K=1 minimum when numTriedPrimaries is 0', () => {
		// count=3, K=max(0,1)=1 → min(3,1)/1 = 1.0
		expect(computeReachScore('step-by-step', { 'step-by-step': 3 }, 0)).toBeCloseTo(1.0, 5);
	});
});

// ---------------------------------------------------------------------------
// computeSynergyScore
// ---------------------------------------------------------------------------

describe('computeSynergyScore', () => {
	it('returns 0 when familiarity is 0', () => {
		expect(computeSynergyScore(0, 0.8)).toBe(0);
	});

	it('returns 0 when tagAffinity is 0', () => {
		expect(computeSynergyScore(0.8, 0)).toBe(0);
	});

	it('returns geometric mean when both are positive', () => {
		// sqrt(0.64 * 0.36) = sqrt(0.2304) ≈ 0.48
		expect(computeSynergyScore(0.64, 0.36)).toBeCloseTo(Math.sqrt(0.64 * 0.36), 5);
	});

	it('returns 1.0 when both signals are 1.0', () => {
		expect(computeSynergyScore(1.0, 1.0)).toBeCloseTo(1.0, 5);
	});
});

// ---------------------------------------------------------------------------
// computeSecondaryComposite
// ---------------------------------------------------------------------------

describe('computeSecondaryComposite', () => {
	it('blends all 5 signals with default weights', () => {
		// familiarity=0.5, tagAffinity=0.4, frequency=0.3, reach=0.2
		// synergy = sqrt(0.5 * 0.4) = sqrt(0.2) ≈ 0.4472
		// composite = 0.20*0.3 + 0.15*0.2 + 0.25*0.4472 + 0.25*0.5 + 0.15*0.4
		//           = 0.06 + 0.03 + 0.1118 + 0.125 + 0.06 = 0.3868
		const result = computeSecondaryComposite(0.5, 0.4, 0.3, 0.2);
		const synergy = Math.sqrt(0.5 * 0.4);
		const expected =
			0.20 * 0.3 + 0.15 * 0.2 + 0.25 * synergy + 0.25 * 0.5 + 0.15 * 0.4;
		expect(result).toBeCloseTo(expected, 5);
	});

	it('returns 0 when all signals are 0', () => {
		expect(computeSecondaryComposite(0, 0, 0, 0)).toBe(0);
	});

	it('uses custom weights when provided', () => {
		const w: SecondaryProcessorWeights = {
			frequency: 1, reach: 0, synergy: 0, familiarity: 0, tagAffinity: 0,
		};
		// Only frequency contributes: 1.0 * 0.5 = 0.5
		expect(computeSecondaryComposite(0.8, 0.8, 0.5, 0.3, w)).toBeCloseTo(0.5, 5);
	});
});

// ---------------------------------------------------------------------------
// computeCompositeScore
// ---------------------------------------------------------------------------

describe('computeCompositeScore', () => {
	it('combines base signals with weights and confidence', () => {
		const score = computeCompositeScore(0.8, 0.6, 0.4, 0.5, DEFAULT_WEIGHTS);
		// (0.50*0.8 + 0.25*0.6 + 0.25*0.4 + 0.20*0) * 0.5 = (0.4 + 0.15 + 0.1) * 0.5 = 0.325
		expect(score).toBeCloseTo(0.325, 5);
	});

	it('returns 0 when confidence is 0', () => {
		expect(computeCompositeScore(1, 1, 1, 0, DEFAULT_WEIGHTS)).toBe(0);
	});

	it('returns 0 when all signals are 0', () => {
		expect(computeCompositeScore(0, 0, 0, 1, DEFAULT_WEIGHTS)).toBe(0);
	});

	it('respects custom weights', () => {
		const weights: RecommendationWeights = { affinity: 1, gap: 0, diversity: 0, secondary: 0 };
		const score = computeCompositeScore(0.6, 0.9, 0.9, 1.0, weights);
		expect(score).toBeCloseTo(0.6, 5);
	});

	it('adds secondary composite to base score', () => {
		// base = (0.50*0.8 + 0.25*0.6 + 0.25*0.4) = 0.65
		// secondary = 0.20*0.5 = 0.10
		// composite = (0.65 + 0.10) * 0.5 = 0.375
		const score = computeCompositeScore(0.8, 0.6, 0.4, 0.5, DEFAULT_WEIGHTS, 0.5);
		expect(score).toBeCloseTo(0.375, 5);
	});

	it('handles full secondary composite at 1.0', () => {
		// base = 0.65, secondary = 0.20*1.0 = 0.20
		// composite = (0.65 + 0.20) * 0.5 = 0.425
		const score = computeCompositeScore(0.8, 0.6, 0.4, 0.5, DEFAULT_WEIGHTS, 1.0);
		expect(score).toBeCloseTo(0.425, 5);
	});

	it('ignores secondary when weight is 0', () => {
		const weights: RecommendationWeights = { affinity: 1, gap: 0, diversity: 0, secondary: 0 };
		const score = computeCompositeScore(0.6, 0, 0, 1.0, weights, 1.0);
		expect(score).toBeCloseTo(0.6, 5);
	});
});

// ---------------------------------------------------------------------------
// classifyConfidence
// ---------------------------------------------------------------------------

describe('classifyConfidence', () => {
	it('returns high tier for composite > 0.30 and confidence > 0.5', () => {
		const scored = makeScoredStrategy({
			name: 'step-by-step',
			compositeScore: 0.35,
			confidenceWeight: 0.6,
			affinityScore: 0.5,
		});
		const result = classifyConfidence(scored, { coding: 10, math: 5 });
		expect(result.tier).toBe('high');
		expect(result.label).toBe('Strong match');
		expect(result.reason).toContain('coding');
	});

	it('returns moderate tier for composite > 0.10', () => {
		const scored = makeScoredStrategy({
			compositeScore: 0.20,
			confidenceWeight: 0.3,
			affinityScore: 0.3,
		});
		const result = classifyConfidence(scored, { coding: 5 });
		expect(result.tier).toBe('moderate');
		expect(result.label).toBe('Worth trying');
	});

	it('does NOT promote to moderate when composite is low despite high confidence', () => {
		// High data confidence + low composite → still exploratory (no broken OR)
		const scored = makeScoredStrategy({
			compositeScore: 0.05,
			confidenceWeight: 0.9,
		});
		const result = classifyConfidence(scored, {});
		expect(result.tier).toBe('exploratory');
	});

	it('returns exploratory for low composite and low confidence', () => {
		const scored = makeScoredStrategy({
			compositeScore: 0.05,
			confidenceWeight: 0.2,
		});
		const result = classifyConfidence(scored, {});
		expect(result.tier).toBe('exploratory');
		expect(result.label).toBe('Explore');
	});

	it('produces human-readable reason with actual task type names', () => {
		const scored = makeScoredStrategy({
			name: 'chain-of-thought',
			compositeScore: 0.40,
			confidenceWeight: 0.7,
			affinityScore: 0.6,
		});
		const result = classifyConfidence(scored, { reasoning: 10, analysis: 5, math: 2 });
		expect(result.tier).toBe('high');
		// Should reference actual task types, not percentages
		expect(result.reason).toContain('reasoning');
		expect(result.reason).not.toContain('%');
	});

	it('includes detail string for tooltip with work percentage', () => {
		const scored = makeScoredStrategy({
			name: 'step-by-step',
			compositeScore: 0.35,
			confidenceWeight: 0.6,
			affinityScore: 0.57,
		});
		const result = classifyConfidence(scored, { coding: 30, math: 2 });
		expect(result.detail).toContain('57%');
		expect(result.detail).toContain('coding');
	});

	it('never mentions bestFor types absent from user history', () => {
		const scored = makeScoredStrategy({
			name: 'step-by-step',
			compositeScore: 0.35,
			confidenceWeight: 0.6,
			affinityScore: 0.5,
		});
		// coding matches, but math does not exist in user's freq — should NOT appear
		const result = classifyConfidence(scored, { coding: 30 });
		expect(result.detail).toContain('coding');
		expect(result.detail).not.toContain('math');
		expect(result.detail).not.toContain('new territory');
	});

	it('returns diversity-focused moderate reason when diversityScore is high', () => {
		const scored = makeScoredStrategy({
			name: 'few-shot-scaffolding',
			compositeScore: 0.20,
			confidenceWeight: 0.3,
			affinityScore: 0.1,
			diversityScore: 0.8,
		});
		// few-shot bestFor: classification, extraction, formatting — none in user's freq
		const result = classifyConfidence(scored, { coding: 10 });
		expect(result.tier).toBe('moderate');
		expect(result.reason).toContain('different territory');
	});

	it('uses fallback detail when no bestFor types match user history', () => {
		const scored = makeScoredStrategy({
			name: 'few-shot-scaffolding',
			compositeScore: 0.20,
			confidenceWeight: 0.5,
			affinityScore: 0,
		});
		// few-shot bestFor: classification, extraction, formatting — none in user's freq
		const result = classifyConfidence(scored, { coding: 10, analysis: 5 });
		expect(result.detail).toBe('A different approach to complement your toolkit');
	});

	it('mentions gap when current strategies underperform on matched types', () => {
		const scored = makeScoredStrategy({
			name: 'step-by-step',
			compositeScore: 0.35,
			confidenceWeight: 0.6,
			affinityScore: 0.5,
			gapScore: 0.4,
		});
		const result = classifyConfidence(scored, { coding: 20, analysis: 10 });
		expect(result.detail).toContain('underperforming');
		expect(result.detail).toContain('coding');
	});

	it('tells users to keep forging when data is very low', () => {
		const scored = makeScoredStrategy({
			compositeScore: 0.02,
			confidenceWeight: 0.1,
		});
		const result = classifyConfidence(scored, {});
		expect(result.tier).toBe('exploratory');
		expect(result.detail).toContain('Keep forging');
	});

	it('includes secondary usage in detail when secondaryCount > 0', () => {
		const scored = makeScoredStrategy({
			name: 'step-by-step',
			compositeScore: 0.35,
			confidenceWeight: 0.6,
			affinityScore: 0.5,
		});
		const result = classifyConfidence(scored, { coding: 20 }, 5);
		expect(result.detail).toContain('5×');
		expect(result.detail).toContain('secondary');
	});

	it('does not mention secondary when secondaryCount is 0', () => {
		const scored = makeScoredStrategy({
			name: 'step-by-step',
			compositeScore: 0.35,
			confidenceWeight: 0.6,
			affinityScore: 0.5,
		});
		const result = classifyConfidence(scored, { coding: 20 }, 0);
		expect(result.detail).not.toContain('secondary');
	});

	it('uses secondary-aware reason in moderate tier when affinity is low', () => {
		const scored = makeScoredStrategy({
			name: 'few-shot-scaffolding',
			compositeScore: 0.20,
			confidenceWeight: 0.5,
			affinityScore: 0.1,
			diversityScore: 0.3,
		});
		// few-shot bestFor: classification, extraction, formatting — none match user types
		const result = classifyConfidence(scored, { coding: 10 }, 4);
		expect(result.tier).toBe('moderate');
		expect(result.reason).toContain('Already in your toolkit');
	});

	it('prefers affinity reason over secondary in moderate tier', () => {
		const scored = makeScoredStrategy({
			name: 'step-by-step',
			compositeScore: 0.20,
			confidenceWeight: 0.5,
			affinityScore: 0.5,
		});
		// step-by-step bestFor includes coding, which is in user's freq
		const result = classifyConfidence(scored, { coding: 20, analysis: 10 }, 3);
		expect(result.tier).toBe('moderate');
		expect(result.reason).toContain('coding');
		expect(result.reason).not.toContain('toolkit');
	});
});

// ---------------------------------------------------------------------------
// generateSecondaryInsights
// ---------------------------------------------------------------------------

describe('generateSecondaryInsights', () => {
	it('returns empty array when no secondary data', () => {
		const scored = makeScoredStrategy({
			tagAffinityBoost: 0,
			secondaryFamiliarityScore: 0,
			secondaryInfluencePct: 0,
		});
		const insights = generateSecondaryInsights(scored, 0, {});
		expect(insights).toEqual([]);
	});

	it('generates tag engagement insight when tagAffinityBoost > 0.1', () => {
		const scored = makeScoredStrategy({
			name: 'step-by-step',
			tagAffinityBoost: 0.5,
			secondaryFamiliarityScore: 0,
			secondaryInfluencePct: 0,
		});
		const tags = { 'chain-of-thought': { coding: 10, analysis: 5 } };
		const insights = generateSecondaryInsights(scored, 0, tags);
		const tagInsight = insights.find((i) => i.type === 'tag_engagement');
		expect(tagInsight).toBeDefined();
		expect(tagInsight!.message).toContain('coding');
		expect(tagInsight!.message).toContain('analysis');
	});

	it('generates familiarity insight when secondaryCount > 0 and familiarity > 0.1', () => {
		const scored = makeScoredStrategy({
			secondaryFamiliarityScore: 0.6,
			secondaryInfluencePct: 3,
		});
		const insights = generateSecondaryInsights(scored, 5, {});
		const famInsight = insights.find((i) => i.type === 'familiarity');
		expect(famInsight).toBeDefined();
		expect(famInsight!.message).toContain('5×');
		expect(famInsight!.message).toContain('3%');
	});

	it('generates frequency impact insight when influence > 5%', () => {
		const scored = makeScoredStrategy({
			secondaryInfluencePct: 15,
		});
		const insights = generateSecondaryInsights(scored, 0, {});
		const freqInsight = insights.find((i) => i.type === 'frequency_impact');
		expect(freqInsight).toBeDefined();
		expect(freqInsight!.message).toContain('15%');
	});

	it('sorts insights by impact descending', () => {
		const scored = makeScoredStrategy({
			name: 'step-by-step',
			tagAffinityBoost: 0.3,
			secondaryFamiliarityScore: 0.8,
			secondaryInfluencePct: 20,
		});
		const tags = { 'chain-of-thought': { coding: 10 } };
		const insights = generateSecondaryInsights(scored, 5, tags);
		expect(insights.length).toBeGreaterThanOrEqual(2);
		for (let i = 1; i < insights.length; i++) {
			expect(insights[i].impact).toBeLessThanOrEqual(insights[i - 1].impact);
		}
	});

	it('returns empty when all signals below thresholds', () => {
		const scored = makeScoredStrategy({
			tagAffinityBoost: 0.05,
			secondaryFamiliarityScore: 0.05,
			secondaryInfluencePct: 3,
		});
		const insights = generateSecondaryInsights(scored, 1, {});
		expect(insights).toEqual([]);
	});

	it('does not generate familiarity insight when secondaryCount is 0', () => {
		const scored = makeScoredStrategy({
			secondaryFamiliarityScore: 0.5,
			secondaryInfluencePct: 10,
		});
		const insights = generateSecondaryInsights(scored, 0, {});
		const famInsight = insights.find((i) => i.type === 'familiarity');
		expect(famInsight).toBeUndefined();
	});
});

// ---------------------------------------------------------------------------
// selectTopPerformer
// ---------------------------------------------------------------------------

describe('selectTopPerformer', () => {
	it('selects strategy with highest score meeting minimum count', () => {
		const result = selectTopPerformer(
			{ 'chain-of-thought': 5, 'co-star': 3, 'step-by-step': 1 },
			{ 'chain-of-thought': 0.85, 'co-star': 0.90, 'step-by-step': 0.95 },
		);
		expect(result).not.toBeNull();
		expect(result!.name).toBe('co-star');
		expect(result!.score).toBe(0.90);
	});

	it('returns null when no strategy meets minimum count', () => {
		const result = selectTopPerformer(
			{ 'chain-of-thought': 2, 'co-star': 1 },
			{ 'chain-of-thought': 0.9, 'co-star': 0.8 },
		);
		expect(result).toBeNull();
	});

	it('returns null for empty distribution', () => {
		expect(selectTopPerformer({}, {})).toBeNull();
	});

	it('breaks ties by higher count', () => {
		const result = selectTopPerformer(
			{ 'chain-of-thought': 10, 'co-star': 5 },
			{ 'chain-of-thought': 0.80, 'co-star': 0.80 },
		);
		expect(result!.name).toBe('chain-of-thought');
	});

	it('breaks count ties by alphabetical name', () => {
		const result = selectTopPerformer(
			{ 'co-star': 5, 'chain-of-thought': 5 },
			{ 'co-star': 0.80, 'chain-of-thought': 0.80 },
		);
		expect(result!.name).toBe('chain-of-thought');
	});

	it('skips strategies with no score data', () => {
		const result = selectTopPerformer(
			{ 'chain-of-thought': 5, 'co-star': 10 },
			{ 'chain-of-thought': 0.7 },
		);
		expect(result!.name).toBe('chain-of-thought');
	});

	it('marks count >= 5 as significant', () => {
		const result = selectTopPerformer(
			{ 'chain-of-thought': 5 },
			{ 'chain-of-thought': 0.8 },
		);
		expect(result!.isSignificant).toBe(true);
	});

	it('marks count < 5 as not significant', () => {
		const result = selectTopPerformer(
			{ 'chain-of-thought': 3 },
			{ 'chain-of-thought': 0.8 },
		);
		expect(result!.isSignificant).toBe(false);
	});

	it('respects custom minCount', () => {
		const result = selectTopPerformer(
			{ 'chain-of-thought': 4 },
			{ 'chain-of-thought': 0.8 },
			5,
		);
		expect(result).toBeNull();
	});
});

// ---------------------------------------------------------------------------
// computeRecommendations — integration tests
// ---------------------------------------------------------------------------

describe('computeRecommendations', () => {
	describe('edge cases', () => {
		it('returns null for empty distribution (no optimizations)', () => {
			const result = computeRecommendations({
				strategyDistribution: {},
				scoreByStrategy: {},
				taskTypesByStrategy: {},
			});
			expect(result).toBeNull();
		});

		it('returns null when all 10 strategies are tried', () => {
			const allUsed: Record<string, number> = {};
			const allScores: Record<string, number> = {};
			for (const s of [
				'chain-of-thought', 'co-star', 'risen', 'role-task-format',
				'few-shot-scaffolding', 'step-by-step', 'structured-output',
				'constraint-injection', 'context-enrichment', 'persona-assignment',
			]) {
				allUsed[s] = 1;
				allScores[s] = 0.8;
			}
			const result = computeRecommendations({
				strategyDistribution: allUsed,
				scoreByStrategy: allScores,
				taskTypesByStrategy: {},
			});
			expect(result).toBeNull();
		});

		it('handles only 1 optimization with low confidence', () => {
			const result = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 1 },
				scoreByStrategy: { 'chain-of-thought': 0.8 },
				taskTypesByStrategy: { 'chain-of-thought': { reasoning: 1 } },
			});
			expect(result).not.toBeNull();
			// With 1 optimization, confidence is very low
			expect(result!.strategy.confidenceWeight).toBeLessThan(0.2);
			expect(result!.confidence.tier).toBe('exploratory');
		});

		it('handles no task type data (pure exploration mode)', () => {
			const result = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 10, 'co-star': 5 },
				scoreByStrategy: { 'chain-of-thought': 0.7, 'co-star': 0.8 },
				taskTypesByStrategy: {},
			});
			expect(result).not.toBeNull();
			// All affinityScores should be 0
			for (const s of result!.ranked) {
				expect(s.affinityScore).toBe(0);
			}
		});

		it('handles strategies with no score data in gap analysis', () => {
			const result = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 5 },
				scoreByStrategy: {},
				taskTypesByStrategy: { 'chain-of-thought': { reasoning: 5 } },
			});
			expect(result).not.toBeNull();
			// Gap score should degrade gracefully (globalAvgScore is null → gap=0)
			for (const s of result!.ranked) {
				expect(s.gapScore).toBe(0);
			}
		});

		it('handles all optimizations being the same task type', () => {
			const result = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 20 },
				scoreByStrategy: { 'chain-of-thought': 0.75 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 20 } },
			});
			expect(result).not.toBeNull();
			// step-by-step (bestFor: coding, analysis, math) should rank high due to coding affinity
			const stepByStep = result!.ranked.find((s) => s.name === 'step-by-step');
			expect(stepByStep).toBeDefined();
			expect(stepByStep!.affinityScore).toBe(1.0); // coding matches 100%
		});
	});

	describe('ranking correctness', () => {
		it('ranks by composite score descending', () => {
			const result = computeRecommendations({
				strategyDistribution: {
					'chain-of-thought': 20,
					'co-star': 10,
				},
				scoreByStrategy: { 'chain-of-thought': 0.7, 'co-star': 0.6 },
				taskTypesByStrategy: {
					'chain-of-thought': { reasoning: 10, coding: 10 },
					'co-star': { writing: 5, creative: 5 },
				},
			});
			expect(result).not.toBeNull();
			const scores = result!.ranked.map((s) => s.compositeScore);
			for (let i = 1; i < scores.length; i++) {
				expect(scores[i]).toBeLessThanOrEqual(scores[i - 1]);
			}
		});

		it('breaks composite score ties alphabetically', () => {
			// With no task type data and same tried strategies, all untried get same signals
			const result = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 5 },
				scoreByStrategy: {},
				taskTypesByStrategy: {},
			});
			expect(result).not.toBeNull();
			const names = result!.ranked.map((s) => s.name);
			// All have compositeScore=0 (no affinity data, no gap data), should be alphabetical
			const sorted = [...names].sort();
			expect(names).toEqual(sorted);
		});

		it('the strategy property matches the first ranked entry', () => {
			const result = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 10 },
				scoreByStrategy: { 'chain-of-thought': 0.7 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 10 } },
			});
			expect(result).not.toBeNull();
			expect(result!.strategy).toBe(result!.ranked[0]);
		});
	});

	describe('worked example (Phase 2, Step 2.3)', () => {
		// User has done 15 optimizations: coding=8, writing=4, analysis=3
		// Tried: co-star (score 0.72), step-by-step (score 0.58)
		// co-star bestFor: [writing, creative, reasoning]
		// step-by-step bestFor: [coding, analysis, math]
		const input: RecommendationInput = {
			strategyDistribution: { 'co-star': 9, 'step-by-step': 6 },
			scoreByStrategy: { 'co-star': 0.72, 'step-by-step': 0.58 },
			taskTypesByStrategy: {
				'co-star': { writing: 4, analysis: 1 },
				'step-by-step': { coding: 8, analysis: 2 },
			},
		};

		it('produces valid recommendations with expected signals', () => {
			const result = computeRecommendations(input);
			expect(result).not.toBeNull();
			expect(result!.ranked.length).toBe(8); // 10 - 2 tried = 8 untried
		});

		it('chain-of-thought has affinity from analysis tasks', () => {
			const result = computeRecommendations(input)!;
			const cot = result.ranked.find((s) => s.name === 'chain-of-thought')!;
			// taskFreq: coding=8, writing=4, analysis=3 → total=15
			// cot bestFor: [reasoning, analysis, math] → matching: analysis=3
			// affinity = 3/15 = 0.2
			expect(cot.affinityScore).toBeCloseTo(3 / 15, 3);
		});

		it('constraint-injection has high affinity from coding tasks', () => {
			const result = computeRecommendations(input)!;
			const ci = result.ranked.find((s) => s.name === 'constraint-injection')!;
			// ci bestFor: [coding, medical, extraction] → matching: coding=8
			// affinity = 8/15 ≈ 0.533
			expect(ci.affinityScore).toBeCloseTo(8 / 15, 3);
		});

		it('confidence weight matches expected level for 15 optimizations', () => {
			const result = computeRecommendations(input)!;
			// confidence = 1 - 1/(1 + 15/10) = 1 - 1/2.5 = 0.6
			expect(result.strategy.confidenceWeight).toBeCloseTo(0.6, 3);
		});
	});

	describe('custom weights', () => {
		it('affinity-only weights produce affinity-driven ranking', () => {
			const result = computeRecommendations(
				{
					strategyDistribution: { 'co-star': 10 },
					scoreByStrategy: { 'co-star': 0.7 },
					taskTypesByStrategy: { 'co-star': { coding: 10 } },
				},
				{ affinity: 1, gap: 0, diversity: 0, secondary: 0 },
			);
			expect(result).not.toBeNull();
			// Strategies with coding in bestFor should rank highest
			const top = result!.strategy;
			// step-by-step, structured-output, constraint-injection all have 'coding' in bestFor
			expect(top.affinityScore).toBeGreaterThan(0);
		});

		it('diversity-only weights prefer uncovered task types', () => {
			const result = computeRecommendations(
				{
					strategyDistribution: { 'chain-of-thought': 10 },
					scoreByStrategy: { 'chain-of-thought': 0.9 },
					taskTypesByStrategy: { 'chain-of-thought': { reasoning: 10 } },
				},
				{ affinity: 0, gap: 0, diversity: 1, secondary: 0 },
			);
			expect(result).not.toBeNull();
			// chain-of-thought is well-served at reasoning. Strategies NOT targeting reasoning
			// should have higher diversity scores.
			const topDiv = result!.strategy.diversityScore;
			expect(topDiv).toBeGreaterThan(0);
		});
	});

	describe('secondary distribution integration', () => {
		it('populates secondaryFamiliarityScore for untried strategies with secondary usage', () => {
			const result = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 20 },
				scoreByStrategy: { 'chain-of-thought': 0.8 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 20 } },
				secondaryDistribution: { 'step-by-step': 5, 'co-star': 2 },
			});
			expect(result).not.toBeNull();
			const sbs = result!.ranked.find((s) => s.name === 'step-by-step')!;
			const cos = result!.ranked.find((s) => s.name === 'co-star')!;
			const rtf = result!.ranked.find((s) => s.name === 'role-task-format')!;
			// step-by-step: 5/5 = 1.0 (max)
			expect(sbs.secondaryFamiliarityScore).toBeCloseTo(1.0, 3);
			// co-star: 2/5 = 0.4
			expect(cos.secondaryFamiliarityScore).toBeCloseTo(0.4, 3);
			// role-task-format: 0 (no secondary usage)
			expect(rtf.secondaryFamiliarityScore).toBe(0);
		});

		it('boosts composite score for strategies with secondary usage', () => {
			const baseResult = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 20 },
				scoreByStrategy: { 'chain-of-thought': 0.8 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 20 } },
			});
			const boostedResult = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 20 },
				scoreByStrategy: { 'chain-of-thought': 0.8 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 20 } },
				secondaryDistribution: { 'step-by-step': 8 },
			});
			const baseSbs = baseResult!.ranked.find((s) => s.name === 'step-by-step')!;
			const boostedSbs = boostedResult!.ranked.find((s) => s.name === 'step-by-step')!;
			expect(boostedSbs.compositeScore).toBeGreaterThan(baseSbs.compositeScore);
		});

		it('defaults secondaryFamiliarityScore to 0 when no secondary data', () => {
			const result = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 10 },
				scoreByStrategy: { 'chain-of-thought': 0.7 },
				taskTypesByStrategy: {},
			});
			for (const s of result!.ranked) {
				expect(s.secondaryFamiliarityScore).toBe(0);
			}
		});

		it('populates new secondary sub-signals for strategies with secondary data', () => {
			const result = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 20 },
				scoreByStrategy: { 'chain-of-thought': 0.8 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 20 } },
				secondaryDistribution: { 'step-by-step': 5 },
			});
			const sbs = result!.ranked.find((s) => s.name === 'step-by-step')!;
			expect(sbs.frequencyScore).toBeGreaterThan(0);
			expect(sbs.reachScore).toBeGreaterThan(0);
			expect(sbs.secondaryComposite).toBeGreaterThan(0);
			expect(sbs.secondaryInfluencePct).toBeGreaterThan(0);
		});

		it('defaults all new secondary fields to 0 when no secondary data', () => {
			const result = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 10 },
				scoreByStrategy: { 'chain-of-thought': 0.7 },
				taskTypesByStrategy: {},
			});
			for (const s of result!.ranked) {
				expect(s.frequencyScore).toBe(0);
				expect(s.reachScore).toBe(0);
				expect(s.synergyScore).toBe(0);
				expect(s.secondaryComposite).toBe(0);
				expect(s.secondaryInfluencePct).toBe(0);
			}
		});
	});

	describe('tag affinity integration', () => {
		it('populates tagAffinityBoost for strategies whose bestFor matches tags', () => {
			const result = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 20 },
				scoreByStrategy: { 'chain-of-thought': 0.8 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 20 } },
				tagsByStrategy: { 'chain-of-thought': { coding: 10, analysis: 5 } },
			});
			expect(result).not.toBeNull();
			// step-by-step bestFor: [coding, analysis, math]
			// tags: coding=10, analysis=5, total=15
			// boost = (10 + 5) / 15 = 1.0
			const sbs = result!.ranked.find((s) => s.name === 'step-by-step')!;
			expect(sbs.tagAffinityBoost).toBeCloseTo(1.0, 3);
			// few-shot bestFor: [classification, extraction, formatting] — no tag matches
			const fss = result!.ranked.find((s) => s.name === 'few-shot-scaffolding')!;
			expect(fss.tagAffinityBoost).toBe(0);
		});

		it('boosts composite score when tags align with bestFor', () => {
			const baseResult = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 20 },
				scoreByStrategy: { 'chain-of-thought': 0.8 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 20 } },
			});
			const tagResult = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 20 },
				scoreByStrategy: { 'chain-of-thought': 0.8 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 20 } },
				tagsByStrategy: { 'chain-of-thought': { coding: 10, math: 5 } },
			});
			const baseSbs = baseResult!.ranked.find((s) => s.name === 'step-by-step')!;
			const tagSbs = tagResult!.ranked.find((s) => s.name === 'step-by-step')!;
			expect(tagSbs.compositeScore).toBeGreaterThan(baseSbs.compositeScore);
		});

		it('defaults tagAffinityBoost to 0 when no tag data', () => {
			const result = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 10 },
				scoreByStrategy: { 'chain-of-thought': 0.7 },
				taskTypesByStrategy: {},
			});
			for (const s of result!.ranked) {
				expect(s.tagAffinityBoost).toBe(0);
			}
		});
	});

	describe('secondary + tag combined', () => {
		it('both signals stack to boost composite score', () => {
			const baseResult = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 20 },
				scoreByStrategy: { 'chain-of-thought': 0.8 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 20 } },
			});
			const combinedResult = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 20 },
				scoreByStrategy: { 'chain-of-thought': 0.8 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 20 } },
				secondaryDistribution: { 'step-by-step': 5 },
				tagsByStrategy: { 'chain-of-thought': { coding: 10 } },
			});
			const baseSbs = baseResult!.ranked.find((s) => s.name === 'step-by-step')!;
			const combinedSbs = combinedResult!.ranked.find((s) => s.name === 'step-by-step')!;
			expect(combinedSbs.compositeScore).toBeGreaterThan(baseSbs.compositeScore);
			expect(combinedSbs.secondaryFamiliarityScore).toBeGreaterThan(0);
			expect(combinedSbs.tagAffinityBoost).toBeGreaterThan(0);
		});

		it('passes secondary count to classifyConfidence for top recommendation', () => {
			// constraint-injection ranks #1 here: bestFor [coding, medical, extraction]
			// gets gap=1.0 and diversity=1.0 since chain-of-thought doesn't cover those types
			const result = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 50 },
				scoreByStrategy: { 'chain-of-thought': 0.8 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 50 } },
				secondaryDistribution: { 'constraint-injection': 8 },
			});
			expect(result).not.toBeNull();
			expect(result!.strategy.name).toBe('constraint-injection');
			// Detail should mention secondary usage
			expect(result!.confidence.detail).toContain('8×');
			expect(result!.confidence.detail).toContain('secondary');
		});

		it('synergy score is non-zero when both familiarity and tag affinity are present', () => {
			const result = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 20 },
				scoreByStrategy: { 'chain-of-thought': 0.8 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 20 } },
				secondaryDistribution: { 'step-by-step': 5 },
				tagsByStrategy: { 'chain-of-thought': { coding: 10, analysis: 5 } },
			});
			const sbs = result!.ranked.find((s) => s.name === 'step-by-step')!;
			// step-by-step has both secondary usage and tag match → synergy > 0
			expect(sbs.synergyScore).toBeGreaterThan(0);
			expect(sbs.secondaryComposite).toBeGreaterThan(sbs.secondaryFamiliarityScore * 0.25);
		});
	});

	describe('insights integration', () => {
		it('includes insights array in recommendation result', () => {
			const result = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 20 },
				scoreByStrategy: { 'chain-of-thought': 0.8 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 20 } },
			});
			expect(result).not.toBeNull();
			expect(Array.isArray(result!.insights)).toBe(true);
		});

		it('generates insights when secondary data produces meaningful signals', () => {
			const result = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 50 },
				scoreByStrategy: { 'chain-of-thought': 0.8 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 50 } },
				secondaryDistribution: { 'constraint-injection': 10 },
				tagsByStrategy: { 'chain-of-thought': { coding: 20 } },
			});
			expect(result).not.toBeNull();
			// constraint-injection should be top with high secondary influence
			expect(result!.strategy.name).toBe('constraint-injection');
			expect(result!.insights.length).toBeGreaterThan(0);
		});

		it('returns empty insights when no secondary data', () => {
			const result = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 20 },
				scoreByStrategy: { 'chain-of-thought': 0.8 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 20 } },
			});
			expect(result!.insights).toEqual([]);
		});

		it('secondaryInfluencePct is computed correctly in pipeline', () => {
			const result = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 20 },
				scoreByStrategy: { 'chain-of-thought': 0.8 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 20 } },
				secondaryDistribution: { 'step-by-step': 8 },
			});
			const sbs = result!.ranked.find((s) => s.name === 'step-by-step')!;
			// secondaryInfluencePct should reflect the percentage contribution
			expect(sbs.secondaryInfluencePct).toBeGreaterThan(0);
			expect(sbs.secondaryInfluencePct).toBeLessThanOrEqual(100);
		});

		it('secondaryInfluencePct is 0 when no secondary data', () => {
			const result = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 20 },
				scoreByStrategy: { 'chain-of-thought': 0.8 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 20 } },
			});
			for (const s of result!.ranked) {
				expect(s.secondaryInfluencePct).toBe(0);
			}
		});
	});

	describe('enhanced analytics integration', () => {
		it('scoreMatrix enhances affinity with need-weighted scoring', () => {
			const baseResult = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 10, 'co-star': 10 },
				scoreByStrategy: { 'chain-of-thought': 0.7, 'co-star': 0.5 },
				taskTypesByStrategy: {
					'chain-of-thought': { reasoning: 10 },
					'co-star': { writing: 5, coding: 5 },
				},
			});
			const matrixResult = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 10, 'co-star': 10 },
				scoreByStrategy: { 'chain-of-thought': 0.7, 'co-star': 0.5 },
				taskTypesByStrategy: {
					'chain-of-thought': { reasoning: 10 },
					'co-star': { writing: 5, coding: 5 },
				},
				scoreMatrix: {
					'chain-of-thought': { reasoning: { count: 10, avg_score: 0.7 } },
					'co-star': {
						writing: { count: 5, avg_score: 0.8 },
						coding: { count: 5, avg_score: 0.3 },
					},
				},
			});
			// With scoreMatrix, strategies targeting low-performing coding tasks
			// should get different affinity scores
			expect(baseResult).not.toBeNull();
			expect(matrixResult).not.toBeNull();
			const baseCI = baseResult!.ranked.find(s => s.name === 'constraint-injection');
			const matrixCI = matrixResult!.ranked.find(s => s.name === 'constraint-injection');
			// constraint-injection bestFor includes coding — enhanced affinity should differ
			expect(baseCI!.affinityScore).not.toBe(matrixCI!.affinityScore);
		});

		it('scoreMatrix enhances gap analysis with per-task-type scores', () => {
			const matrixResult = computeRecommendations({
				strategyDistribution: { 'co-star': 10 },
				scoreByStrategy: { 'co-star': 0.7 },
				taskTypesByStrategy: {
					'co-star': { writing: 5, coding: 5 },
				},
				scoreMatrix: {
					'co-star': {
						writing: { count: 5, avg_score: 0.9 },
						coding: { count: 5, avg_score: 0.3 },
					},
				},
			});
			expect(matrixResult).not.toBeNull();
			// Strategies targeting coding (where co-star scores 0.3) should have higher gap
			const sbs = matrixResult!.ranked.find(s => s.name === 'step-by-step');
			// step-by-step bestFor: [coding, analysis, math] — coding has low score → gap
			expect(sbs!.gapScore).toBeGreaterThan(0);
		});

		it('comboEffectiveness boosts composite score for strategies used as secondaries', () => {
			const baseResult = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 20 },
				scoreByStrategy: { 'chain-of-thought': 0.8 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 20 } },
			});
			const comboResult = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 20 },
				scoreByStrategy: { 'chain-of-thought': 0.8 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 20 } },
				comboEffectiveness: {
					'chain-of-thought': {
						'step-by-step': { count: 10, avg_score: 0.9 },
					},
				},
			});
			const baseSbs = baseResult!.ranked.find(s => s.name === 'step-by-step')!;
			const comboSbs = comboResult!.ranked.find(s => s.name === 'step-by-step')!;
			expect(comboSbs.compositeScore).toBeGreaterThan(baseSbs.compositeScore);
		});

		it('scoreVariance populates scoreStddev on scored strategies', () => {
			const result = computeRecommendations({
				strategyDistribution: { 'chain-of-thought': 20 },
				scoreByStrategy: { 'chain-of-thought': 0.8 },
				taskTypesByStrategy: { 'chain-of-thought': { coding: 20 } },
				scoreVariance: {
					'step-by-step': { min: 0.5, max: 1.0, avg: 0.75, stddev: 0.15, count: 10 },
				},
			});
			const sbs = result!.ranked.find(s => s.name === 'step-by-step')!;
			expect(sbs.scoreStddev).toBe(0.15);
		});

		it('backward compatible: no analytics fields produces same results as before', () => {
			const input: RecommendationInput = {
				strategyDistribution: { 'chain-of-thought': 15, 'co-star': 5 },
				scoreByStrategy: { 'chain-of-thought': 0.8, 'co-star': 0.6 },
				taskTypesByStrategy: {
					'chain-of-thought': { reasoning: 10, coding: 5 },
					'co-star': { writing: 5 },
				},
			};
			const result = computeRecommendations(input);
			expect(result).not.toBeNull();
			expect(result!.ranked.length).toBe(8); // 10 - 2 tried
			// All strategies should still have valid scores
			for (const s of result!.ranked) {
				expect(s.compositeScore).toBeGreaterThanOrEqual(0);
				expect(s.scoreStddev).toBeUndefined(); // no variance data
			}
		});
	});
});

// ---------------------------------------------------------------------------
// computeComboScore
// ---------------------------------------------------------------------------

describe('computeComboScore', () => {
	it('returns 0 when no combo effectiveness data', () => {
		expect(computeComboScore('step-by-step', {}, 0.7)).toBe(0);
	});

	it('returns 0 when strategy has no secondary appearances', () => {
		const combo = {
			'chain-of-thought': { 'co-star': { count: 5, avg_score: 0.8 } },
		};
		expect(computeComboScore('step-by-step', combo, 0.7)).toBe(0);
	});

	it('returns 0 when globalAvgScore is null', () => {
		const combo = {
			'chain-of-thought': { 'step-by-step': { count: 5, avg_score: 0.8 } },
		};
		expect(computeComboScore('step-by-step', combo, null)).toBe(0);
	});

	it('computes normalized score relative to global average', () => {
		const combo = {
			'chain-of-thought': { 'step-by-step': { count: 10, avg_score: 0.9 } },
			'co-star': { 'step-by-step': { count: 5, avg_score: 0.7 } },
		};
		const score = computeComboScore('step-by-step', combo, 0.7);
		// Weighted avg: (0.9*10 + 0.7*5) / 15 ≈ 0.833
		// Normalized: 0.833 / 0.7 ≈ 1.0 (clamped)
		expect(score).toBeGreaterThan(0);
		expect(score).toBeLessThanOrEqual(1);
	});

	it('returns fractional value when combo avg is below global avg', () => {
		const combo = {
			'chain-of-thought': { 'step-by-step': { count: 10, avg_score: 0.3 } },
		};
		const score = computeComboScore('step-by-step', combo, 0.7);
		// 0.3 / 0.7 ≈ 0.43
		expect(score).toBeCloseTo(0.3 / 0.7, 3);
	});
});

// ---------------------------------------------------------------------------
// selectTopPerformer with variance
// ---------------------------------------------------------------------------

describe('selectTopPerformer with variance', () => {
	it('breaks ties by lower stddev when scores are equal', () => {
		const result = selectTopPerformer(
			{ 'chain-of-thought': 5, 'co-star': 5 },
			{ 'chain-of-thought': 0.80, 'co-star': 0.80 },
			3,
			{
				'chain-of-thought': { min: 0.6, max: 1.0, avg: 0.8, stddev: 0.15, count: 5 },
				'co-star': { min: 0.7, max: 0.9, avg: 0.8, stddev: 0.05, count: 5 },
			},
		);
		// co-star has lower stddev → preferred
		expect(result!.name).toBe('co-star');
	});

	it('still uses score as primary comparator with variance data', () => {
		const result = selectTopPerformer(
			{ 'chain-of-thought': 5, 'co-star': 5 },
			{ 'chain-of-thought': 0.90, 'co-star': 0.80 },
			3,
			{
				'chain-of-thought': { min: 0.5, max: 1.0, avg: 0.9, stddev: 0.20, count: 5 },
				'co-star': { min: 0.7, max: 0.9, avg: 0.8, stddev: 0.01, count: 5 },
			},
		);
		// chain-of-thought has higher score, even though higher stddev
		expect(result!.name).toBe('chain-of-thought');
	});

	it('falls back to count then name when no variance data', () => {
		const result = selectTopPerformer(
			{ 'chain-of-thought': 10, 'co-star': 5 },
			{ 'chain-of-thought': 0.80, 'co-star': 0.80 },
			3,
		);
		expect(result!.name).toBe('chain-of-thought');
	});
});

// ---------------------------------------------------------------------------
// computeAffinityScore with scoreMatrix
// ---------------------------------------------------------------------------

describe('computeAffinityScore with scoreMatrix', () => {
	it('weights frequency by need factor when scoreMatrix provided', () => {
		// Tasks: coding=10, writing=5 → total=15
		// Without matrix: affinity for bestFor=[coding] = 10/15 ≈ 0.667
		const basic = computeAffinityScore(['coding'], { coding: 10, writing: 5 }, 15);
		expect(basic).toBeCloseTo(10 / 15, 3);

		// With matrix: coding has low avg (0.3), writing has high avg (0.9)
		// needFactor for coding = 1 + (1 - 0.3) = 1.7
		// needFactor for writing = 1 + (1 - 0.9) = 1.1
		// weightedTotal = 10*1.7 + 5*1.1 = 17 + 5.5 = 22.5
		// weightedMatch(coding) = 10*1.7 = 17
		// enhanced = 17 / 22.5 ≈ 0.756
		const matrix = {
			'co-star': {
				coding: { count: 10, avg_score: 0.3 },
				writing: { count: 5, avg_score: 0.9 },
			},
		};
		const enhanced = computeAffinityScore(['coding'], { coding: 10, writing: 5 }, 15, matrix);
		expect(enhanced).toBeCloseTo(17 / 22.5, 3);
		expect(enhanced).toBeGreaterThan(basic);
	});

	it('falls back to pure frequency when scoreMatrix has no score data', () => {
		const matrix = {
			'co-star': {
				coding: { count: 10, avg_score: null },
			},
		};
		const score = computeAffinityScore(['coding'], { coding: 10, writing: 5 }, 15, matrix);
		// Falls back to basic: 10/15
		expect(score).toBeCloseTo(10 / 15, 3);
	});
});
