<script lang="ts">
	import { onMount } from 'svelte';
	import FileManagerRow from './FileManagerRow.svelte';
	import Icon from './Icon.svelte';
	import { fsOrchestrator } from '$lib/stores/filesystemOrchestrator.svelte';
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import { systemBus } from '$lib/services/systemBus.svelte';
	import { openDocument } from '$lib/utils/documentOpener';
	import {
		createFolderDescriptor,
		createPromptDescriptor,
		createArtifactDescriptor,
	} from '$lib/utils/fileDescriptor';
	import { toForgeFilename } from '$lib/utils/fileTypes';
	import { normalizeScore, getScoreBadgeClass } from '$lib/utils/format';
	import { DRAG_MIME, decodeDragPayload, type DragPayload } from '$lib/utils/dragPayload';
	import { fetchPromptForges, type FsNode, type PathSegment, type ForgeResultSummary } from '$lib/api/client';

	let { folderId }: { folderId: string } = $props();

	function autoFocus(node: HTMLElement) {
		node.focus();
	}

	let nodes: FsNode[] = $state([]);
	let path: PathSegment[] = $state([]);
	let loading = $state(true);
	let error = $state(false);
	let selectedId: string | null = $state(null);
	let newFolderInput = $state(false);
	let newFolderName = $state('');
	let dropTargetId: string | null = $state(null);

	// ── Forge expansion state ──
	let expandedPrompts: Set<string> = $state(new Set());
	let forgeCache: Map<string, ForgeResultSummary[]> = $state(new Map());
	let forgeLoading: Set<string> = $state(new Set());

	async function loadContents() {
		loading = true;
		error = false;
		try {
			const result = await fsOrchestrator.loadChildren(folderId);
			nodes = result;
			path = await fsOrchestrator.getPath(folderId);
		} catch {
			error = true;
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		loadContents();
		const unsub1 = systemBus.on('fs:moved', () => loadContents());
		const unsub2 = systemBus.on('fs:created', () => loadContents());
		const unsub3 = systemBus.on('fs:deleted', () => loadContents());
		const unsub4 = systemBus.on('fs:renamed', () => loadContents());
		return () => { unsub1(); unsub2(); unsub3(); unsub4(); };
	});

	// Reload on folderId change (skip initial since onMount handles it)
	let mounted = false;
	$effect(() => {
		// eslint-disable-next-line @typescript-eslint/no-unused-expressions
		folderId; // track the prop
		if (mounted) {
			loadContents();
		}
		mounted = true;
	});

	function handleOpen(node: FsNode) {
		if (node.type === 'folder') {
			openDocument(createFolderDescriptor(node.id, node.name, node.parent_id, node.depth));
		} else {
			const parentId = node.parent_id ?? folderId;
			openDocument(createPromptDescriptor(node.id, parentId, node.name));
		}
	}

	function handleBreadcrumbClick(segment: PathSegment) {
		if (segment.id === folderId) return;
		openDocument(createFolderDescriptor(segment.id, segment.name));
	}

	async function handleCreateFolder() {
		const name = newFolderName.trim();
		if (!name) return;
		await fsOrchestrator.createFolder(name, folderId);
		newFolderInput = false;
		newFolderName = '';
	}

	function handleDragOver(e: DragEvent, targetNodeId: string) {
		if (!e.dataTransfer?.types.includes(DRAG_MIME)) return;
		e.preventDefault();
		e.dataTransfer.dropEffect = 'move';
		dropTargetId = targetNodeId;
	}

	function handleDragLeave() {
		dropTargetId = null;
	}

	async function handleDrop(e: DragEvent, targetNodeId: string | null) {
		e.preventDefault();
		dropTargetId = null;
		const raw = e.dataTransfer?.getData(DRAG_MIME);
		if (!raw) return;
		const payload = decodeDragPayload(raw);
		if (!payload) return;
		const desc = payload.descriptor;
		const type = desc.kind === 'folder' ? 'project' : 'prompt';
		await fsOrchestrator.move(type as 'project' | 'prompt', desc.id, targetNodeId);
	}

	function folderDragPayload(node: FsNode): DragPayload {
		return {
			descriptor: createFolderDescriptor(node.id, node.name, node.parent_id, node.depth),
			source: 'folder-window',
		};
	}

	function promptDragPayload(node: FsNode): DragPayload {
		return {
			descriptor: createPromptDescriptor(node.id, node.parent_id ?? folderId, node.name),
			source: 'folder-window',
		};
	}

	// ── Forge expansion ──

	async function toggleForgeExpansion(node: FsNode) {
		const id = node.id;
		if (expandedPrompts.has(id)) {
			expandedPrompts = new Set([...expandedPrompts].filter(x => x !== id));
			return;
		}
		expandedPrompts = new Set([...expandedPrompts, id]);

		// Use cache if available
		if (forgeCache.has(id)) return;

		// Fetch forges
		forgeLoading = new Set([...forgeLoading, id]);
		try {
			const parentId = node.parent_id ?? folderId;
			const result = await fetchPromptForges(parentId, id);
			forgeCache = new Map([...forgeCache, [id, result.items]]);
		} catch {
			// Silently fail — user can collapse and retry
		} finally {
			forgeLoading = new Set([...forgeLoading].filter(x => x !== id));
		}
	}

	function handleForgeClick(forge: ForgeResultSummary) {
		const name = toForgeFilename(forge.title, forge.overall_score, forge.version);
		openDocument(createArtifactDescriptor(forge.id, name));
	}
</script>

