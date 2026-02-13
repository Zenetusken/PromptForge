<script lang="ts">
	import { historyState } from '$lib/stores/history';
	import { truncateText, formatRelativeTime } from '$lib/utils/format';

	let { open = $bindable(true) }: { open: boolean } = $props();

	let searchQuery = $state('');

	let filteredEntries = $derived(
		historyState.entries.filter((entry) =>
			entry.prompt.toLowerCase().includes(searchQuery.toLowerCase())
		)
	);

	function getScoreClass(score: number): string {
		if (score >= 80) return 'bg-neon-green/10 text-neon-green';
		if (score >= 50) return 'bg-neon-yellow/10 text-neon-yellow';
		return 'bg-neon-red/10 text-neon-red';
	}

	$effect(() => {
		if (open) {
			historyState.loadHistory();
		}
	});
</script>

<aside
	class="flex h-full shrink-0 flex-col border-r border-text-dim/20 bg-bg-secondary transition-all duration-300"
	class:w-72={open}
	class:w-0={!open}
	class:overflow-hidden={!open}
>
	<div class="flex h-14 items-center justify-between border-b border-text-dim/20 px-4">
		<span class="font-mono text-sm font-semibold text-text-secondary">History</span>
		<span class="rounded-full bg-bg-card px-2 py-0.5 font-mono text-xs text-text-dim">
			{historyState.entries.length}
		</span>
	</div>

	<div class="p-3">
		<input
			type="text"
			bind:value={searchQuery}
			placeholder="Search history..."
			class="w-full rounded-lg border border-text-dim/20 bg-bg-input px-3 py-2 text-sm text-text-primary outline-none placeholder:text-text-dim focus:border-neon-cyan/40"
		/>
	</div>

	<div class="flex-1 overflow-y-auto px-2 pb-2">
		{#if filteredEntries.length === 0}
			<div class="flex flex-col items-center justify-center py-10 text-center">
				<div class="mb-2 text-2xl text-text-dim">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						width="24"
						height="24"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						stroke-linecap="round"
						stroke-linejoin="round"
					>
						<circle cx="12" cy="12" r="10" />
						<polyline points="12 6 12 12 16 14" />
					</svg>
				</div>
				<p class="text-xs text-text-dim">
					{searchQuery ? 'No matching entries' : 'No history yet'}
				</p>
			</div>
		{:else}
			{#each filteredEntries as entry (entry.id)}
				<button
					class="mb-1 w-full rounded-lg p-3 text-left transition-colors hover:bg-bg-card"
					onclick={() => {
						// Could navigate to or load a specific optimization
					}}
				>
					<div class="mb-1 text-sm text-text-primary">
						{truncateText(entry.prompt, 60)}
					</div>
					<div class="flex items-center justify-between">
						<span class="text-xs text-text-dim">
							{formatRelativeTime(entry.createdAt)}
						</span>
						{#if entry.score !== undefined}
							<span class="rounded-full px-1.5 py-0.5 font-mono text-xs {getScoreClass(entry.score)}">
								{entry.score}
							</span>
						{/if}
					</div>
				</button>
			{/each}
		{/if}
	</div>
</aside>
