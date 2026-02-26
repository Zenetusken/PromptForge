<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import Icon from './Icon.svelte';
	import FileManagerView from './FileManagerView.svelte';
	import FileManagerRow from './FileManagerRow.svelte';
	import DesktopContextMenu from './DesktopContextMenu.svelte';
	import ConfirmModal from './ConfirmModal.svelte';
	import type { ColumnDef } from './FileManagerView.svelte';
	import type { ContextAction } from '$lib/stores/desktopStore.svelte';
	import { projectsState } from '$lib/stores/projects.svelte';
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import { forgeSession } from '$lib/stores/forgeSession.svelte';
	import { toastState } from '$lib/stores/toast.svelte';
	import { clipboardService } from '$lib/services/clipboardService.svelte';
	import { fetchProject, type ProjectDetail } from '$lib/api/client';
	import { formatRelativeTime, truncateText } from '$lib/utils/format';
	import { toFilename } from '$lib/utils/fileTypes';

	// ── View state ──
	type ProjectsView = 'list' | 'project';
	let currentView: ProjectsView = $state('list');
	let activeProjectId: string | null = $state(null);
	let activeProjectData: ProjectDetail | null = $state(null);
	let activeProjectLoading: boolean = $state(false);

	// ── Navigation stacks ──
	let backStack: Array<{ view: ProjectsView; projectId: string | null }> = $state([]);
	let forwardStack: Array<{ view: ProjectsView; projectId: string | null }> = $state([]);

	// ── Search ──
	let searchInput = $state('');
	let searchTimer: ReturnType<typeof setTimeout> | null = null;

	// ── Selection ──
	let selectedId: string | null = $state(null);

	// ── Context menu ──
	let ctxMenu = $state({ open: false, x: 0, y: 0, targetId: null as string | null, actions: [] as ContextAction[] });
	let confirmAction: { type: 'delete-project' | 'delete-prompt'; id: string; label: string } | null = $state(null);

	function projectActions(project: { id: string; status: string }): ContextAction[] {
		const actions: ContextAction[] = [
			{ id: 'open', label: 'Open', icon: 'folder-open' },
		];
		if (project.status === 'archived') {
			actions.push({ id: 'unarchive', label: 'Unarchive', icon: 'archive', separator: true });
		} else {
			actions.push({ id: 'archive', label: 'Archive', icon: 'archive', separator: true });
		}
		actions.push({ id: 'delete', label: 'Delete Project', icon: 'trash-2', separator: true, danger: true });
		return actions;
	}

	const promptActions: ContextAction[] = [
		{ id: 'open-review', label: 'Open', icon: 'arrow-up-right' },
		{ id: 'forge', label: 'Forge', icon: 'bolt' },
		{ id: 'copy-content', label: 'Copy Content', icon: 'copy' },
		{ id: 'delete-prompt', label: 'Delete Prompt', icon: 'trash-2', separator: true, danger: true },
	];

	function openCtxMenu(e: MouseEvent, id: string, actions: ContextAction[]) {
		ctxMenu = { open: true, x: e.clientX, y: e.clientY, targetId: id, actions };
	}

	function closeCtxMenu() {
		ctxMenu = { open: false, x: 0, y: 0, targetId: null, actions: [] };
	}

	function handleContextAction(actionId: string) {
		const targetId = ctxMenu.targetId;
		closeCtxMenu();
		if (!targetId) return;

		switch (actionId) {
			case 'open':
				navigateTo('project', targetId);
				break;
			case 'open-review': {
				const prompt = activeProjectData?.prompts.find((p) => p.id === targetId);
				if (prompt) handlePromptOpen(prompt);
				break;
			}
			case 'archive':
				projectsState.archive(targetId);
				break;
			case 'unarchive':
				projectsState.unarchive(targetId);
				break;
			case 'delete': {
				const project = projectsState.items.find((p) => p.id === targetId);
				confirmAction = { type: 'delete-project', id: targetId, label: project?.name ?? 'this project' };
				break;
			}
			case 'forge': {
				const prompt = activeProjectData?.prompts.find((p) => p.id === targetId);
				if (prompt && activeProjectData) {
					forgeSession.loadRequest({ text: prompt.content, project: activeProjectData.name });
				}
				break;
			}
			case 'copy-content': {
				const prompt = activeProjectData?.prompts.find((p) => p.id === targetId);
				if (prompt) {
					clipboardService.copy(prompt.content, 'Prompt content');
					toastState.show('Prompt content copied', 'success');
				}
				break;
			}
			case 'delete-prompt': {
				const prompt = activeProjectData?.prompts.find((p) => p.id === targetId);
				confirmAction = { type: 'delete-prompt', id: targetId, label: truncateText(prompt?.content ?? 'this prompt', 40) };
				break;
			}
		}
	}

	async function handleConfirmAction() {
		if (!confirmAction) return;
		const { type, id } = confirmAction;
		confirmAction = null;
		if (type === 'delete-project') {
			const ok = await projectsState.remove(id);
			if (ok) toastState.show('Project deleted', 'success');
			else toastState.show('Failed to delete project', 'error');
		} else if (type === 'delete-prompt' && activeProjectId) {
			const ok = await projectsState.removePrompt(activeProjectId, id);
			if (ok) {
				toastState.show('Prompt deleted', 'success');
				await loadProjectDetail(activeProjectId);
			} else {
				toastState.show('Failed to delete prompt', 'error');
			}
		}
	}

	// ── Column defs ──
	const listColumns: ColumnDef[] = [
		{ key: 'name', label: 'Name', width: 'flex-1' },
		{ key: 'prompt_count', label: 'Prompts', width: 'w-16', align: 'right', sortable: false },
		{ key: 'updated_at', label: 'Modified', width: 'w-24' },
	];

	const promptColumns: ColumnDef[] = [
		{ key: 'content', label: 'Name', width: 'flex-1', sortable: false },
		{ key: 'version', label: 'Ver', width: 'w-10', align: 'right', sortable: false },
		{ key: 'forge_count', label: 'Forges', width: 'w-14', align: 'right', sortable: false },
		{ key: 'updated_at', label: 'Modified', width: 'w-24', sortable: false },
	];

	// ── Navigation functions ──
	function navigateTo(view: ProjectsView, projectId: string | null) {
		backStack = [...backStack, { view: currentView, projectId: activeProjectId }];
		forwardStack = [];
		currentView = view;
		activeProjectId = projectId;
		selectedId = null;
		if (view === 'project' && projectId) loadProjectDetail(projectId);
		syncBreadcrumbs();
		syncNavigation();
	}

	function goBack() {
		if (!backStack.length) return;
		const prev = backStack[backStack.length - 1];
		backStack = backStack.slice(0, -1);
		forwardStack = [...forwardStack, { view: currentView, projectId: activeProjectId }];
		currentView = prev.view;
		activeProjectId = prev.projectId;
		selectedId = null;
		if (prev.view === 'project' && prev.projectId) loadProjectDetail(prev.projectId);
		syncBreadcrumbs();
		syncNavigation();
	}

	function goForward() {
		if (!forwardStack.length) return;
		const next = forwardStack[forwardStack.length - 1];
		forwardStack = forwardStack.slice(0, -1);
		backStack = [...backStack, { view: currentView, projectId: activeProjectId }];
		currentView = next.view;
		activeProjectId = next.projectId;
		selectedId = null;
		if (next.view === 'project' && next.projectId) loadProjectDetail(next.projectId);
		syncBreadcrumbs();
		syncNavigation();
	}

	// ── Breadcrumb & navigation sync ──
	function syncBreadcrumbs() {
		if (currentView === 'list') {
			windowManager.setBreadcrumbs('projects', [
				{ label: 'Desktop', icon: 'monitor', action: () => windowManager.closeWindow('projects') },
				{ label: 'Projects' },
			]);
		} else {
			const name = activeProjectData?.name ?? 'Loading...';
			windowManager.setBreadcrumbs('projects', [
				{ label: 'Desktop', icon: 'monitor', action: () => windowManager.closeWindow('projects') },
				{ label: 'Projects', action: () => navigateTo('list', null) },
				{ label: name },
			]);
		}
	}

	function syncNavigation() {
		windowManager.setNavigation('projects', {
			canGoBack: backStack.length > 0,
			canGoForward: forwardStack.length > 0,
			goBack,
			goForward,
		});
	}

	// ── Data loading ──
	async function loadProjectDetail(id: string) {
		activeProjectLoading = true;
		try {
			activeProjectData = await fetchProject(id);
			syncBreadcrumbs(); // Update "Loading..." → real name
		} finally {
			activeProjectLoading = false;
		}
	}

	// ── Handlers ──
	function handleSearch(value: string) {
		searchInput = value;
		if (searchTimer) clearTimeout(searchTimer);
		searchTimer = setTimeout(() => {
			projectsState.setSearch(value);
		}, 300);
	}

	function handleFilterToggle() {
		projectsState.setStatusFilter(
			projectsState.statusFilter === 'active' ? 'archived' : 'active'
		);
	}

	function handleListSort(key: string) {
		projectsState.setSortField(key);
	}

	async function handlePromptOpen(prompt: import('$lib/api/client').ProjectPrompt) {
		if (!activeProjectId || !activeProjectData) return;
		const { openPromptInIDE } = await import('$lib/utils/promptOpener');
		await openPromptInIDE({ promptId: prompt.id, projectId: activeProjectId, projectData: activeProjectData, prompt });
	}

	// ── Consume pending navigation from projectsState ──
	$effect(() => {
		const pendingId = projectsState.pendingNavigateProjectId;
		if (pendingId) {
			projectsState.pendingNavigateProjectId = null;
			navigateTo('project', pendingId);
		}
	});

	// ── Lifecycle ──
	onMount(() => {
		if (!projectsState.hasLoaded) projectsState.loadProjects();
		syncNavigation();
		syncBreadcrumbs();
	});

	onDestroy(() => {
		windowManager.clearNavigation('projects');
	});
