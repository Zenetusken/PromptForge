<script lang="ts">
	import { historyState } from '$lib/stores/history.svelte';

	let {
		searchQuery = $bindable(''),
		showClearConfirm = $bindable(false)
	}: {
		searchQuery: string;
		showClearConfirm: boolean;
	} = $props();

	let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null;

	function handleSearch() {
		if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
		searchDebounceTimer = setTimeout(() => {
			historyState.setSearch(searchQuery);
		}, 300);
	}

	function handleSortChange(e: Event) {
		const select = e.target as HTMLSelectElement;
		historyState.setSortBy(select.value);
	}

	function handleTaskTypeFilter(e: Event) {
		const select = e.target as HTMLSelectElement;
		historyState.setFilterTaskType(select.value);
	}

	function handleProjectFilter(e: Event) {
		const select = e.target as HTMLSelectElement;
		historyState.setFilterProject(select.value);
	}
</script>

<div class="p-3 space-y-2">
	<input
		type="text"
		bind:value={searchQuery}
		oninput={handleSearch}
		placeholder="Search history..."
		aria-label="Search optimization history"
		data-testid="history-search"
		class="search-input w-full rounded-lg border border-text-dim/20 bg-bg-input px-3 py-2 text-sm text-text-primary outline-none placeholder:text-text-dim focus:border-neon-cyan/60"
	/>
	<div class="flex items-center gap-2">
		<select
			value={historyState.sortBy}
			onchange={handleSortChange}
			aria-label="Sort history by"
			class="flex-1 rounded-lg border border-text-dim/20 bg-bg-input px-2 py-1.5 font-mono text-xs text-text-secondary outline-none focus:border-neon-cyan/40"
			data-testid="history-sort"
		>
			<option value="created_at">Date</option>
			<option value="overall_score">Score</option>
			<option value="task_type">Task Type</option>
		</select>
		<button
			class="rounded-lg border border-neon-red/20 px-2 py-1.5 font-mono text-xs text-neon-red transition-colors hover:bg-neon-red/10"
			onclick={() => { showClearConfirm = true; }}
			aria-label="Clear all history"
			data-testid="clear-history-btn"
		>
			Clear
		</button>
	</div>
	{#if historyState.availableTaskTypes.length > 0 || historyState.availableProjects.length > 0}
		<div class="flex items-center gap-2">
			{#if historyState.availableTaskTypes.length > 0}
				<select
					value={historyState.filterTaskType}
					onchange={handleTaskTypeFilter}
					aria-label="Filter by task type"
					class="flex-1 rounded-lg border border-text-dim/20 bg-bg-input px-2 py-1.5 font-mono text-xs text-text-secondary outline-none focus:border-neon-cyan/40"
					data-testid="filter-task-type"
				>
					<option value="">All types</option>
					{#each historyState.availableTaskTypes as taskType}
						<option value={taskType}>{taskType}</option>
					{/each}
				</select>
			{/if}
			{#if historyState.availableProjects.length > 0}
				<select
					value={historyState.filterProject}
					onchange={handleProjectFilter}
					aria-label="Filter by project"
					class="flex-1 rounded-lg border border-text-dim/20 bg-bg-input px-2 py-1.5 font-mono text-xs text-text-secondary outline-none focus:border-neon-cyan/40"
					data-testid="filter-project"
				>
					<option value="">All projects</option>
					{#each historyState.availableProjects as project}
						<option value={project}>{project}</option>
					{/each}
				</select>
			{/if}
		</div>
	{/if}
</div>

<style>
	.search-input:focus {
		box-shadow: 0 0 8px rgba(0, 240, 255, 0.3), 0 0 16px rgba(0, 240, 255, 0.1);
		border-color: rgba(0, 240, 255, 0.6);
	}
</style>
