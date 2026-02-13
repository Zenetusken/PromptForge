<script lang="ts">
	let { scores }: { scores: Record<string, number> } = $props();

	function getScoreColor(score: number): string {
		if (score >= 80) return 'neon-green';
		if (score >= 50) return 'neon-yellow';
		return 'neon-red';
	}

	let scoreEntries = $derived(Object.entries(scores));
</script>

<div>
	<h4 class="mb-3 font-mono text-xs font-semibold uppercase tracking-wider text-text-secondary">
		Quality Scores
	</h4>

	<div class="grid gap-3 sm:grid-cols-2">
		{#each scoreEntries as [label, score] (label)}
			{@const color = getScoreColor(score)}
			<div class="rounded-lg bg-bg-input p-3">
				<div class="mb-2 flex items-center justify-between">
					<span class="text-sm capitalize text-text-primary">
						{label.replace(/_/g, ' ')}
					</span>
					<span
						class="font-mono text-sm font-bold"
						class:text-neon-green={color === 'neon-green'}
						class:text-neon-yellow={color === 'neon-yellow'}
						class:text-neon-red={color === 'neon-red'}
					>
						{score}
					</span>
				</div>
				<div class="h-1.5 w-full overflow-hidden rounded-full bg-bg-primary">
					<div
						class="h-full rounded-full transition-all duration-700"
						class:bg-neon-green={color === 'neon-green'}
						class:bg-neon-yellow={color === 'neon-yellow'}
						class:bg-neon-red={color === 'neon-red'}
						style="width: {score}%;"
					></div>
				</div>
			</div>
		{/each}
	</div>
</div>
