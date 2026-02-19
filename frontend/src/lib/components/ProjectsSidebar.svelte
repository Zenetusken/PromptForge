<script lang="ts">
	import { projectsState } from '$lib/stores/projects.svelte';
	import ProjectItem from './ProjectItem.svelte';
	import CreateProjectDialog from './CreateProjectDialog.svelte';
	import Icon from './Icon.svelte';
	import { SidebarTabs, Tooltip } from './ui';

	let searchQuery = $state('');
	let showCreateForm = $state(false);
	let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null;

	const isArchived = $derived(projectsState.statusFilter === 'archived');

	function handleSearch() {
		if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
		searchDebounceTimer = setTimeout(() => {
			projectsState.setSearch(searchQuery);
		}, 300);
	}

	function setFilter(status: 'active' | 'archived') {
		projectsState.setStatusFilter(status);
	}

	// Close create form when switching away from active
	$effect(() => {
		if (isArchived) showCreateForm = false;
	});

	$effect(() => {
		return () => {
			if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
		};
	});
</script>

<div class="space-y-2 p-3">
	<!-- Search + New Project -->
	<div class="flex items-center gap-1.5">
		<div class="relative flex-1">
			<Icon name="search" size={13} class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-dim" />
			<input
				type="text"
				bind:value={searchQuery}
				oninput={handleSearch}
				placeholder="Search projects..."
				aria-label="Search projects"
				data-testid="projects-search"
				class="input-field w-full py-2 pl-9 pr-3 text-sm"
			/>
		</div>
		{#if !isArchived}
			<Tooltip text="Create new project" side="bottom" class="shrink-0">
				<button
					onclick={() => { showCreateForm = !showCreateForm; }}
					class="flex h-[34px] w-[34px] items-center justify-center rounded-lg border border-neon-cyan/15 text-neon-cyan/60
						transition-all hover:bg-neon-cyan/8 hover:text-neon-cyan hover:border-neon-cyan/25
						hover:shadow-[0_0_8px_rgba(0,229,255,0.06)]
						active:bg-neon-cyan/15
						focus-visible:outline-offset-0"
					aria-label="New project"
					data-testid="new-project-btn"
				>
					<Icon name="plus" size={14} />
				</button>
			</Tooltip>
		{/if}
	</div>

	<!-- Active / Archived toggle -->
	<SidebarTabs
		value={projectsState.statusFilter}
		onValueChange={(v) => setFilter(v as 'active' | 'archived')}
		label="Project status filter"
		tabs={[
			{ value: 'active', label: 'Active', testid: 'filter-active' },
			{ value: 'archived', label: 'Archived', testid: 'filter-archived', activeClass: 'text-neon-yellow bg-neon-yellow/8' },
		]}
	/>
</div>

{#if showCreateForm}
	<CreateProjectDialog onclose={() => { showCreateForm = false; }} />
{/if}

<div class="flex-1 overflow-y-auto px-2 pb-2" data-testid="projects-list">
	{#if projectsState.isLoading && !projectsState.hasLoaded}
		<div class="space-y-1.5 p-2" data-testid="projects-skeleton">
			{#each [1, 2, 3] as _}
				<div class="min-h-[72px] rounded-xl p-3">
					<div class="mb-1 flex items-center gap-1.5">
						<div class="skeleton h-3.5 w-3.5 shrink-0 rounded"></div>
						<div class="skeleton h-3.5 w-3/5"></div>
						<div class="skeleton ml-auto h-4 w-5 shrink-0 rounded-full"></div>
					</div>
					<div class="skeleton h-3 w-12"></div>
				</div>
			{/each}
		</div>
	{:else if projectsState.items.length === 0}
		<div class="flex flex-col items-center justify-center py-12 text-center" data-testid="projects-empty">
			<div class="mb-3 rounded-xl bg-bg-hover/50 p-3 text-text-dim">
				{#if projectsState.searchQuery}
					<Icon name="search" size={24} />
				{:else if isArchived}
					<Icon name="archive" size={24} />
				{:else}
					<Icon name="folder" size={24} />
				{/if}
			</div>
			<p class="text-sm font-medium text-text-secondary">
				{#if projectsState.searchQuery}
					No matches
				{:else if isArchived}
					No archived projects
				{:else}
					No projects yet
				{/if}
			</p>
			{#if projectsState.searchQuery}
				<p class="mt-1 text-xs text-text-dim">Try a different search term</p>
			{:else if isArchived}
				<p class="mt-1 text-xs leading-relaxed text-text-dim">Archived projects will appear here</p>
			{:else}
				<p class="mt-1 text-xs leading-relaxed text-text-dim">Create one to organize your prompts</p>
			{/if}
		</div>
	{:else}
		{#each projectsState.items as project (project.id)}
			<ProjectItem {project} />
		{/each}

		{#if projectsState.total > projectsState.items.length}
			<div class="py-3 text-center">
				<button
					class="text-xs text-text-dim transition-colors hover:text-neon-cyan hover:underline hover:underline-offset-2 active:text-neon-cyan/70
						focus-visible:outline-offset-0"
					onclick={() => projectsState.loadProjects({ page: projectsState.page + 1 })}
					data-testid="projects-load-more"
				>
					Load more ({projectsState.total - projectsState.items.length} remaining)
				</button>
			</div>
		{/if}
	{/if}
</div>
