<script lang="ts">
	import { goto } from "$app/navigation";
	import { projectsState } from "$lib/stores/projects.svelte";
	import { toastState } from "$lib/stores/toast.svelte";
	import { formatRelativeTime, formatExactTime } from "$lib/utils/format";
	import type { ProjectSummary } from "$lib/api/client";
	import Icon from "./Icon.svelte";
	import { Tooltip } from "./ui";

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
			toastState.show(`"${project.name}" deleted`, "success");
		} else {
			toastState.show("Failed to delete project", "error");
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
			toastState.show(`"${project.name}" archived`, "success");
		} else {
			toastState.show("Failed to archive project", "error");
		}
	}

	async function handleUnarchive(e: Event) {
		e.stopPropagation();
		const result = await projectsState.unarchive(project.id);
		if (result) {
			toastState.show(`"${project.name}" restored`, "success");
		} else {
			toastState.show("Failed to restore project", "error");
		}
	}

	const isArchived = $derived(project.status === "archived");

	function handleKeydown(e: KeyboardEvent) {
		if (
			(e.key === "Enter" || e.key === " ") &&
			e.target === e.currentTarget
		) {
			e.preventDefault();
			navigate();
		} else if (e.key === "Escape" && confirmDeleteId) {
			e.stopPropagation();
			confirmDeleteId = null;
		}
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="sidebar-card group relative mb-0.5 w-full cursor-pointer rounded-lg
		border border-transparent p-1.5 text-left outline-none
		transition-[background-color,border-color,border-left-color] duration-200
		hover:border-[var(--sidebar-accent)] hover:bg-bg-hover/40
		focus-visible:border-[var(--sidebar-accent)] focus-visible:bg-bg-hover/20
		active:bg-bg-hover/60
		{confirmDeleteId ? 'z-[2]' : ''}"
	style="--sidebar-accent: {isArchived
		? 'var(--color-neon-yellow)'
		: 'var(--color-neon-cyan)'}"
	onclick={navigate}
	onkeydown={handleKeydown}
	role="button"
	tabindex="0"
	data-testid="project-item"
>
	<div class="mb-0.5 flex items-center gap-1.5">
		<Icon
			name="folder"
			size={12}
			class="shrink-0 {isArchived
				? 'text-neon-yellow/70'
				: 'text-neon-cyan/70'}"
		/>
		<span
			class="min-w-0 truncate text-[12px] font-display font-bold tracking-tight leading-snug text-text-primary"
			>{project.name}</span
		>
		{#if project.has_context}
			<Tooltip text="Has context profile" class="shrink-0"
				><span
					class="inline-block h-1.5 w-1.5 rounded-full bg-neon-green"
				></span></Tooltip
			>
		{/if}
		<Tooltip
			text="{project.prompt_count} prompt {project.prompt_count === 1
				? 'card'
				: 'cards'}"
			class="ml-auto shrink-0"
		>
			<span
				class="score-circle score-circle-sm {isArchived
					? 'text-neon-yellow'
					: 'text-neon-cyan'}"
			>
				{project.prompt_count}
			</span>
		</Tooltip>
	</div>
	<div class="truncate text-[11px] text-text-dim">
		{project.description || "No description"}
	</div>
	<div class="text-[11px] text-text-dim">
		<Tooltip text={formatExactTime(project.updated_at)}
			><span>{formatRelativeTime(project.updated_at)}</span></Tooltip
		>
	</div>

	<!-- Floating action pill overlay -->
	{#if confirmDeleteId !== project.id}
		<div
			class="sidebar-card-overlay absolute right-1.5 top-1.5 z-10 flex items-center gap-0.5 rounded-lg border border-border-subtle bg-bg-card/90 p-0.5 backdrop-blur-md"
		>
			<Tooltip text="Open Project" side="top" interactive>
				<button
					class="flex h-5 w-5 items-center justify-center rounded-md text-neon-cyan bg-neon-cyan/5 hover:bg-neon-cyan/15 active:bg-neon-cyan/25 transition-colors focus-visible:outline-offset-0 focus-visible:ring-1 focus-visible:ring-neon-cyan"
					onclick={(e) => {
						e.stopPropagation();
						navigate();
					}}
					aria-label="Open"
					data-testid="project-open-btn"
				>
					<Icon name="folder-open" size={12} />
				</button>
			</Tooltip>
			{#if isArchived}
				<Tooltip text="Restore" side="top" interactive>
					<button
						class="flex h-5 w-5 items-center justify-center rounded-md text-neon-green bg-neon-green/5 hover:bg-neon-green/15 active:bg-neon-green/25 transition-colors focus-visible:outline-offset-0 focus-visible:ring-1 focus-visible:ring-neon-green"
						onclick={(e) => handleUnarchive(e)}
						aria-label="Restore project"
						data-testid="project-restore-btn"
					>
						<Icon name="refresh" size={12} />
					</button>
				</Tooltip>
			{:else}
				<Tooltip text="Archive" side="top" interactive>
					<button
						class="flex h-5 w-5 items-center justify-center rounded-md text-neon-yellow bg-neon-yellow/5 hover:bg-neon-yellow/15 active:bg-neon-yellow/25 transition-colors focus-visible:outline-offset-0 focus-visible:ring-1 focus-visible:ring-neon-yellow"
						onclick={(e) => handleArchive(e)}
						aria-label="Archive project"
						data-testid="project-archive-btn"
					>
						<Icon name="archive" size={12} />
					</button>
				</Tooltip>
			{/if}
			<Tooltip text="Delete" side="top" interactive>
				<button
					class="flex h-5 w-5 items-center justify-center rounded-md text-neon-red bg-neon-red/5 hover:bg-neon-red/15 active:bg-neon-red/25 transition-colors focus-visible:outline-offset-0 focus-visible:ring-1 focus-visible:ring-neon-red"
					onclick={(e) => requestDelete(e)}
					aria-label="Delete project"
					data-testid="project-delete-btn"
				>
					<Icon name="x" size={12} />
				</button>
			</Tooltip>
		</div>
	{/if}

	<!-- Delete confirmation overlay -->
	{#if confirmDeleteId === project.id}
		<div
			class="delete-confirm-bar absolute inset-x-0 bottom-0 z-20 flex items-center justify-between
			rounded-b-xl px-2 py-0.5 animate-slide-up-in"
		>
			<span class="text-[11px] font-medium text-neon-red"
				>Delete this project?</span
			>
			<div class="flex items-center gap-1">
				<button
					class="rounded-lg px-2 py-0.5 text-[11px] bg-neon-red/15 text-neon-red
						hover:bg-neon-red/25 active:bg-neon-red/35 transition-colors
						focus-visible:outline-offset-0"
					onclick={(e) => confirmDelete(e)}
					data-testid="confirm-project-delete"
				>
					Delete
				</button>
				<button
					class="rounded-lg px-2 py-0.5 text-[11px] bg-bg-hover text-text-dim
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
