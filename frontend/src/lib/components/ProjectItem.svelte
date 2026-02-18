<script lang="ts">
	import { goto } from '$app/navigation';
	import { projectsState } from '$lib/stores/projects.svelte';
	import { toastState } from '$lib/stores/toast.svelte';
	import { formatRelativeTime } from '$lib/utils/format';
	import type { ProjectSummary } from '$lib/api/client';
	import Icon from './Icon.svelte';

	let { project }: { project: ProjectSummary } = $props();

	let confirmDeleteId: string | null = $state(null);

	function navigate() {
		goto(`/projects/${project.id}`);
	}

	function requestDelete(e: Event) {
		e.stopPropagation();
		confirmDeleteId = project.id;
	}

	async function confirmDelete(e: Event) {
		e.stopPropagation();
		confirmDeleteId = null;
		const success = await projectsState.remove(project.id);
		if (success) {
			toastState.show(`"${project.name}" deleted`, 'success');
		} else {
			toastState.show('Failed to delete project', 'error');
		}
	}

	function cancelDelete(e: Event) {
		e.stopPropagation();
		confirmDeleteId = null;
	}

	async function handleArchive(e: Event) {
		e.stopPropagation();
		const result = await projectsState.archive(project.id);
		if (result) {
			toastState.show(`"${project.name}" archived`, 'success');
		} else {
			toastState.show('Failed to archive project', 'error');
		}
	}

	async function handleUnarchive(e: Event) {
		e.stopPropagation();
		const result = await projectsState.unarchive(project.id);
		if (result) {
			toastState.show(`"${project.name}" restored`, 'success');
		} else {
			toastState.show('Failed to restore project', 'error');
		}
	}

	const isArchived = $derived(projectsState.statusFilter === 'archived');

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			navigate();
		} else if (e.key === 'Escape' && confirmDeleteId) {
			e.stopPropagation();
			confirmDeleteId = null;
		}
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="sidebar-card group relative mb-0.5 min-h-[72px] w-full cursor-pointer rounded-xl
		border border-transparent p-3 text-left outline-none
		transition-[background-color,border-color,box-shadow] duration-200
		hover:border-border-glow hover:bg-bg-hover/40
		focus-visible:border-neon-cyan/40 focus-visible:bg-bg-hover/20 focus-visible:shadow-[0_0_12px_rgba(0,229,255,0.08)]
		active:bg-bg-hover/60"
	onclick={navigate}
	onkeydown={handleKeydown}
	role="button"
	tabindex="0"
	data-testid="project-item"
>
	<div class="mb-1 flex items-center gap-1.5">
		<Icon name="folder" size={13} class="shrink-0 {isArchived ? 'text-neon-yellow/60' : 'text-neon-cyan/60'}" />
		<span class="min-w-0 truncate text-sm leading-snug text-text-primary">{project.name}</span>
		<span class="badge ml-auto shrink-0 rounded-full {isArchived ? 'bg-neon-yellow/10 text-neon-yellow' : 'bg-neon-cyan/10 text-neon-cyan'}">
			{project.prompt_count}
		</span>
	</div>
	<div class="text-[11px] text-text-dim">
		{formatRelativeTime(project.updated_at)}
	</div>

	<!-- Action buttons overlay (full-card, matches HistoryEntry pattern) -->
	{#if confirmDeleteId !== project.id}
		<div class="sidebar-card-overlay absolute inset-0 z-10 flex flex-col justify-between rounded-xl bg-bg-card p-3">
			<div>
				<div class="flex items-center gap-1.5">
					<Icon name="folder" size={13} class="shrink-0 {isArchived ? 'text-neon-yellow/60' : 'text-neon-cyan/60'}" />
					<span class="min-w-0 truncate text-sm leading-snug text-text-primary">{project.name}</span>
					<span class="badge ml-auto shrink-0 rounded-full {isArchived ? 'bg-neon-yellow/10 text-neon-yellow' : 'bg-neon-cyan/10 text-neon-cyan'}">
						{project.prompt_count}
					</span>
				</div>
				<div class="mt-0.5 text-[11px] text-text-dim">
					{formatRelativeTime(project.updated_at)}
				</div>
			</div>
			<div class="flex items-center gap-1">
				<button
					class="btn-ghost inline-flex items-center gap-1 py-0.5 text-[10px] text-neon-cyan bg-neon-cyan/8
						hover:bg-neon-cyan/15 active:bg-neon-cyan/22 transition-colors
						focus-visible:outline-offset-0"
					onclick={(e) => { e.stopPropagation(); navigate(); }}
					data-testid="project-open-btn"
				>
					<Icon name="folder-open" size={10} />
					Open
				</button>
				{#if isArchived}
					<button
						class="btn-ghost inline-flex items-center gap-1 py-0.5 text-[10px] text-neon-green bg-neon-green/8
							hover:bg-neon-green/15 active:bg-neon-green/22 transition-colors
							focus-visible:outline-offset-0"
						onclick={(e) => handleUnarchive(e)}
						aria-label="Restore project"
						data-testid="project-restore-btn"
					>
						<Icon name="refresh" size={10} />
						Restore
					</button>
				{:else}
					<button
						class="btn-ghost inline-flex items-center gap-1 py-0.5 text-[10px] text-neon-yellow bg-neon-yellow/8
							hover:bg-neon-yellow/15 active:bg-neon-yellow/22 transition-colors
							focus-visible:outline-offset-0"
						onclick={(e) => handleArchive(e)}
						aria-label="Archive project"
						data-testid="project-archive-btn"
					>
						<Icon name="archive" size={10} />
						Archive
					</button>
				{/if}
				<button
					class="btn-ghost ml-auto inline-flex items-center gap-1 py-0.5 text-[10px] text-neon-red bg-neon-red/8
						hover:bg-neon-red/15 active:bg-neon-red/22 transition-colors
						focus-visible:outline-offset-0"
					onclick={(e) => requestDelete(e)}
					aria-label="Delete project"
					data-testid="project-delete-btn"
				>
					<Icon name="x" size={10} />
					Delete
				</button>
			</div>
		</div>
	{/if}

	<!-- Delete confirmation overlay -->
	{#if confirmDeleteId === project.id}
		<div class="absolute inset-x-0 bottom-0 z-20 flex items-center justify-between
			rounded-b-xl bg-bg-card px-3 py-2
			border-t border-neon-red/15 animate-fade-in">
			<span class="text-[10px] font-medium text-neon-red">Delete this project?</span>
			<div class="flex items-center gap-1">
				<button
					class="rounded-lg px-1.5 py-0.5 text-[10px] bg-neon-red/15 text-neon-red
						hover:bg-neon-red/25 active:bg-neon-red/35 transition-colors
						focus-visible:outline-offset-0"
					onclick={(e) => confirmDelete(e)}
					data-testid="confirm-project-delete"
				>
					Delete
				</button>
				<button
					class="rounded-lg px-1.5 py-0.5 text-[10px] bg-bg-hover text-text-dim
						hover:bg-bg-hover/80 active:bg-bg-hover/60 transition-colors
						focus-visible:outline-offset-0"
					onclick={(e) => cancelDelete(e)}
					data-testid="cancel-project-delete"
				>
					Cancel
				</button>
			</div>
		</div>
	{/if}
</div>