</script>

{#if currentView === 'list'}
	<!-- Project list view -->
	<FileManagerView
		columns={listColumns}
		sortKey={projectsState.sortBy}
		sortOrder={projectsState.sortOrder}
		onsort={handleListSort}
		itemCount={projectsState.total}
		itemLabel="project"
		isLoading={projectsState.isLoading && !projectsState.hasLoaded}
		hasMore={projectsState.items.length < projectsState.total}
		onloadmore={() => projectsState.loadProjects({ page: projectsState.page + 1 })}
		onbackgroundclick={() => selectedId = null}
		emptyIcon="folder"
		emptyMessage={projectsState.searchQuery ? 'No matching projects' : 'No projects yet'}
	>
		{#snippet toolbar()}
			<div class="relative">
				<input
					type="text"
					placeholder="Search..."
					class="h-6 w-32 rounded border border-border-subtle bg-bg-input px-2 text-[10px] text-text-primary placeholder:text-text-dim/40 focus:border-neon-cyan/30 focus:outline-none"
					value={searchInput}
					oninput={(e) => handleSearch(e.currentTarget.value)}
				/>
			</div>
			<button
				class="flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors {projectsState.statusFilter === 'archived' ? 'bg-neon-purple/10 text-neon-purple' : 'text-text-dim hover:bg-bg-hover hover:text-text-secondary'}"
				onclick={handleFilterToggle}
				title="Toggle active/archived"
			>
				<Icon name="archive" size={10} />
				{projectsState.statusFilter === 'archived' ? 'Archived' : 'Active'}
			</button>
		{/snippet}

		{#snippet rows()}
			{#each projectsState.items as project (project.id)}
				<FileManagerRow onselect={() => selectedId = project.id} onopen={() => navigateTo('project', project.id)} oncontextmenu={(e) => openCtxMenu(e, project.id, projectActions(project))} active={selectedId === project.id} testId="project-row-{project.id}">
					<div class="flex flex-1 min-w-0 items-center gap-3">
						<Icon
							name="folder"
							size={16}
							class="{project.status === 'archived' ? 'text-text-dim/40' : 'text-neon-yellow/70'} shrink-0"
						/>
						<span class="text-xs font-medium text-text-primary truncate">{project.name}</span>
						{#if project.has_context}
							<span class="h-1.5 w-1.5 rounded-full bg-neon-green shrink-0" title="Has context profile"></span>
						{/if}
						{#if project.status === 'archived'}
							<span class="text-[9px] text-text-dim/50 shrink-0">(archived)</span>
						{/if}
					</div>
					<div class="w-16 text-right text-[10px] text-text-dim tabular-nums">
						{project.prompt_count}
					</div>
					<div class="w-24 text-[10px] text-text-dim">
						{formatRelativeTime(project.updated_at)}
					</div>
				</FileManagerRow>
			{/each}
		{/snippet}
	</FileManagerView>

{:else}
	<!-- Project detail (prompts) view -->
	<FileManagerView
		columns={promptColumns}
		sortKey=""
		sortOrder="asc"
		onsort={() => {}}
		itemCount={activeProjectData?.prompts.length ?? 0}
		itemLabel="prompt"
		isLoading={activeProjectLoading}
		onbackgroundclick={() => selectedId = null}
		emptyIcon="file-text"
		emptyMessage="No prompts yet"
	>
		{#snippet toolbar()}{/snippet}

		{#snippet rows()}
			{#if activeProjectData}
				{#each activeProjectData.prompts as prompt (prompt.id)}
					<FileManagerRow onselect={() => selectedId = prompt.id} onopen={() => handlePromptOpen(prompt)} oncontextmenu={(e) => openCtxMenu(e, prompt.id, promptActions)} active={selectedId === prompt.id} testId="prompt-row-{prompt.id}">
						<div class="flex flex-1 min-w-0 items-center gap-3">
							<Icon name="file-text" size={16} class="text-neon-cyan/70 shrink-0" />
							<span class="text-xs text-text-primary truncate block">
								{toFilename(prompt.content)}
							</span>
						</div>
						<div class="w-10 text-right text-[10px] text-text-dim tabular-nums">
							v{prompt.version}
						</div>
						<div class="w-14 text-right text-[10px] text-text-dim tabular-nums">
							{prompt.forge_count}
						</div>
						<div class="w-24 text-[10px] text-text-dim">
							{formatRelativeTime(prompt.updated_at)}
						</div>
					</FileManagerRow>
				{/each}
			{/if}
		{/snippet}
	</FileManagerView>
{/if}

<DesktopContextMenu
	open={ctxMenu.open}
	x={ctxMenu.x}
	y={ctxMenu.y}
	actions={ctxMenu.actions}
	onaction={handleContextAction}
	onclose={closeCtxMenu}
/>

<ConfirmModal
	open={confirmAction !== null}
	title={confirmAction?.type === 'delete-project' ? 'Delete Project' : 'Delete Prompt'}
	message={confirmAction ? `Permanently delete "${confirmAction.label}"? This cannot be undone.` : ''}
	confirmLabel="Delete"
	onconfirm={handleConfirmAction}
	oncancel={() => confirmAction = null}
/>
