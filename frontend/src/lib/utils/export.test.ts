import { describe, it, expect, vi, afterEach } from 'vitest';
import {
	slugifyTitle,
	generateExportMarkdown,
	codeFence,
	buildScoreTable,
	buildMetadataTable,
	buildFooter,
} from './export';
import type { OptimizationResultState } from '$lib/stores/optimization.svelte';

function makeResult(overrides: Partial<OptimizationResultState> = {}): OptimizationResultState {
	return {
		id: 'test-id-abc123',
		original: 'Raw prompt text',
		optimized: 'Optimized prompt text',
		task_type: 'coding',
		complexity: 'medium',
		weaknesses: [],
		strengths: [],
		changes_made: [],
		framework_applied: 'role-based',
		optimization_notes: '',
		scores: { clarity: 0.9, specificity: 0.8, structure: 0.7, faithfulness: 0.85, overall: 0.81 },
		is_improvement: true,
		verdict: '',
		duration_ms: 1500,
		model_used: '',
		input_tokens: 100,
		output_tokens: 50,
		title: '',
		project: '',
		project_id: '',
		project_status: '',
		tags: [],
		strategy: '',
		strategy_reasoning: '',
		strategy_confidence: 0.9,
		secondary_frameworks: [],
		...overrides,
	};
}

describe('slugifyTitle', () => {
	it('lowercases and replaces spaces with hyphens', () => {
		expect(slugifyTitle('My Great Prompt')).toBe('my-great-prompt');
	});

	it('strips special characters', () => {
		expect(slugifyTitle('Hello! @World #2024')).toBe('hello-world-2024');
	});

	it('collapses consecutive non-alphanumeric chars', () => {
		expect(slugifyTitle('a---b___c')).toBe('a-b-c');
	});

	it('trims leading and trailing hyphens', () => {
		expect(slugifyTitle('---title---')).toBe('title');
	});

	it('handles empty string', () => {
		expect(slugifyTitle('')).toBe('');
	});

	it('handles unicode by stripping non-ascii', () => {
		expect(slugifyTitle('café résumé')).toBe('caf-r-sum');
	});
});

describe('codeFence', () => {
	it('wraps content in triple backtick fence', () => {
		expect(codeFence('hello world')).toBe('```\nhello world\n```');
	});

	it('extends fence when content contains triple backticks', () => {
		const content = 'some ```code``` here';
		const result = codeFence(content);
		expect(result).toBe('````\nsome ```code``` here\n````');
	});

	it('extends fence further for nested fences', () => {
		const content = 'outer ````\ninner ```\n````';
		const result = codeFence(content);
		expect(result).toMatch(/^`{5}\n/);
		expect(result).toMatch(/\n`{5}$/);
	});
});

describe('buildScoreTable', () => {
	it('produces a markdown table with header and 5 data rows', () => {
		const scores = { clarity: 0.9, specificity: 0.8, structure: 0.7, faithfulness: 0.85, overall: 0.81 };
		const rows = buildScoreTable(scores);
		expect(rows).toHaveLength(7); // header + separator + 5 data
		expect(rows[0]).toBe('| Metric | Score | Rating |');
		expect(rows[1]).toContain('---');
	});

	it('bolds the Overall row', () => {
		const scores = { clarity: 0.9, specificity: 0.8, structure: 0.7, faithfulness: 0.85, overall: 0.81 };
		const rows = buildScoreTable(scores);
		expect(rows[2]).toContain('**Overall**');
		expect(rows[2]).toContain('81/100');
		expect(rows[2]).toContain('Good');
	});

	it('includes Rating column with tier labels', () => {
		const scores = { clarity: 0.3, specificity: 0.5, structure: 0.8, faithfulness: 0.0, overall: 0.45 };
		const rows = buildScoreTable(scores);
		// Overall 45 => Fair
		expect(rows[2]).toContain('Fair');
		// Clarity 30 => Low
		expect(rows[3]).toContain('Low');
		// Specificity 50 => Fair
		expect(rows[4]).toContain('Fair');
		// Structure 80 => Good
		expect(rows[5]).toContain('Good');
	});

	it('handles zero scores', () => {
		const scores = { clarity: 0, specificity: 0, structure: 0, faithfulness: 0, overall: 0 };
		const rows = buildScoreTable(scores);
		expect(rows[2]).toContain('0/100');
	});
});

