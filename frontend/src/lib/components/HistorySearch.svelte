<script lang="ts">
	import { historyState } from '$lib/stores/history.svelte';
	import Icon from './Icon.svelte';
	import Dropdown from './Dropdown.svelte';

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

	$effect(() => {
		return () => {
			if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
		};
	});

	const sortOptions = [
		{ value: 'created_at', label: 'Date' },
		{ value: 'overall_score', label: 'Score' },
		{ value: 'task_type', label: 'Task Type' }
	];

	let taskTypeOptions = $derived([
		{ value: '', label: 'All types' },
		...historyState.availableTaskTypes.map((t) => ({ value: t, label: t }))
	]);

	let projectOptions = $derived([
		{ value: '', label: 'All projects' },
		...historyState.availableProjects.map((p) => ({ value: p, label: p }))
	]);
</script>

<div class="space-y-2 p-3">
	<div class="relative">
		<Icon name="search" size={13} class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-dim" />
		<input
			type="text"
			bind:value={searchQuery}
			oninput={handleSearch}
			placeholder="Search..."
			aria-label="Search optimization history"
			data-testid="history-search"
			class="input-field py-2 pl-9 pr-3 text-sm"
		/>
	</div>
	<div class="flex items-center gap-1.5">
		<Dropdown
			value={historyState.sortBy}
			options={sortOptions}
			label="Sort history by"
			onchange={(v) => historyState.setSortBy(v)}
			testid="history-sort"
		/>
		<button
			class="rounded-lg border border-neon-red/15 px-2.5 py-1.5 text-xs text-neon-red/70 transition-colors hover:bg-neon-red/8 hover:text-neon-red"
			onclick={() => { showClearConfirm = true; }}
			aria-label="Clear all history"
			data-testid="clear-history-btn"
		>
			Clear
		</button>
	</div>
	{#if historyState.availableTaskTypes.length > 0 || historyState.availableProjects.length > 0}
		<div class="flex items-center gap-1.5">
			{#if historyState.availableTaskTypes.length > 0}
				<Dropdown
					value={historyState.filterTaskType}
					options={taskTypeOptions}
					label="Filter by task type"
					onchange={(v) => historyState.setFilterTaskType(v)}
					testid="filter-task-type"
				/>
			{/if}
			{#if historyState.availableProjects.length > 0}
				<Dropdown
					value={historyState.filterProject}
					options={projectOptions}
					label="Filter by project"
					onchange={(v) => historyState.setFilterProject(v)}
					testid="filter-project"
				/>
			{/if}
		</div>
	{/if}
</div>
