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
		promptAnalysis.analyzePrompt('## Role\nYou are a {{name}} assistant');
		promptAnalysis.reset();
		expect(promptAnalysis.heuristic).toBeNull();
		expect(promptAnalysis.recommendedStrategies).toEqual([]);
		expect(promptAnalysis.sections).toEqual([]);
		expect(promptAnalysis.variables).toEqual([]);
		expect(promptAnalysis.isAnalyzing).toBe(false);
	});

	it('populates sections immediately (no debounce)', () => {
		promptAnalysis.analyzePrompt('## Role\nYou are an assistant\n\n## Steps\n1. Do things');
		// Sections should be available immediately — no timer advance needed
		expect(promptAnalysis.sections.length).toBe(2);
		expect(promptAnalysis.sections[0].type).toBe('role');
		expect(promptAnalysis.sections[0].lineNumber).toBe(1);
		expect(promptAnalysis.sections[1].type).toBe('steps');
		expect(promptAnalysis.sections[1].lineNumber).toBe(4);
	});

	it('populates variables immediately (no debounce)', () => {
		promptAnalysis.analyzePrompt('Hello {{name}}, your role is {{role}}.');
		expect(promptAnalysis.variables.length).toBe(2);
		expect(promptAnalysis.variables.map(v => v.name)).toContain('name');
		expect(promptAnalysis.variables.map(v => v.name)).toContain('role');
	});

	it('clears sections/variables for empty text', () => {
		promptAnalysis.analyzePrompt('## Role\nAssistant with {{name}}');
		expect(promptAnalysis.sections.length).toBeGreaterThan(0);
		expect(promptAnalysis.variables.length).toBeGreaterThan(0);
		promptAnalysis.analyzePrompt('');
		expect(promptAnalysis.sections).toEqual([]);
		expect(promptAnalysis.variables).toEqual([]);
	});

	it('computes sections/variables even for short text (< 50 chars)', () => {
		promptAnalysis.analyzePrompt('## Role\n{{x}}');
		// Heuristic should be null (too short) but sections/variables should populate
		expect(promptAnalysis.heuristic).toBeNull();
		expect(promptAnalysis.sections.length).toBe(1);
		expect(promptAnalysis.variables.length).toBe(1);
	});
});