describe('buildMetadataTable', () => {
	it('always includes ID row', () => {
		const rows = buildMetadataTable(makeResult());
		const idRow = rows.find(r => r.includes('| ID |'));
		expect(idRow).toContain('test-id-abc123');
	});

	it('includes model when present', () => {
		const rows = buildMetadataTable(makeResult({ model_used: 'claude-opus-4-6' }));
		expect(rows.find(r => r.includes('| Model |'))).toContain('claude-opus-4-6');
	});

	it('omits model when empty', () => {
		const rows = buildMetadataTable(makeResult({ model_used: '' }));
		expect(rows.find(r => r.includes('| Model |'))).toBeUndefined();
	});

	it('formats duration as seconds', () => {
		const rows = buildMetadataTable(makeResult({ duration_ms: 12300 }));
		expect(rows.find(r => r.includes('| Duration |'))).toContain('12.3s');
	});

	it('omits duration when zero', () => {
		const rows = buildMetadataTable(makeResult({ duration_ms: 0 }));
		expect(rows.find(r => r.includes('| Duration |'))).toBeUndefined();
	});

	it('formats tokens with locale separators', () => {
		const rows = buildMetadataTable(makeResult({ input_tokens: 1247, output_tokens: 892 }));
		const tokenRow = rows.find(r => r.includes('| Tokens |'));
		expect(tokenRow).toContain('1,247 in');
		expect(tokenRow).toContain('892 out');
	});

	it('omits tokens when both are zero', () => {
		const rows = buildMetadataTable(makeResult({ input_tokens: 0, output_tokens: 0 }));
		expect(rows.find(r => r.includes('| Tokens |'))).toBeUndefined();
	});

	it('includes project with archived suffix', () => {
		const rows = buildMetadataTable(makeResult({ project: 'My Project', project_status: 'archived' }));
		expect(rows.find(r => r.includes('| Project |'))).toContain('My Project (archived)');
	});

	it('includes project without suffix when active', () => {
		const rows = buildMetadataTable(makeResult({ project: 'My Project', project_status: 'active' }));
		const row = rows.find(r => r.includes('| Project |'));
		expect(row).toContain('My Project');
		expect(row).not.toContain('(archived)');
	});

	it('includes tags as comma-separated list', () => {
		const rows = buildMetadataTable(makeResult({ tags: ['api', 'refactoring'] }));
		expect(rows.find(r => r.includes('| Tags |'))).toContain('api, refactoring');
	});

	it('omits tags when empty', () => {
		const rows = buildMetadataTable(makeResult({ tags: [] }));
		expect(rows.find(r => r.includes('| Tags |'))).toBeUndefined();
	});
});

describe('buildFooter', () => {
	afterEach(() => {
		vi.useRealTimers();
	});

	it('includes PromptForge branding and UTC date/time', () => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date('2026-02-18T14:32:00Z'));
		const footer = buildFooter();
		expect(footer).toBe('*Exported from PromptForge on 2026-02-18 at 14:32 UTC*');
	});

	it('zero-pads hours and minutes', () => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date('2026-01-05T03:07:00Z'));
		const footer = buildFooter();
		expect(footer).toContain('03:07 UTC');
	});
});

