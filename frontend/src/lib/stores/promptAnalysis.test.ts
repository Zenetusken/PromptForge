import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Mock dependencies
vi.mock('$lib/stores/stats.svelte', () => ({
	statsState: {
		stats: null,
	},
}));

import { promptAnalysis } from './promptAnalysis.svelte';

describe('PromptAnalysisState', () => {
	beforeEach(() => {
		promptAnalysis.reset();
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('starts with null heuristic', () => {
		expect(promptAnalysis.heuristic).toBeNull();
	});

	it('starts with empty recommendations', () => {
		expect(promptAnalysis.recommendedStrategies).toEqual([]);
	});

	it('returns null for short text', () => {
		promptAnalysis.analyzePrompt('hello');
		vi.advanceTimersByTime(400);
		expect(promptAnalysis.heuristic).toBeNull();
	});

	it('analyzes coding prompts after debounce', () => {
		promptAnalysis.analyzePrompt(
			'Write a Python function that implements a binary search algorithm with proper error handling and unit tests.'
		);
		expect(promptAnalysis.isAnalyzing).toBe(true);
		vi.advanceTimersByTime(400);
		expect(promptAnalysis.heuristic).not.toBeNull();
		expect(promptAnalysis.heuristic!.taskType).toBe('coding');
		expect(promptAnalysis.isAnalyzing).toBe(false);
	});

	it('debounces multiple rapid calls', () => {
		promptAnalysis.analyzePrompt('Write a function that sorts data efficiently');
		promptAnalysis.analyzePrompt('Write a Python function that sorts data and returns results efficiently in sorted order');
		vi.advanceTimersByTime(400);
		// Only the last call should produce a result
		expect(promptAnalysis.heuristic).not.toBeNull();
	});

	it('updateFromPipeline overrides heuristic with confidence 1.0', () => {
		promptAnalysis.updateFromPipeline('coding', 'moderate');
		expect(promptAnalysis.heuristic).not.toBeNull();
		expect(promptAnalysis.heuristic!.taskType).toBe('coding');
		expect(promptAnalysis.heuristic!.confidence).toBe(1.0);
	});

	it('reset clears all state', () => {
		promptAnalysis.updateFromPipeline('coding');
		promptAnalysis.reset();
		expect(promptAnalysis.heuristic).toBeNull();
		expect(promptAnalysis.recommendedStrategies).toEqual([]);
		expect(promptAnalysis.isAnalyzing).toBe(false);
	});
});
