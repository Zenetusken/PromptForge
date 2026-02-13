<script lang="ts">
	import DiffView from './DiffView.svelte';
	import ScorePanel from './ScorePanel.svelte';
	import CopyButton from './CopyButton.svelte';

	let {
		original,
		optimized,
		scores = {},
		explanation = ''
	}: {
		original: string;
		optimized: string;
		scores?: Record<string, number>;
		explanation?: string;
	} = $props();

	let activeTab = $state<'optimized' | 'diff' | 'original'>('optimized');
</script>

<div class="rounded-xl border border-text-dim/20 bg-bg-card">
	<!-- Tabs -->
	<div class="flex items-center justify-between border-b border-text-dim/20 px-5">
		<div class="flex gap-1">
			<button
				class="border-b-2 px-4 py-3 font-mono text-sm transition-colors"
				class:border-neon-cyan={activeTab === 'optimized'}
				class:text-neon-cyan={activeTab === 'optimized'}
				class:border-transparent={activeTab !== 'optimized'}
				class:text-text-secondary={activeTab !== 'optimized'}
				onclick={() => (activeTab = 'optimized')}
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
			>
				Original
			</button>
		</div>

		<CopyButton text={activeTab === 'original' ? original : optimized} />
	</div>

	<!-- Content -->
	<div class="p-5">
		{#if activeTab === 'optimized'}
			<pre class="whitespace-pre-wrap font-mono text-sm leading-relaxed text-text-primary">{optimized}</pre>
		{:else if activeTab === 'diff'}
			<DiffView {original} {optimized} />
		{:else}
			<pre class="whitespace-pre-wrap font-mono text-sm leading-relaxed text-text-secondary">{original}</pre>
		{/if}
	</div>

	<!-- Scores & Explanation -->
	{#if Object.keys(scores).length > 0 || explanation}
		<div class="border-t border-text-dim/20 p-5">
			{#if Object.keys(scores).length > 0}
				<ScorePanel {scores} />
			{/if}

			{#if explanation}
				<div class="mt-4">
					<h4 class="mb-2 font-mono text-xs font-semibold uppercase tracking-wider text-text-secondary">
						Explanation
					</h4>
					<p class="text-sm leading-relaxed text-text-secondary">{explanation}</p>
				</div>
			{/if}
		</div>
	{/if}
</div>
