<script lang="ts">
	import { goto } from '$app/navigation';
	import { optimizationState, type OptimizationResultState } from '$lib/stores/optimization.svelte';
	import { toastState } from '$lib/stores/toast.svelte';
	import { promptState } from '$lib/stores/prompt.svelte';
	import { useCopyFeedback } from '$lib/utils/useCopyFeedback.svelte';
	import { normalizeScore } from '$lib/utils/format';
	import Icon from './Icon.svelte';

	let { result }: { result: OptimizationResultState } = $props();

	const copyFeedback = useCopyFeedback();

	function copyOptimized() {
		copyFeedback.copy(result.optimized);
		toastState.show('Copied to clipboard!', 'success', 3000);
	}

	function handleReforge() {
		if (result.id) {
			optimizationState.retryOptimization(result.id, result.original);
		} else {
			optimizationState.startOptimization(result.original);
		}
		if (window.location.pathname !== '/') {
			goto('/');
		}
	}

	function handleEditReforge() {
		promptState.set(result.optimized);
		if (window.location.pathname !== '/') {
			goto('/');
		} else {
			window.scrollTo({ top: 0, behavior: 'smooth' });
		}
	}

	function handleExportMd() {
		const heading = result.title || 'Optimized Prompt';
		const lines: string[] = [
			`# ${heading}`,
			'',
			result.optimized,
			'',
			'## Original Prompt',
			'',
			result.original,
			'',
			'## Analysis',
			'',
			`- **Task Type:** ${result.task_type}`,
			`- **Complexity:** ${result.complexity}`,
			`- **Framework:** ${result.framework_applied}`,
		];
		if (result.strategy_reasoning) lines.push(`- **Strategy:** ${result.strategy_reasoning}`);
		if (result.model_used) lines.push(`- **Model:** ${result.model_used}`);
		if (result.project) lines.push(`- **Project:** ${result.project}`);
		if (result.tags.length > 0) lines.push(`- **Tags:** ${result.tags.join(', ')}`);
		lines.push(
			`- **Overall Score:** ${normalizeScore(result.scores.overall) ?? 0}/100`,
			`- **Clarity:** ${normalizeScore(result.scores.clarity) ?? 0}/100`,
			`- **Specificity:** ${normalizeScore(result.scores.specificity) ?? 0}/100`,
			`- **Structure:** ${normalizeScore(result.scores.structure) ?? 0}/100`,
			`- **Faithfulness:** ${normalizeScore(result.scores.faithfulness) ?? 0}/100`,
		);
		if (result.verdict) {
			lines.push('', '## Verdict', '', result.verdict);
		}
		if (result.strengths.length > 0) {
			lines.push('', '## Strengths', '', ...result.strengths.map(s => '- ' + s));
		}
		if (result.weaknesses.length > 0) {
			lines.push('', '## Weaknesses', '', ...result.weaknesses.map(w => '- ' + w));
		}
		if (result.changes_made.length > 0) {
			lines.push('', '## Changes Made', '', ...result.changes_made.map(c => '- ' + c));
		}
		if (result.optimization_notes) {
			lines.push('', '## Notes', '', result.optimization_notes);
		}
		lines.push('');

		const content = lines.join('\n');
		const blob = new Blob([content], { type: 'text/markdown' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		const slug = heading.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
		a.download = `${slug}.md`;
		a.click();
		URL.revokeObjectURL(url);
	}
</script>

<div class="flex flex-wrap items-center gap-2 border-t border-border-subtle px-5 py-4" data-testid="result-actions">
	<button
		class="btn-ghost flex items-center gap-1.5 transition-[background-color,color] duration-200 {copyFeedback.copied ? 'copy-flash bg-neon-green/15 text-neon-green' : 'bg-neon-cyan/8 text-neon-cyan hover:bg-neon-cyan/15'}"
		onclick={copyOptimized}
		data-testid="copy-optimized-btn"
	>
		{#if copyFeedback.copied}
			<Icon name="check" size={12} />
			Copied!
		{:else}
			<Icon name="copy" size={12} />
			Copy Optimized
		{/if}
	</button>
	<button
		class="btn-ghost flex items-center gap-1.5 bg-neon-purple/8 text-neon-purple hover:bg-neon-purple/15"
		onclick={handleExportMd}
		data-testid="export-md-btn"
	>
		<Icon name="download" size={12} />
		Export .md
	</button>
	<button
		class="btn-ghost flex items-center gap-1.5 bg-neon-cyan/8 text-neon-cyan hover:bg-neon-cyan/15"
		onclick={handleReforge}
		data-testid="reforge-result-btn"
	>
		<Icon name="refresh" size={12} />
		Re-forge
	</button>
	<button
		class="btn-ghost flex items-center gap-1.5 bg-neon-green/8 text-neon-green hover:bg-neon-green/15"
		onclick={handleEditReforge}
		data-testid="edit-reforge-result-btn"
	>
		<Icon name="edit" size={12} />
		Edit & Re-forge
	</button>
</div>
