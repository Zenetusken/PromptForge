import { describe, it, expect } from 'vitest';
import { generateScoreExplanation } from './scoreExplanation';

describe('generateScoreExplanation', () => {
	it('generates a coherent narrative for high scores', () => {
		const explanation = generateScoreExplanation({
			clarity: 0.95,
			specificity: 0.90,
			structure: 0.97,
			faithfulness: 0.93,
			conciseness: 0.88,
			overall: 0.93,
		});
		expect(explanation).toContain('overall score of 93');
		// Faithfulness has the highest weight (25%)
		expect(explanation).toContain('Faithfulness highest at 25%');
	});

	it('identifies the top contributor correctly', () => {
		// faithfulness=100 × 0.25 = 25 pts (highest contribution)
		const explanation = generateScoreExplanation({
			clarity: 0.50,
			specificity: 0.50,
			structure: 0.50,
			faithfulness: 1.0,
			conciseness: 0.50,
			overall: 0.60,
		});
		expect(explanation).toContain('primarily driven by Faithfulness');
	});

	it('identifies the lowest contributor correctly', () => {
		// structure=10 × 0.15 = 1.5 pts (lowest contribution)
		const explanation = generateScoreExplanation({
			clarity: 0.80,
			specificity: 0.80,
			structure: 0.10,
			faithfulness: 0.80,
			conciseness: 0.80,
			overall: 0.64,
		});
		expect(explanation).toContain('Structure');
		expect(explanation).toContain('lowest contribution');
	});

	it('handles already-normalized scores (0-100 range)', () => {
		const explanation = generateScoreExplanation({
			clarity: 80,
			specificity: 70,
			structure: 90,
			faithfulness: 85,
			conciseness: 75,
			overall: 80,
		});
		expect(explanation).toContain('overall score of 80');
	});

	it('includes framework adherence when present', () => {
		const explanation = generateScoreExplanation({
			clarity: 0.80,
			specificity: 0.70,
			structure: 0.75,
			faithfulness: 0.85,
			conciseness: 0.72,
			overall: 0.77,
			framework_adherence: 0.65,
		});
		expect(explanation).toContain('Strategy Fit scored 65');
		expect(explanation).toContain('supplementary, not in weighted average');
	});

	it('omits framework adherence when absent', () => {
		const explanation = generateScoreExplanation({
			clarity: 0.80,
			specificity: 0.70,
			structure: 0.75,
			faithfulness: 0.85,
			conciseness: 0.72,
			overall: 0.77,
		});
		expect(explanation).not.toContain('Strategy Fit');
		expect(explanation).not.toContain('supplementary');
	});
});
