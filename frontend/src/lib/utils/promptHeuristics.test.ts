import { describe, it, expect } from 'vitest';
import { estimateTaskType } from './promptHeuristics';

describe('estimateTaskType', () => {
	it('returns null for empty text', () => {
		expect(estimateTaskType('')).toBeNull();
	});

	it('returns null for very short text', () => {
		expect(estimateTaskType('hello world')).toBeNull();
	});

	it('detects coding prompts', () => {
		const result = estimateTaskType(
			'Write a Python function that takes a list of numbers and returns the sorted unique values. Include error handling for invalid inputs.'
		);
		expect(result).not.toBeNull();
		expect(result!.taskType).toBe('coding');
		expect(result!.confidence).toBeGreaterThan(0.4);
	});

	it('detects writing prompts', () => {
		const result = estimateTaskType(
			'Write a compelling marketing email for our new product launch. Include a subject line, hero section, and call-to-action.'
		);
		expect(result).not.toBeNull();
		expect(result!.taskType).toBe('writing');
	});

	it('detects analysis prompts', () => {
		const result = estimateTaskType(
			'Analyze the quarterly sales data and provide a breakdown of trends, patterns, and key metrics across all regions.'
		);
		expect(result).not.toBeNull();
		expect(result!.taskType).toBe('analysis');
	});

	it('detects extraction prompts', () => {
		const result = estimateTaskType(
			'Extract all email addresses and phone numbers from the following text. List all named entities found.'
		);
		expect(result).not.toBeNull();
		expect(result!.taskType).toBe('extraction');
	});

	it('detects classification prompts', () => {
		const result = estimateTaskType(
			'Classify the following customer reviews by sentiment (positive, negative, neutral) and categorize by topic.'
		);
		expect(result).not.toBeNull();
		expect(result!.taskType).toBe('classification');
	});

	it('detects creative prompts', () => {
		const result = estimateTaskType(
			'Write a short story about a character who discovers a hidden world. Include vivid dialogue and scene descriptions.'
		);
		expect(result).not.toBeNull();
		expect(result!.taskType).toBe('creative');
	});

	it('detects formatting prompts', () => {
		const result = estimateTaskType(
			'Convert the following data into a JSON schema with proper structure. Include a table format for the output.'
		);
		expect(result).not.toBeNull();
		expect(result!.taskType).toBe('formatting');
	});

	it('returns matched keywords', () => {
		const result = estimateTaskType(
			'Implement a REST API endpoint that handles user authentication and returns a JWT token.'
		);
		expect(result).not.toBeNull();
		expect(result!.matchedKeywords.length).toBeGreaterThan(0);
	});

	it('handles ambiguous prompts by picking highest confidence', () => {
		const result = estimateTaskType(
			'Analyze and write code to implement a data pipeline that extracts information from CSV files.'
		);
		expect(result).not.toBeNull();
		// Should pick the type with the most keyword matches
		expect(result!.confidence).toBeGreaterThan(0.3);
	});
});
