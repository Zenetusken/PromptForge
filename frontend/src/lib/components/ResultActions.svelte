<script lang="ts">
	import { goto } from '$app/navigation';
	import { optimizationState, type OptimizationResultState } from '$lib/stores/optimization.svelte';
	import { toastState } from '$lib/stores/toast.svelte';
	import { promptState } from '$lib/stores/prompt.svelte';
	import { copyToClipboard } from '$lib/utils/clipboard';
	import { normalizeScore } from '$lib/utils/format';

	let { result }: { result: OptimizationResultState } = $props();

	let copyFeedback = $state(false);

	function copyOptimized() {
		copyFeedback = true;
		setTimeout(() => { copyFeedback = false; }, 2000);
		copyToClipboard(result.optimized);
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

<div class="flex flex-wrap items-center gap-2 border-t border-text-dim/20 px-5 py-3" data-testid="result-actions">
	<button
		class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-mono text-xs transition-all {copyFeedback ? 'copy-flash bg-neon-green/20 text-neon-green' : 'bg-neon-cyan/10 text-neon-cyan hover:bg-neon-cyan/20'}"
		onclick={copyOptimized}
		data-testid="copy-optimized-btn"
	>
		{#if copyFeedback}
			<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
			Copied!
		{:else}
			<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>
				<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>
			</svg>
			Copy Optimized
		{/if}
	</button>
	<button
		class="flex items-center gap-1.5 rounded-lg bg-neon-purple/10 px-3 py-1.5 font-mono text-xs text-neon-purple transition-colors hover:bg-neon-purple/20"
		onclick={handleExportMd}
		data-testid="export-md-btn"
	>
		<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
			<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
		</svg>
		Export .md
	</button>
	<button
		class="flex items-center gap-1.5 rounded-lg bg-neon-cyan/10 px-3 py-1.5 font-mono text-xs text-neon-cyan transition-colors hover:bg-neon-cyan/20"
		onclick={handleReforge}
		data-testid="reforge-result-btn"
	>
		<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
			<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>
		</svg>
		Re-forge
	</button>
	<button
		class="flex items-center gap-1.5 rounded-lg bg-neon-green/10 px-3 py-1.5 font-mono text-xs text-neon-green transition-colors hover:bg-neon-green/20"
		onclick={handleEditReforge}
		data-testid="edit-reforge-result-btn"
	>
		<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
			<path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
		</svg>
		Edit & Re-forge
	</button>
</div>
