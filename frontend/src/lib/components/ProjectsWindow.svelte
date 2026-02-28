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
	import { fsOrchestrator } from '$lib/stores/filesystemOrchestrator.svelte';
	import { systemBus } from '$lib/services/systemBus.svelte';
	import { forgeSession } from '$lib/stores/forgeSession.svelte';
	import { toastState } from '$lib/stores/toast.svelte';
	import { clipboardService } from '$lib/services/clipboardService.svelte';
	import { type FsNode, type PathSegment } from '$lib/api/client';
	import { formatRelativeTime, truncateText } from '$lib/utils/format';
	import { toFilename } from '$lib/utils/fileTypes';
	import { createPromptDescriptor, createFolderDescriptor } from '$lib/utils/fileDescriptor';
	import { openDocument } from '$lib/utils/documentOpener';
	import { DRAG_MIME, decodeDragPayload } from '$lib/utils/dragPayload';

	function autoFocus(node: HTMLElement) {
		node.focus();
	}

	// ── View state ──
	type ProjectsView = 'list' | 'folder';
	let currentView: ProjectsView = $state('list');
	let activeFolderId: string | null = $state(null);
	let folderNodes: FsNode[] = $state([]);
	let folderPath: PathSegment[] = $state([]);
	let folderLoading: boolean = $state(false);

	// ── Navigation stacks ──
	let backStack: Array<{ view: ProjectsView; folderId: string | null }> = $state([]);
	let forwardStack: Array<{ view: ProjectsView; folderId: string | null }> = $state([]);

	// ── Search ──
	let searchInput = $state('');
	let searchTimer: ReturnType<typeof setTimeout> | null = null;

	// ── Selection ──
	let selectedId: string | null = $state(null);

	// ── New folder ──
	let newFolderInput = $state(false);
	let newFolderName = $state('');

	// ── Drop target ──
	let dropTargetId: string | null = $state(null);

	// ── Context menu ──
	let ctxMenu = $state({ open: false, x: 0, y: 0, targetId: null as string | null, actions: [] as ContextAction[] });
	let confirmAction: { type: 'delete-project' | 'delete-prompt' | 'delete-folder'; id: string; label: string } | null = $state(null);

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

	const subfolderActions: ContextAction[] = [
		{ id: 'open-folder', label: 'Open', icon: 'folder-open' },
		{ id: 'delete-folder', label: 'Delete', icon: 'trash-2', separator: true, danger: true },
	];

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
				navigateTo('folder', targetId);
				break;
			case 'open-folder':
				navigateTo('folder', targetId);
				break;
			case 'open-review': {
				const node = folderNodes.find((n) => n.id === targetId && n.type === 'prompt');
				if (node) handleNodeOpen(node);
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
			case 'delete-folder': {
				const node = folderNodes.find((n) => n.id === targetId);
				confirmAction = { type: 'delete-folder', id: targetId, label: node?.name ?? 'this folder' };
				break;
			}
			case 'forge': {
				const node = folderNodes.find((n) => n.id === targetId && n.type === 'prompt');
				if (node && activeFolderId) {
					const projectName = folderPath[0]?.name ?? '';
					forgeSession.loadRequest({
						text: node.content ?? '',
						title: projectName,
						project: projectName,
						promptId: node.id,
						sourceAction: 'optimize',
					});
				}
				break;
			}
			case 'copy-content': {
				const node = folderNodes.find((n) => n.id === targetId && n.type === 'prompt');
				if (node?.content) {
					clipboardService.copy(node.content, 'Prompt content');
					toastState.show('Prompt content copied', 'success');
				}
				break;
			}
			case 'delete-prompt': {
				const node = folderNodes.find((n) => n.id === targetId && n.type === 'prompt');
				confirmAction = { type: 'delete-prompt', id: targetId, label: truncateText(node?.content ?? 'this prompt', 40) };
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
		} else if (type === 'delete-folder') {
			const ok = await fsOrchestrator.deleteFolder(id);
			if (ok) {
				toastState.show('Folder deleted', 'success');
				if (activeFolderId) await loadFolderContents(activeFolderId);
			} else {
				toastState.show('Failed to delete folder', 'error');
			}
		} else if (type === 'delete-prompt' && activeFolderId) {
			const ok = await projectsState.removePrompt(activeFolderId, id);
			if (ok) {
				toastState.show('Prompt deleted', 'success');
				await loadFolderContents(activeFolderId);
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

	const folderColumns: ColumnDef[] = [
		{ key: 'name', label: 'Name', width: 'flex-1', sortable: false },
		{ key: 'version', label: 'Ver', width: 'w-10', align: 'right', sortable: false },
		{ key: 'updated_at', label: 'Modified', width: 'w-24', sortable: false },
	];

	// ── Navigation functions ──
	function navigateTo(view: ProjectsView, folderId: string | null) {
		backStack = [...backStack, { view: currentView, folderId: activeFolderId }];
		forwardStack = [];
		currentView = view;
		activeFolderId = folderId;
		selectedId = null;
		newFolderInput = false;
		if (view === 'folder' && folderId) loadFolderContents(folderId);
		syncBreadcrumbs();
		syncNavigation();
	}

	function goBack() {
		if (!backStack.length) return;
		const prev = backStack[backStack.length - 1];
		backStack = backStack.slice(0, -1);
		forwardStack = [...forwardStack, { view: currentView, folderId: activeFolderId }];
		currentView = prev.view;
		activeFolderId = prev.folderId;
		selectedId = null;
		newFolderInput = false;
		if (prev.view === 'folder' && prev.folderId) loadFolderContents(prev.folderId);
		syncBreadcrumbs();
		syncNavigation();
	}

	function goForward() {
		if (!forwardStack.length) return;
		const next = forwardStack[forwardStack.length - 1];
		forwardStack = forwardStack.slice(0, -1);
		backStack = [...backStack, { view: currentView, folderId: activeFolderId }];
		currentView = next.view;
		activeFolderId = next.folderId;
		selectedId = null;
		newFolderInput = false;
		if (next.view === 'folder' && next.folderId) loadFolderContents(next.folderId);
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
		} else if (activeFolderId) {
			const segments: Array<{ label: string; icon?: string; action?: () => void }> = [
				{ label: 'Desktop', icon: 'monitor', action: () => windowManager.closeWindow('projects') },
				{ label: 'Projects', action: () => navigateTo('list', null) },
			];
			for (let i = 0; i < folderPath.length; i++) {
				const seg = folderPath[i];
				if (i < folderPath.length - 1) {
					const segId = seg.id;
					segments.push({ label: seg.name, action: () => navigateTo('folder', segId) });
				} else {
					segments.push({ label: seg.name });
				}
			}
			windowManager.setBreadcrumbs('projects', segments);
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
	async function loadFolderContents(id: string) {
		folderLoading = true;
		try {
			folderNodes = await fsOrchestrator.loadChildren(id);
			folderPath = await fsOrchestrator.getPath(id);
			syncBreadcrumbs();
		} finally {
			folderLoading = false;
		}
	}

	// ── Node open handler ──
	function handleNodeOpen(node: FsNode) {
		if (node.type === 'folder') {
			navigateTo('folder', node.id);
		} else if (activeFolderId) {
			openDocument(createPromptDescriptor(node.id, activeFolderId, node.name));
		}
	}

	// ── New folder ──
	async function handleCreateFolder() {
		const name = newFolderName.trim();
		if (!name) return;
		await fsOrchestrator.createFolder(name, activeFolderId);
		newFolderInput = false;
		newFolderName = '';
		if (activeFolderId) await loadFolderContents(activeFolderId);
	}

	// ── Drag-and-drop for folder rows ──
	function handleRowDragOver(e: DragEvent, targetNodeId: string) {
		if (!e.dataTransfer?.types.includes(DRAG_MIME)) return;
		e.preventDefault();
		e.dataTransfer.dropEffect = 'move';
		dropTargetId = targetNodeId;
	}

	function handleRowDragLeave() {
		dropTargetId = null;
	}

	async function handleRowDrop(e: DragEvent, targetNodeId: string) {
		e.preventDefault();
		e.stopPropagation();
		dropTargetId = null;
		const raw = e.dataTransfer?.getData(DRAG_MIME);
		if (!raw) return;
		const payload = decodeDragPayload(raw);
		if (!payload) return;
		const desc = payload.descriptor;
		const type = desc.kind === 'folder' ? 'project' : 'prompt';
		await fsOrchestrator.move(type as 'project' | 'prompt', desc.id, targetNodeId);
		if (activeFolderId) await loadFolderContents(activeFolderId);
	}

	// ── Search/filter ──
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

	// ── Consume pending navigation from projectsState ──
	$effect(() => {
		const pendingId = projectsState.pendingNavigateProjectId;
		if (pendingId) {
			projectsState.pendingNavigateProjectId = null;
			navigateTo('folder', pendingId);
		}
	});

	// ── Lifecycle ──
	onMount(() => {
		if (!projectsState.hasLoaded) projectsState.loadProjects();
		syncNavigation();
		syncBreadcrumbs();

		const unsub1 = systemBus.on('fs:moved', () => {
			if (activeFolderId) loadFolderContents(activeFolderId);
		});
		const unsub2 = systemBus.on('fs:created', () => {
			if (activeFolderId) loadFolderContents(activeFolderId);
		});
		const unsub3 = systemBus.on('fs:deleted', () => {
			if (activeFolderId) loadFolderContents(activeFolderId);
		});
		const unsub4 = systemBus.on('fs:renamed', () => {
			if (activeFolderId) loadFolderContents(activeFolderId);
		});

		return () => { unsub1(); unsub2(); unsub3(); unsub4(); };
	});

	onDestroy(() => {
		if (searchTimer) clearTimeout(searchTimer);
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
					id="projects-search"
					type="text"
					placeholder="Search..."
					aria-label="Search projects"
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
				<FileManagerRow onselect={() => selectedId = project.id} onopen={() => navigateTo('folder', project.id)} oncontextmenu={(e) => openCtxMenu(e, project.id, projectActions(project))} active={selectedId === project.id} testId="project-row-{project.id}">
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
	<!-- Folder view (N-level nesting) -->
	<FileManagerView
		columns={folderColumns}
		sortKey=""
		sortOrder="asc"
		onsort={() => {}}
		itemCount={folderNodes.length}
		itemLabel="item"
		isLoading={folderLoading}
		onbackgroundclick={() => selectedId = null}
		emptyIcon="folder"
		emptyMessage="This folder is empty"
	>
		{#snippet toolbar()}
			{#if newFolderInput}
				<input
					id="projects-new-folder"
					class="h-6 w-36 rounded border border-white/10 bg-bg-input px-2 text-[10px] text-text-primary outline-none focus:border-neon-cyan/40"
					placeholder="Folder name..."
					aria-label="New folder name"
					use:autoFocus
					bind:value={newFolderName}
					onkeydown={(e) => { if (e.key === 'Enter') handleCreateFolder(); if (e.key === 'Escape') { newFolderInput = false; newFolderName = ''; } }}
				/>
			{:else}
				<button
					class="text-[10px] text-text-dim hover:text-neon-cyan transition-colors"
					onclick={() => { newFolderInput = true; }}
				>+ New Folder</button>
			{/if}
		{/snippet}

		{#snippet rows()}
			{#each folderNodes as node (node.id)}
				{@const isFolder = node.type === 'folder'}
				{@const isDropTarget = dropTargetId === node.id && isFolder}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div
					class={isDropTarget ? 'bg-neon-cyan/10 ring-1 ring-neon-cyan/30 rounded-sm' : ''}
					ondragover={(e) => { if (isFolder) handleRowDragOver(e, node.id); }}
					ondragleave={() => handleRowDragLeave()}
					ondrop={(e) => { if (isFolder) { e.stopPropagation(); handleRowDrop(e, node.id); } }}
				>
					<FileManagerRow
						active={selectedId === node.id}
						onselect={() => { selectedId = node.id; }}
						onopen={() => handleNodeOpen(node)}
						oncontextmenu={(e) => openCtxMenu(e, node.id, isFolder ? subfolderActions : promptActions)}
						dragPayload={isFolder
							? { descriptor: createFolderDescriptor(node.id, node.name, node.parent_id, node.depth), source: 'projects-window' }
							: { descriptor: createPromptDescriptor(node.id, activeFolderId ?? '', node.name), source: 'projects-window' }
						}
					>
						{#if isFolder}
							<div class="flex flex-1 min-w-0 items-center gap-3">
								<Icon name="folder" size={16} class="text-neon-yellow/70 shrink-0" />
								<span class="text-xs font-medium text-text-primary truncate">{node.name}</span>
							</div>
							<div class="w-10"></div>
							<div class="w-24 text-[10px] text-text-dim">
								{node.updated_at ? formatRelativeTime(node.updated_at) : ''}
							</div>
						{:else}
							<div class="flex flex-1 min-w-0 items-center gap-3">
								<Icon name="file-text" size={16} class="text-neon-cyan/70 shrink-0" />
								<span class="text-xs text-text-primary truncate block">{node.name}</span>
							</div>
							<div class="w-10 text-right text-[10px] text-text-dim tabular-nums">
								{#if node.version}v{node.version}{/if}
							</div>
							<div class="w-24 text-[10px] text-text-dim">
								{node.updated_at ? formatRelativeTime(node.updated_at) : ''}
							</div>
						{/if}
					</FileManagerRow>
				</div>
			{/each}
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
	title={confirmAction?.type === 'delete-project' ? 'Delete Project' : confirmAction?.type === 'delete-folder' ? 'Delete Folder' : 'Delete Prompt'}
	message={confirmAction ? `Permanently delete "${confirmAction.label}"? This cannot be undone.` : ''}
	confirmLabel="Delete"
	onconfirm={handleConfirmAction}
	oncancel={() => confirmAction = null}
/>
