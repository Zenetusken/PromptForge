/**
 * Client-side keyword-based task type estimation.
 * No LLM call — purely pattern-based heuristic for real-time analysis.
 */

import type { TaskTypeName } from './taskTypes';

/** Pattern definition for a task type: keyword sets with optional negative keywords. */
interface TaskTypePattern {
	type: TaskTypeName;
	/** Primary keywords — presence strongly indicates this task type. */
	keywords: string[];
	/** Negative keywords — presence reduces confidence. */
	negative?: string[];
	/** Base confidence when any keyword matches (0-1). */
	baseConfidence: number;
}

const PATTERNS: TaskTypePattern[] = [
	{
		type: 'coding',
		keywords: [
			'code', 'function', 'implement', 'debug', 'refactor', 'api', 'endpoint',
			'class', 'method', 'variable', 'algorithm', 'program', 'script',
			'typescript', 'javascript', 'python', 'rust', 'java', 'sql', 'html', 'css',
			'git', 'deploy', 'build', 'compile', 'test', 'unit test', 'integration test',
			'bug', 'error handling', 'exception', 'stack trace', 'lint',
		],
		baseConfidence: 0.75,
	},
	{
		type: 'analysis',
		keywords: [
			'analyze', 'analysis', 'evaluate', 'assess', 'compare', 'benchmark',
			'metrics', 'data', 'trend', 'pattern', 'insight', 'report',
			'breakdown', 'investigate', 'audit', 'review', 'pros and cons',
		],
		baseConfidence: 0.70,
	},
	{
		type: 'reasoning',
		keywords: [
			'reason', 'logic', 'deduce', 'infer', 'argue', 'hypothesis',
			'proof', 'theorem', 'explain why', 'think through', 'consider',
			'implications', 'cause and effect', 'decision', 'trade-off',
		],
		baseConfidence: 0.65,
	},
	{
		type: 'math',
		keywords: [
			'calculate', 'compute', 'equation', 'formula', 'derivative',
			'integral', 'probability', 'statistics', 'algebra', 'geometry',
			'matrix', 'vector', 'solve', 'proof', 'mathematical',
		],
		baseConfidence: 0.80,
	},
	{
		type: 'writing',
		keywords: [
			'write', 'draft', 'compose', 'email', 'letter', 'article',
			'blog', 'copy', 'content', 'headline', 'subject line',
			'paragraph', 'essay', 'press release', 'announcement',
		],
		negative: ['code', 'function', 'implement'],
		baseConfidence: 0.70,
	},
	{
		type: 'creative',
		keywords: [
			'creative', 'story', 'poem', 'fiction', 'narrative', 'character',
			'dialogue', 'scene', 'plot', 'brainstorm', 'imagine', 'invent',
			'design', 'concept', 'brand', 'slogan', 'tagline', 'campaign',
		],
		baseConfidence: 0.75,
	},
	{
		type: 'extraction',
		keywords: [
			'extract', 'parse', 'scrape', 'pull out', 'identify', 'find all',
			'list all', 'gather', 'collect', 'mine', 'regex', 'pattern match',
			'named entity', 'key information',
		],
		baseConfidence: 0.75,
	},
	{
		type: 'classification',
		keywords: [
			'classify', 'categorize', 'label', 'tag', 'sort', 'bucket',
			'sentiment', 'positive', 'negative', 'neutral', 'spam',
			'topic', 'group', 'cluster',
		],
		baseConfidence: 0.75,
	},
	{
		type: 'formatting',
		keywords: [
			'format', 'json', 'csv', 'table', 'markdown', 'xml', 'yaml',
			'template', 'structure', 'schema', 'layout', 'convert',
			'transform', 'restructure',
		],
		baseConfidence: 0.70,
	},
	{
		type: 'medical',
		keywords: [
			'medical', 'clinical', 'patient', 'diagnosis', 'symptom',
			'treatment', 'drug', 'medication', 'healthcare', 'disease',
			'therapy', 'condition', 'prognosis',
		],
		baseConfidence: 0.80,
	},
	{
		type: 'legal',
		keywords: [
			'legal', 'law', 'contract', 'clause', 'compliance', 'regulation',
			'statute', 'liability', 'court', 'attorney', 'plaintiff',
			'defendant', 'jurisdiction', 'intellectual property',
		],
		baseConfidence: 0.80,
	},
	{
		type: 'education',
		keywords: [
			'teach', 'learn', 'explain', 'tutorial', 'lesson', 'curriculum',
			'student', 'course', 'quiz', 'exercise', 'example', 'beginner',
			'step by step', 'guide', 'how to',
		],
		negative: ['code', 'api', 'function'],
		baseConfidence: 0.60,
	},
];

export interface HeuristicResult {
	taskType: TaskTypeName;
	confidence: number;
	matchedKeywords: string[];
}

/**
 * Estimate the task type of a prompt using keyword matching.
 * Returns null if no pattern matches with sufficient confidence.
 */
export function estimateTaskType(text: string): HeuristicResult | null {
	if (!text || text.length < 20) return null;

	const lower = text.toLowerCase();
	let bestResult: HeuristicResult | null = null;

	for (const pattern of PATTERNS) {
		const matched: string[] = [];
		for (const kw of pattern.keywords) {
			if (lower.includes(kw)) {
				matched.push(kw);
			}
		}

		if (matched.length === 0) continue;

		// Check negative keywords
		let negativeHits = 0;
		if (pattern.negative) {
			for (const neg of pattern.negative) {
				if (lower.includes(neg)) negativeHits++;
			}
		}

		// Confidence scales with number of keyword matches, reduced by negatives
		const matchRatio = Math.min(matched.length / 3, 1); // 3+ matches = full match ratio
		const negativePenalty = negativeHits * 0.15;
		const confidence = Math.max(0, pattern.baseConfidence * matchRatio - negativePenalty);

		if (confidence < 0.3) continue;

		if (!bestResult || confidence > bestResult.confidence) {
			bestResult = {
				taskType: pattern.type,
				confidence,
				matchedKeywords: matched.slice(0, 5),
			};
		}
	}

	return bestResult;
}
