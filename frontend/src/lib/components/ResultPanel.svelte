<script lang="ts">
	import DiffView from './DiffView.svelte';
	import ScorePanel from './ScorePanel.svelte';
	import CopyButton from './CopyButton.svelte';
	import { optimizationState, toastState, type OptimizationResultState } from '$lib/stores/optimization.svelte';
	import { promptState } from '$lib/stores/prompt.svelte';

	let { result }: { result: OptimizationResultState } = $props();

	let activeTab = $state<'optimized' | 'diff' | 'original'>('optimized');
	let copyFeedback = $state(false);

	let hasScores = $derived(
		result.scores.clarity > 0 ||
		result.scores.specificity > 0 ||
		result.scores.structure > 0 ||
		result.scores.faithfulness > 0 ||
		result.scores.overall > 0
	);

	function copyOptimized() {
		// Show feedback immediately
		copyFeedback = true;
		setTimeout(() => { copyFeedback = false; }, 2000);

		// Copy to clipboard in next microtask to avoid blocking Puppeteer/automation
		setTimeout(() => {
			try {
				const textarea = document.createElement('textarea');
				textarea.value = result.optimized;
				textarea.style.position = 'fixed';
				textarea.style.opacity = '0';
				textarea.style.pointerEvents = 'none';
				document.body.appendChild(textarea);
				textarea.select();
				document.execCommand('copy');
				document.body.removeChild(textarea);
			} catch { /* clipboard copy is best-effort */ }
		}, 0);

		// Show toast notification
		toastState.show('Copied to clipboard!', 'success', 3000);
	}

	function handleReforge() {
		if (result.id) {
			optimizationState.retryOptimization(result.id, result.original);
		} else {
			optimizationState.startOptimization(result.original);
		}
	}

	function handleEditReforge() {
		promptState.set(result.optimized);
		window.scrollTo({ top: 0, behavior: 'smooth' });
	}

	function handleExportMd() {
		const content = `# Optimized Prompt\n\n${result.optimized}\n\n## Original Prompt\n\n${result.original}\n\n## Analysis\n\n- **Task Type:** ${result.task_type}\n- **Complexity:** ${result.complexity}\n- **Framework:** ${result.framework_applied}\n- **Overall Score:** ${result.scores.overall}\n\n## Verdict\n\n${result.verdict}\n\n## Changes Made\n\n${result.changes_made.map(c => '- ' + c).join('\n')}\n`;
		const blob = new Blob([content], { type: 'text/markdown' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = 'optimized-prompt.md';
		a.click();
		URL.revokeObjectURL(url);
	}
</script>

<div class="animate-fade-in rounded-xl border border-neon-cyan/20 bg-bg-card" data-testid="result-panel">
	<!-- Header with metadata -->
	<div class="flex flex-wrap items-center gap-2 border-b border-text-dim/20 px-5 py-3" data-testid="result-metadata">
		{#if result.task_type}
			<span class="rounded-full bg-neon-cyan/10 px-2.5 py-0.5 font-mono text-xs text-neon-cyan" data-testid="task-type-badge">
				{result.task_type}
			</span>
		{/if}
		{#if result.complexity}
			<span class="rounded-full bg-neon-purple/10 px-2.5 py-0.5 font-mono text-xs text-neon-purple" data-testid="complexity-badge">
				{result.complexity}
			</span>
		{/if}
		{#if result.framework_applied}
			<span class="rounded-full bg-text-dim/10 px-2.5 py-0.5 font-mono text-xs text-text-secondary" data-testid="framework-badge">
				{result.framework_applied}
			</span>
		{/if}
		{#if result.is_improvement}
			<span class="rounded-full bg-neon-green/10 px-2.5 py-0.5 font-mono text-xs text-neon-green" data-testid="improvement-badge">
				Improved
			</span>
		{:else}
			<span class="rounded-full bg-neon-yellow/10 px-2.5 py-0.5 font-mono text-xs text-neon-yellow">
				No improvement
			</span>
		{/if}
		{#if result.duration_ms > 0}
			<span class="ml-auto font-mono text-xs text-text-dim" data-testid="duration">
				{(result.duration_ms / 1000).toFixed(1)}s
			</span>
		{/if}
	</div>

	<!-- Tabs -->
	<div class="flex items-center justify-between border-b border-text-dim/20 px-5">
		<div class="flex gap-1" data-testid="result-tabs">
			<button
				class="border-b-2 px-4 py-3 font-mono text-sm transition-colors"
				class:border-neon-cyan={activeTab === 'optimized'}
				class:text-neon-cyan={activeTab === 'optimized'}
				class:border-transparent={activeTab !== 'optimized'}
				class:text-text-secondary={activeTab !== 'optimized'}
				onclick={() => (activeTab = 'optimized')}
				data-testid="tab-optimized"
			>
				Optimized
			</button>
			<button
				class="border-b-2 px-4 py-3 font-mono text-sm transition-colors"
				class:border-neon-purple={activeTab === 'diff'}
				class:text-neon-purple={activeTab === 'diff'}
				class:border-transparent={activeTab !== 'diff'}
				class:text-text-secondary={activeTab !== 'diff'}
				onclick={() => (activeTab = 'diff')}
				data-testid="tab-diff"
			>
				Diff View
			</button>
			<button
				class="border-b-2 px-4 py-3 font-mono text-sm transition-colors"
				class:border-text-secondary={activeTab === 'original'}
				class:text-text-primary={activeTab === 'original'}
				class:border-transparent={activeTab !== 'original'}
				class:text-text-secondary={activeTab !== 'original'}
				onclick={() => (activeTab = 'original')}
				data-testid="tab-original"
			>
				Original
			</button>
		</div>

		<div class="flex items-center gap-2">
			<CopyButton text={activeTab === 'original' ? result.original : result.optimized} />
		</div>
	</div>

	<!-- Content -->
	<div class="p-5" data-testid="result-content">
		{#if activeTab === 'optimized'}
			<pre class="whitespace-pre-wrap font-mono text-sm leading-relaxed text-text-primary">{result.optimized}</pre>
		{:else if activeTab === 'diff'}
			<DiffView original={result.original} optimized={result.optimized} />
		{:else}
			<pre class="whitespace-pre-wrap font-mono text-sm leading-relaxed text-text-secondary">{result.original}</pre>
		{/if}
	</div>

	<!-- Action buttons -->
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

	<!-- Verdict -->
	{#if result.verdict}
		<div class="border-t border-text-dim/20 px-5 py-4" data-testid="verdict">
			<h4 class="mb-2 font-mono text-xs font-semibold uppercase tracking-wider text-text-secondary">
				Verdict
			</h4>
			<p class="text-sm leading-relaxed text-text-primary">{result.verdict}</p>
		</div>
	{/if}

	<!-- Changes Made -->
	{#if result.changes_made.length > 0}
		<div class="border-t border-text-dim/20 px-5 py-4" data-testid="changes-made">
			<h4 class="mb-2 font-mono text-xs font-semibold uppercase tracking-wider text-text-secondary">
				Changes Made
			</h4>
			<ul class="space-y-1">
				{#each result.changes_made as change}
					<li class="flex items-start gap-2 text-sm text-text-secondary">
						<span class="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-neon-cyan"></span>
						{change}
					</li>
				{/each}
			</ul>
		</div>
	{/if}

	<!-- Optimization Notes -->
	{#if result.optimization_notes}
		<div class="border-t border-text-dim/20 px-5 py-4" data-testid="optimization-notes">
			<h4 class="mb-2 font-mono text-xs font-semibold uppercase tracking-wider text-text-secondary">
				Notes
			</h4>
			<p class="text-sm leading-relaxed text-text-secondary">{result.optimization_notes}</p>
		</div>
	{/if}

	<!-- Scores -->
	{#if hasScores}
		<div class="border-t border-text-dim/20 p-5">
			<ScorePanel scores={result.scores} />
		</div>
	{/if}
</div>
