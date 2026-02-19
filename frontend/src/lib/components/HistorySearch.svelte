<script lang="ts">
	import { historyState } from '$lib/stores/history.svelte';
	import { projectsState } from '$lib/stores/projects.svelte';
	import Icon from './Icon.svelte';
	import Dropdown from './Dropdown.svelte';
	import { Switch, Tooltip } from './ui';

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
		...projectsState.allItems.map((p) => ({ value: p.id, label: p.name })),
	]);

	// Ensure all projects (active + archived) are loaded for the filter dropdown
	$effect(() => {
		if (!projectsState.allItemsLoaded) {
			projectsState.loadAllProjects();
		}
	});

	let isFilteredByArchivedProject = $derived(
		historyState.filterProjectId
			? projectsState.allItems.some(
				(p) => p.id === historyState.filterProjectId && p.status === 'archived'
			)
			: false
	);

	let hasFilters = $derived(
		historyState.availableTaskTypes.length > 0 || projectsState.allItems.length > 0
	);

</script>

<div class="space-y-2 p-3">
	<!-- Search + Delete All -->
	<div class="flex items-center gap-1.5">
		<div class="relative flex-1">
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
		<Tooltip text="Delete all history">
			<button
				class="btn-icon-danger"
				onclick={() => { showClearConfirm = true; }}
				aria-label="Delete all history"
				data-testid="clear-history-btn"
			>
				<Icon name="trash-2" size={14} />
			</button>
		</Tooltip>
	</div>

	<!-- Sort -->
	<div class="flex items-center gap-1.5">
		<Dropdown
			value={historyState.sortBy}
			options={sortOptions}
			label="Sort history by"
			onchange={(v) => historyState.setSortBy(v)}
			testid="history-sort"
		/>
	</div>

	<!-- Type + Project filters -->
	{#if hasFilters}
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
			{#if projectsState.allItems.length > 0}
				<Dropdown
					value={historyState.filterProjectId}
					options={projectOptions}
					label="Filter by project"
					onchange={(v) => historyState.setFilterProjectId(v)}
					testid="filter-project"
				/>
			{/if}
		</div>
	{/if}

	<!-- Archived project indicator -->
	{#if isFilteredByArchivedProject}
		<div class="rounded-lg border-l-2 border-l-neon-yellow/30 bg-neon-yellow/5 border border-neon-yellow/10 px-3 py-1.5 text-[11px] text-neon-yellow/70">
			Showing results for archived project
		</div>
	{/if}

	<!-- Hide archived toggle -->
	<div class="flex items-center justify-between px-0.5">
		<Tooltip text="Hide results from archived projects"><span class="text-[11px] text-text-dim select-none">Hide archived</span></Tooltip>
		<Switch
			checked={historyState.hideArchived}
			onCheckedChange={(v) => historyState.setHideArchived(v)}
			label="Hide archived projects"
		/>
	</div>
</div>