describe('generateExportMarkdown', () => {
	it('uses result title as heading when present', () => {
		const md = generateExportMarkdown(makeResult({ title: 'My Custom Title' }));
		expect(md).toMatch(/^# My Custom Title\n/);
	});

	it('falls back to "Optimized Prompt" when title is empty', () => {
		const md = generateExportMarkdown(makeResult({ title: '' }));
		expect(md).toMatch(/^# Optimized Prompt\n/);
	});

	it('wraps optimized prompt in a code fence under ## Optimized Prompt', () => {
		const md = generateExportMarkdown(makeResult({ optimized: 'Do the thing' }));
		expect(md).toContain('## Optimized Prompt\n\n```\nDo the thing\n```');
	});

	it('wraps original prompt in a code fence under ## Original Prompt', () => {
		const md = generateExportMarkdown(makeResult({ original: 'Raw text' }));
		expect(md).toContain('## Original Prompt\n\n```\nRaw text\n```');
	});

	it('extends code fence when prompt contains triple backticks', () => {
		const md = generateExportMarkdown(makeResult({ optimized: 'Use ```code``` blocks' }));
		expect(md).toContain('````\nUse ```code``` blocks\n````');
	});

	it('includes Changes Made section before Scores when present', () => {
		const md = generateExportMarkdown(makeResult({ changes_made: ['Added role', 'Added constraints'] }));
		expect(md).toContain('## Changes Made');
		expect(md).toContain('- Added role');
		expect(md).toContain('- Added constraints');
		// Changes Made should appear before Scores
		const changesIdx = md.indexOf('## Changes Made');
		const scoresIdx = md.indexOf('## Scores');
		expect(changesIdx).toBeLessThan(scoresIdx);
	});

	it('omits Changes Made section when empty', () => {
		const md = generateExportMarkdown(makeResult({ changes_made: [] }));
		expect(md).not.toContain('## Changes Made');
	});

	it('includes Scores section with markdown table', () => {
		const md = generateExportMarkdown(makeResult());
		expect(md).toContain('## Scores');
		expect(md).toContain('| Metric | Score | Rating |');
		expect(md).toContain('| **Overall** | 81/100 | Good |');
		expect(md).toContain('| Clarity | 90/100 | Good |');
		expect(md).toContain('| Specificity | 80/100 | Good |');
		expect(md).toContain('| Structure | 70/100 | Good |');
		expect(md).toContain('| Faithfulness | 85/100 | Good |');
	});

	it('includes verdict right after scores table when present', () => {
		const md = generateExportMarkdown(makeResult({ verdict: 'Significant improvement' }));
		expect(md).toContain('**Verdict:** Significant improvement');
		// Verdict should appear after Scores section
		const scoresIdx = md.indexOf('## Scores');
		const verdictIdx = md.indexOf('**Verdict:**');
		expect(verdictIdx).toBeGreaterThan(scoresIdx);
	});

	it('omits verdict when empty', () => {
		const md = generateExportMarkdown(makeResult({ verdict: '' }));
		expect(md).not.toContain('**Verdict:**');
	});

	it('includes Strategy section with name, confidence%, and reasoning', () => {
		const md = generateExportMarkdown(makeResult({
			strategy: 'chain-of-thought',
			strategy_confidence: 0.91,
			strategy_reasoning: 'Best fit for reasoning tasks',
		}));
		expect(md).toContain('## Strategy');
		expect(md).toContain('- **Strategy:** chain-of-thought');
		expect(md).toContain('- **Confidence:** 91%');
		expect(md).toContain('- **Reasoning:** Best fit for reasoning tasks');
	});

	it('omits Strategy section when no strategy data', () => {
		const md = generateExportMarkdown(makeResult({
			strategy: '',
			strategy_confidence: 0,
			strategy_reasoning: '',
		}));
		expect(md).not.toContain('## Strategy');
	});

	it('includes Analysis section with task type, complexity, framework, improvement', () => {
		const md = generateExportMarkdown(makeResult());
		expect(md).toContain('## Analysis');
		expect(md).toContain('- **Task Type:** coding');
		expect(md).toContain('- **Complexity:** medium');
		expect(md).toContain('- **Framework Applied:** role-based');
		expect(md).toContain('- **Improvement:** Yes');
	});

	it('shows "No" for is_improvement=false', () => {
		const md = generateExportMarkdown(makeResult({ is_improvement: false }));
		expect(md).toContain('- **Improvement:** No');
	});

	it('includes strengths as ### subsection of Analysis', () => {
		const md = generateExportMarkdown(makeResult({ strengths: ['Clear intent', 'Good structure'] }));
		expect(md).toContain('### Strengths');
		expect(md).toContain('- Clear intent');
		expect(md).toContain('- Good structure');
		// Should be after ## Analysis
		const analysisIdx = md.indexOf('## Analysis');
		const strengthsIdx = md.indexOf('### Strengths');
		expect(strengthsIdx).toBeGreaterThan(analysisIdx);
	});

	it('omits strengths subsection when empty', () => {
		const md = generateExportMarkdown(makeResult({ strengths: [] }));
		expect(md).not.toContain('### Strengths');
	});

	it('includes weaknesses as ### subsection of Analysis', () => {
		const md = generateExportMarkdown(makeResult({ weaknesses: ['Too vague', 'Missing context'] }));
		expect(md).toContain('### Weaknesses');
		expect(md).toContain('- Too vague');
		expect(md).toContain('- Missing context');
	});

	it('omits weaknesses subsection when empty', () => {
		const md = generateExportMarkdown(makeResult({ weaknesses: [] }));
		expect(md).not.toContain('### Weaknesses');
	});

	it('includes Notes section when present', () => {
		const md = generateExportMarkdown(makeResult({ optimization_notes: 'Applied chain-of-thought' }));
		expect(md).toContain('## Notes');
		expect(md).toContain('Applied chain-of-thought');
	});

	it('omits Notes section when empty', () => {
		const md = generateExportMarkdown(makeResult({ optimization_notes: '' }));
		expect(md).not.toContain('## Notes');
	});

	it('includes Metadata section with table', () => {
		const md = generateExportMarkdown(makeResult({
			model_used: 'claude-opus-4-6',
			duration_ms: 12300,
			input_tokens: 1247,
			output_tokens: 892,
			project: 'My Project',
			tags: ['api', 'refactoring'],
		}));
		expect(md).toContain('## Metadata');
		expect(md).toContain('| Model | claude-opus-4-6 |');
		expect(md).toContain('| Duration | 12.3s |');
		expect(md).toContain('| Tokens | 1,247 in / 892 out |');
		expect(md).toContain('| Project | My Project |');
		expect(md).toContain('| Tags | api, refactoring |');
		expect(md).toContain('| ID | test-id-abc123 |');
	});

	it('includes footer line', () => {
		const md = generateExportMarkdown(makeResult());
		expect(md).toContain('*Exported from PromptForge on');
		expect(md).toContain('UTC*');
	});

	it('handles zero scores gracefully', () => {
		const result = makeResult();
		result.scores = { clarity: 0, specificity: 0, structure: 0, faithfulness: 0, overall: 0 };
		const md = generateExportMarkdown(result);
		expect(md).toContain('| **Overall** | 0/100 |');
	});

	it('includes all optional sections in a full result', () => {
		const md = generateExportMarkdown(makeResult({
			title: 'Full Test',
			strategy: 'chain-of-thought',
			strategy_reasoning: 'Strategy reason',
			strategy_confidence: 0.85,
			model_used: 'gpt-4.1',
			project: 'proj',
			tags: ['a', 'b'],
			verdict: 'Great',
			strengths: ['s1'],
			weaknesses: ['w1'],
			changes_made: ['c1'],
			optimization_notes: 'notes',
			is_improvement: true,
		}));
		expect(md).toContain('# Full Test');
		expect(md).toContain('## Optimized Prompt');
		expect(md).toContain('## Original Prompt');
		expect(md).toContain('## Changes Made');
		expect(md).toContain('## Scores');
		expect(md).toContain('**Verdict:** Great');
		expect(md).toContain('## Strategy');
		expect(md).toContain('## Analysis');
		expect(md).toContain('### Strengths');
		expect(md).toContain('### Weaknesses');
		expect(md).toContain('## Notes');
		expect(md).toContain('## Metadata');
		expect(md).toContain('*Exported from PromptForge on');
	});

	it('sections appear in correct order', () => {
		const md = generateExportMarkdown(makeResult({
			changes_made: ['c1'],
			strategy: 'cot',
			strategy_confidence: 0.8,
			strengths: ['s1'],
			weaknesses: ['w1'],
			optimization_notes: 'notes',
			verdict: 'Good',
		}));
		const order = [
			'## Optimized Prompt',
			'## Original Prompt',
			'## Changes Made',
			'## Scores',
			'**Verdict:**',
			'## Strategy',
			'## Analysis',
			'### Strengths',
			'### Weaknesses',
			'## Notes',
			'## Metadata',
			'*Exported from PromptForge',
		];
		let lastIdx = -1;
		for (const section of order) {
			const idx = md.indexOf(section);
			expect(idx, `${section} should be present`).toBeGreaterThan(-1);
			expect(idx, `${section} should be after previous section`).toBeGreaterThan(lastIdx);
			lastIdx = idx;
		}
	});

	it('ends with a trailing newline', () => {
		const md = generateExportMarkdown(makeResult());
		expect(md).toMatch(/\n$/);
	});
});