<!-- Breadcrumb bar -->
<div class="flex items-center gap-1 px-3 py-1.5 border-b border-white/5 text-xs text-text-secondary overflow-x-auto shrink-0">
	<button
		class="hover:text-neon-cyan transition-colors"
		onclick={() => windowManager.openProjectsWindow()}
	>Desktop</button>
	{#each path as segment, i}
		<span class="opacity-40">/</span>
		{#if i < path.length - 1}
			<button
				class="hover:text-neon-cyan transition-colors"
				onclick={() => handleBreadcrumbClick(segment)}
			>{segment.name}</button>
		{:else}
			<span class="text-text-primary">{segment.name}</span>
		{/if}
	{/each}
</div>

<!-- Toolbar -->
<div class="flex items-center gap-2 px-3 py-1.5 border-b border-white/5 shrink-0">
	{#if newFolderInput}
		<input
			id="folder-new-name"
			aria-label="New folder name"
			class="bg-bg-input border border-white/10 rounded px-2 py-0.5 text-xs text-text-primary w-40 outline-none focus:border-neon-cyan/40"
			placeholder="Folder name..."
			use:autoFocus
			bind:value={newFolderName}
			onkeydown={(e) => { if (e.key === 'Enter') handleCreateFolder(); if (e.key === 'Escape') { newFolderInput = false; newFolderName = ''; } }}
		/>
	{:else}
		<button
			class="text-xs text-text-secondary hover:text-neon-cyan transition-colors"
			onclick={() => { newFolderInput = true; }}
		>+ New Folder</button>
	{/if}
</div>

<!-- Content -->
<div
	class="flex-1 overflow-y-auto"
	role="list"
	ondragover={(e) => { e.preventDefault(); }}
	ondrop={(e) => handleDrop(e, folderId)}
>
	{#if loading}
		<div class="p-4 text-text-secondary text-sm text-center">Loading...</div>
	{:else if error}
		<div class="p-4 text-neon-red text-sm text-center">Failed to load folder contents</div>
	{:else if nodes.length === 0}
		<div class="p-4 text-text-secondary text-sm text-center">This folder is empty</div>
	{:else}
		{#each nodes as node (node.id)}
			{@const isFolder = node.type === 'folder'}
			{@const isDropTarget = dropTargetId === node.id && isFolder}
			{@const hasForges = !isFolder && (node.forge_count ?? 0) > 0}
			{@const isExpanded = expandedPrompts.has(node.id)}
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div
				class={isDropTarget ? 'bg-neon-cyan/10 ring-1 ring-neon-cyan/30 rounded-sm' : ''}
				ondragover={(e) => { if (isFolder) handleDragOver(e, node.id); }}
				ondragleave={() => handleDragLeave()}
				ondrop={(e) => { if (isFolder) { e.stopPropagation(); handleDrop(e, node.id); } }}
			>
				<FileManagerRow
					active={selectedId === node.id}
					onselect={() => { selectedId = node.id; }}
					onopen={() => handleOpen(node)}
					dragPayload={isFolder ? folderDragPayload(node) : promptDragPayload(node)}
				>
					{#if isFolder}
						<svg class="w-4 h-4 text-neon-yellow shrink-0" viewBox="0 0 24 24" fill="currentColor" stroke="none">
							<path d="M2 6a2 2 0 012-2h5l2 2h9a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/>
						</svg>
						<span class="text-sm text-text-primary truncate">{node.name}</span>
					{:else}
						<!-- Forge expansion chevron -->
						{#if hasForges}
							<button
								class="w-4 h-4 shrink-0 flex items-center justify-center text-text-dim hover:text-text-secondary transition-colors"
								onclick={(e) => { e.stopPropagation(); toggleForgeExpansion(node); }}
							>
								<Icon name={isExpanded ? 'chevron-down' : 'chevron-right'} size={12} />
							</button>
						{:else}
							<span class="w-4 shrink-0"></span>
						{/if}
						<svg class="w-4 h-4 text-neon-cyan shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
							<polyline points="14 2 14 8 20 8"/>
						</svg>
						<span class="text-sm text-text-primary truncate">{node.name}.md</span>
						{#if hasForges}
							<span class="text-[10px] text-neon-purple ml-1 shrink-0">{node.forge_count} forge{node.forge_count === 1 ? '' : 's'}</span>
						{/if}
						{#if node.version}
							<span class="ml-auto text-xs text-text-dim shrink-0">v{node.version}</span>
						{/if}
					{/if}
				</FileManagerRow>

				<!-- Expanded forge children -->
				{#if isExpanded && !isFolder}
					<div class="border-l border-white/5 ml-5">
						{#if forgeLoading.has(node.id)}
							<div class="px-4 py-1 text-[10px] text-text-dim">Loading forges...</div>
						{:else if forgeCache.has(node.id)}
							{@const forges = forgeCache.get(node.id) ?? []}
							{#if forges.length === 0}
								<div class="px-4 py-1 text-[10px] text-text-dim">No forges found</div>
							{:else}
								{#each forges as forge (forge.id)}
									<FileManagerRow
										active={selectedId === forge.id}
										onselect={() => { selectedId = forge.id; }}
										onopen={() => handleForgeClick(forge)}
									>
										<Icon name="zap" size={14} class="text-neon-purple shrink-0" />
										<span class="text-xs text-text-primary truncate">
											{toForgeFilename(forge.title, forge.overall_score, forge.version)}
										</span>
										{#if forge.overall_score != null}
											<span class="ml-auto shrink-0 rounded px-1 py-0.5 text-[9px] font-bold tabular-nums {getScoreBadgeClass(forge.overall_score)}">
												{normalizeScore(forge.overall_score)}
											</span>
										{/if}
									</FileManagerRow>
								{/each}
							{/if}
						{/if}
					</div>
				{/if}
			</div>
		{/each}
	{/if}
</div>
