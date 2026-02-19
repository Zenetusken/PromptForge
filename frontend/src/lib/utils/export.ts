import { normalizeScore, getScoreTierLabel } from '$lib/utils/format';
import { SCORE_WEIGHTS, type ScoreDimension } from '$lib/utils/scoreDimensions';
import { generateScoreExplanation } from '$lib/utils/scoreExplanation';
import type { OptimizationResultState } from '$lib/stores/optimization.svelte';

/**
 * Slugify a title for use as a markdown filename.
 * Lowercases, replaces non-alphanumeric runs with hyphens, trims leading/trailing hyphens.
 */
export function slugifyTitle(title: string): string {
	return title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

/**
 * Wrap text in a fenced code block, extending the fence delimiter if the content
 * itself contains triple backticks.
 */
export function codeFence(content: string): string {
	let fence = '```';
	while (content.includes(fence)) {
		fence += '`';
	}
	return `${fence}\n${content}\n${fence}`;
}

/**
 * Build markdown table rows for the scores section.
 * Dimensions listed first with their weights, Overall (bold) last.
 */
export function buildScoreTable(scores: OptimizationResultState['scores']): string[] {
	const rows: string[] = [
		'| Metric | Score | Weight | Rating |',
		'|--------|-------|--------|--------|',
	];

	const dimensions: { label: string; key: ScoreDimension }[] = [
		{ label: 'Clarity', key: 'clarity' },
		{ label: 'Specificity', key: 'specificity' },
		{ label: 'Structure', key: 'structure' },
		{ label: 'Faithfulness', key: 'faithfulness' },
	];

	for (const dim of dimensions) {
		const score = normalizeScore(scores[dim.key]) ?? 0;
		const rating = getScoreTierLabel(scores[dim.key]);
		const weight = `${Math.round(SCORE_WEIGHTS[dim.key] * 100)}%`;
		rows.push(`| ${dim.label} | ${score}/100 | ${weight} | ${rating} |`);
	}

	// Overall row (bold, no individual weight — it's the weighted sum)
	const overall = normalizeScore(scores.overall) ?? 0;
	const overallRating = getScoreTierLabel(scores.overall);
	rows.push(`| **Overall** | **${overall}/100** | | **${overallRating}** |`);

	return rows;
}

/**
 * Format an ISO date string as "YYYY-MM-DD HH:MM UTC".
 * Timestamps without timezone suffix are treated as UTC (matching backend convention).
 * Returns null if the input is empty or unparseable.
 */
export function formatCreatedAt(iso: string): string | null {
	if (!iso) return null;
	// Ensure UTC interpretation — timestamps without timezone suffix are UTC from the server
	const normalized = iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z';
	const d = new Date(normalized);
	if (isNaN(d.getTime())) return null;
	const date = d.toISOString().slice(0, 10);
	const hours = String(d.getUTCHours()).padStart(2, '0');
	const minutes = String(d.getUTCMinutes()).padStart(2, '0');
	return `${date} ${hours}:${minutes} UTC`;
}

/**
 * Build markdown table rows for the metadata section.
 * Only includes rows where data is present. ID is always included.
 */
export function buildMetadataTable(result: OptimizationResultState): string[] {
	const rows: string[] = [
		'| Field | Value |',
		'|-------|-------|',
	];

	const created = formatCreatedAt(result.created_at);
	if (created) {
		rows.push(`| Created | ${created} |`);
	}

	if (result.model_used) {
		rows.push(`| Model | ${result.model_used} |`);
	}

	if (result.duration_ms > 0) {
		const seconds = (result.duration_ms / 1000).toFixed(1);
		rows.push(`| Duration | ${seconds}s |`);
	}

	if (result.input_tokens > 0 || result.output_tokens > 0) {
		const inTok = result.input_tokens.toLocaleString('en-US');
		const outTok = result.output_tokens.toLocaleString('en-US');
		rows.push(`| Tokens | ${inTok} in / ${outTok} out |`);
	}

	if (result.version) {
		rows.push(`| Version | ${result.version} |`);
	}

	if (result.project) {
		const projectLabel = result.project_status === 'archived'
			? `${result.project} (archived)`
			: result.project;
		rows.push(`| Project | ${projectLabel} |`);
	}

	if (result.tags.length > 0) {
		rows.push(`| Tags | ${result.tags.join(', ')} |`);
	}

	rows.push(`| ID | ${result.id} |`);

	return rows;
}

/**
 * Build the export footer line with current UTC date/time.
 */
export function buildFooter(): string {
	const now = new Date();
	const date = now.toISOString().slice(0, 10);
	const hours = String(now.getUTCHours()).padStart(2, '0');
	const minutes = String(now.getUTCMinutes()).padStart(2, '0');
	return `*Exported from PromptForge on ${date} at ${hours}:${minutes} UTC*`;
}

/**
 * Build a full markdown document from an optimization result.
 */
export function generateExportMarkdown(result: OptimizationResultState): string {
	const heading = result.title || 'Optimized Prompt';
	const lines: string[] = [];

	// Title
	lines.push(`# ${heading}`, '');

	// Optimized Prompt
	lines.push('## Optimized Prompt', '', codeFence(result.optimized), '');

	// Original Prompt
	lines.push('## Original Prompt', '', codeFence(result.original), '');

	// Changes Made (before scores, omitted if empty)
	if (result.changes_made.length > 0) {
		lines.push('## Changes Made', '', ...result.changes_made.map(c => `- ${c}`), '');
	}

	// Scores (dedicated table section)
	lines.push('## Scores', '', ...buildScoreTable(result.scores), '');
	if (result.verdict) {
		lines.push(`**Verdict:** ${result.verdict}`, '');
	}
	// Score explanation (weighted formula narrative)
	const explanation = generateScoreExplanation(result.scores);
	lines.push(explanation, '');

	// Strategy (omitted if no meaningful data)
	if (result.strategy || result.strategy_reasoning || result.strategy_confidence > 0) {
		lines.push('## Strategy', '');
		if (result.strategy) {
			lines.push(`- **Strategy:** ${result.strategy}`);
		}
		if (result.strategy_confidence > 0) {
			const pct = Math.round(result.strategy_confidence * 100);
			lines.push(`- **Confidence:** ${pct}%`);
		}
		if (result.secondary_frameworks && result.secondary_frameworks.length > 0) {
			lines.push(`- **Secondary Frameworks:** ${result.secondary_frameworks.join(', ')}`);
		}
		if (result.strategy_reasoning) {
			lines.push(`- **Reasoning:** ${result.strategy_reasoning}`);
		}
		lines.push('');
	}

	// Analysis
	lines.push('## Analysis', '');
	lines.push(`- **Task Type:** ${result.task_type}`);
	lines.push(`- **Complexity:** ${result.complexity}`);
	lines.push(`- **Framework Applied:** ${result.framework_applied}`);
	lines.push(`- **Improvement:** ${result.is_improvement ? 'Yes' : 'No'}`);
	lines.push('');

	if (result.strengths.length > 0) {
		lines.push('### Strengths', '', ...result.strengths.map(s => `- ${s}`), '');
	}
	if (result.weaknesses.length > 0) {
		lines.push('### Weaknesses', '', ...result.weaknesses.map(w => `- ${w}`), '');
	}

	// Notes (omitted if empty)
	if (result.optimization_notes) {
		lines.push('## Notes', '', result.optimization_notes, '');
	}

	// Metadata
	lines.push('---', '', '## Metadata', '', ...buildMetadataTable(result), '');

	// Footer
	lines.push('---', '', buildFooter(), '');

	return lines.join('\n');
}

/**
 * Trigger a browser download for an arbitrary Blob.
 */
export function downloadBlob(blob: Blob, filename: string): void {
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = filename;
	a.click();
	URL.revokeObjectURL(url);
}

/**
 * Trigger a markdown file download in the browser.
 */
export function downloadMarkdown(content: string, title: string): void {
	const blob = new Blob([content], { type: 'text/markdown' });
	downloadBlob(blob, `${slugifyTitle(title)}.md`);
}
