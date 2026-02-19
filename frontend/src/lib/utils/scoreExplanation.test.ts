import { describe, it, expect } from 'vitest';
import { generateScoreExplanation } from './scoreExplanation';

describe('generateScoreExplanation', () => {
	it('generates a coherent narrative for high scores', () => {
		const explanation = generateScoreExplanation({
			clarity: 0.95,
			specificity: 0.90,
			structure: 0.97,
			faithfulness: 0.93,
			overall: 0.94,
		});
		expect(explanation).toContain('overall score of 94');
		expect(explanation).toContain('Faithfulness highest at 30%');
	});

	it('identifies the top contributor correctly', () => {
		// faithfulness=100 × 0.30 = 30 pts (highest contribution)
		const explanation = generateScoreExplanation({
			clarity: 0.50,
			specificity: 0.50,
			structure: 0.50,
			faithfulness: 1.0,
			overall: 0.63,
		});
		expect(explanation).toContain('primarily driven by Faithfulness');
	});

	it('identifies the lowest contributor correctly', () => {
		// structure=10 × 0.20 = 2 pts (lowest contribution)
		const explanation = generateScoreExplanation({
			clarity: 0.80,
			specificity: 0.80,
			structure: 0.10,
			faithfulness: 0.80,
			overall: 0.66,
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
			overall: 81,
		});
		expect(explanation).toContain('overall score of 81');
	});
});
