<script lang="ts">
	import { goto } from '$app/navigation';
	import { onDestroy, untrack } from 'svelte';
	import { projectsState } from '$lib/stores/projects.svelte';
	import { promptState } from '$lib/stores/prompt.svelte';
	import { toastState } from '$lib/stores/toast.svelte';
	import { sidebarState } from '$lib/stores/sidebar.svelte';
	import { historyState } from '$lib/stores/history.svelte';
	import { formatRelativeTime, normalizeScore, getScoreBadgeClass, truncateText, formatMetadataSummary } from '$lib/utils/format';
	import MetadataSummaryLine from '$lib/components/MetadataSummaryLine.svelte';
	import type {
		ProjectDetail,
		ProjectPrompt,
		PromptVersionListResponse,
		ForgeResultListResponse,
	} from '$lib/api/client';
	import { fetchPromptVersions, fetchPromptForges, deleteOptimization } from '$lib/api/client';
	import Icon from '$lib/components/Icon.svelte';
	import ConfirmModal from '$lib/components/ConfirmModal.svelte';
	import Breadcrumbs from '$lib/components/Breadcrumbs.svelte';
	import { navigationState } from '$lib/stores/navigation.svelte';
	import { exportProjectAsZip, type ProjectExportProgress } from '$lib/utils/exportProject';

	let { data } = $props();

	let backDest = $derived(navigationState.getBackForProject());

	let _override: ProjectDetail | null = $state(null);
	let project: ProjectDetail = $derived.by(() => {
		// Reactive to data.project changes from navigation
		const base = data.project;
		// Return override if we have one for the same project, otherwise the fresh data
		if (_override && _override.id === base.id) return _override;
		return base;
	});
	let isArchived = $derived(project.status === 'archived');

	// Sync store with current project
	$effect(() => {
		projectsState.activeProject = project;
	});

	// Clear activeProject when leaving the page
	onDestroy(() => {
		projectsState.activeProject = null;
	});

	// Editing state
	let editingName = $state(false);
	let nameInput = $state('');
	let editingDescription = $state(false);
	let descInput = $state('');
	let editingPromptId: string | null = $state(null);
	let editPromptContent = $state('');

	// Add prompt
	let showAddPrompt = $state(false);
	let newPromptContent = $state('');
	let isAddingPrompt = $state(false);

	// Filter tag collapse
	let showAllFilterTags = $state(false);
	const MAX_VISIBLE_FILTER_TAGS = 6;

	// Delete confirmation
	let deletePromptModalId: string | null = $state(null);
	let confirmDeleteProject = $state(false);

	// Per-iteration delete
	let confirmDeleteForgeId: string | null = $state(null);
	let deletingForgeId: string | null = $state(null);

	// Export state
	let isExporting = $state(false);
	let exportProgress: ProjectExportProgress | null = $state(null);

	async function handleExportProject() {
		const hasForges = project.prompts.some((p) => p.forge_count > 0);
		if (!hasForges) {
			toastState.show('No forge results to export', 'info');
			return;
		}
		isExporting = true;
		exportProgress = null;
		try {
			const count = await exportProjectAsZip(project, (progress) => {
				exportProgress = progress;
			});
			toastState.show(`Exported ${count} forge result${count === 1 ? '' : 's'}`, 'success');
		} catch (err) {
			toastState.show('Export failed: ' + (err instanceof Error ? err.message : 'Unknown error'), 'error');
		} finally {
			isExporting = false;
			exportProgress = null;
		}
	}

	// Text truncation expand/collapse
	let expandedPromptText: string | null = $state(null);

	// Version history panel, lazy-loaded per prompt
	let expandedVersions: string | null = $state(null);
	let versionData: Record<string, {
		items: PromptVersionListResponse['items'];
		total: number;
		loading: boolean;
	}> = $state({});

	// Forge timeline data per prompt (for inline score badges)
	let forgeData: Record<string, {
		items: ForgeResultListResponse['items'];
		total: number;
		loaded: boolean;
	}> = $state({});

	// Selected forge per prompt card (maps promptId → forgeId)
	let selectedForgeId: Record<string, string> = $state({});

	// Expand/collapse for iteration list "+N more"
	let expandedIterations: Record<string, boolean> = $state({});

	function syncProject(updated: ProjectDetail) {
		_override = updated;
	}

	async function saveName() {
		const trimmed = nameInput.trim();
		if (!trimmed || trimmed === project.name) {
			editingName = false;
			return;
		}
		const updated = await projectsState.update(project.id, { name: trimmed });
		if (updated) {
			syncProject(updated);
			toastState.show('Project renamed', 'success');
		} else {
			toastState.show('Failed to rename — name may already exist', 'error');
		}
		editingName = false;
	}

	async function saveDescription() {
		const updated = await projectsState.update(project.id, { description: descInput.trim() || '' });
		if (updated) {
			syncProject(updated);
		}
		editingDescription = false;
	}

	async function handleArchiveToggle() {
		if (project.status === 'active') {
			const result = await projectsState.archive(project.id);
			if (result) {
				syncProject({ ...project, status: 'archived', updated_at: result.updated_at });
				toastState.show('Project archived', 'success');
			} else {
				toastState.show('Failed to archive project', 'error');
			}
		} else {
			const result = await projectsState.unarchive(project.id);
			if (result) {
				syncProject({ ...project, status: 'active', updated_at: result.updated_at });
				toastState.show('Project restored', 'success');
			} else {
				toastState.show('Failed to restore project', 'error');
			}
		}
	}

	async function handleDeleteProject() {
		confirmDeleteProject = false;
		const success = await projectsState.remove(project.id);
		if (success) {
			toastState.show('Project deleted', 'success');
			goto('/');
		} else {
			toastState.show('Failed to delete project', 'error');
		}
	}

	async function handleAddPrompt() {
		const content = newPromptContent.trim();
		if (!content || isAddingPrompt) return;
		isAddingPrompt = true;
		try {
			const prompt = await projectsState.addPrompt(project.id, content);
			if (prompt) {
				syncProject({ ...project, prompts: [...project.prompts, prompt] });
				newPromptContent = '';
				showAddPrompt = false;
			}
		} finally {
			isAddingPrompt = false;
		}
	}

	function startEditPrompt(p: ProjectPrompt) {
		editingPromptId = p.id;
		editPromptContent = p.content;
	}

	async function savePromptEdit() {
		if (!editingPromptId) return;
		const pid = editingPromptId;
		const updated = await projectsState.updatePrompt(project.id, pid, editPromptContent);
		if (updated) {
			syncProject({
				...project,
				prompts: project.prompts.map((p) => {
					if (p.id !== updated.id) return p;
					// Preserve latest_forge since single-prompt API doesn't return it
					return { ...updated, latest_forge: updated.latest_forge ?? p.latest_forge };
				}),
			});
			// Invalidate caches so data re-fetches
			delete forgeData[pid];
			delete versionData[pid];
			delete selectedForgeId[pid];
			delete expandedIterations[pid];
		}
		editingPromptId = null;
	}

	async function handleDeletePrompt(promptId: string) {
		deletePromptModalId = null;
		const success = await projectsState.removePrompt(project.id, promptId);
		if (success) {
			syncProject({ ...project, prompts: project.prompts.filter((p) => p.id !== promptId) });
			delete forgeData[promptId];
			delete versionData[promptId];
			delete selectedForgeId[promptId];
			delete expandedIterations[promptId];
			toastState.show('Prompt card deleted', 'success');
			historyState.loadHistory();
		} else {
			toastState.show('Failed to delete prompt card', 'error');
		}
	}

	async function handleDeleteForge(promptId: string, forgeId: string) {
		confirmDeleteForgeId = null;
		deletingForgeId = forgeId;
		try {
			const success = await deleteOptimization(forgeId);
			if (success) {
				// Update local forge data
				const data = forgeData[promptId];
				const remainingItems = data
					? data.items.filter((f) => f.id !== forgeId)
					: [];
				if (data) {
					forgeData[promptId] = {
						...data,
						items: remainingItems,
						total: data.total - 1,
					};
				}
				// Update prompt forge count and latest_forge in local state
				syncProject({
					...project,
					prompts: project.prompts.map((p) => {
						if (p.id !== promptId) return p;
						const newCount = Math.max(0, p.forge_count - 1);
						// If deleted forge was the latest_forge, fall back to next remaining
						let latestForge = p.latest_forge;
						if (latestForge?.id === forgeId) {
							const next = remainingItems[0];
							latestForge = next
								? { id: next.id, title: next.title, task_type: next.task_type, complexity: next.complexity, framework_applied: next.framework_applied, overall_score: next.overall_score, is_improvement: next.is_improvement, tags: next.tags }
								: null;
						}
						return { ...p, forge_count: newCount, latest_forge: latestForge };
					}),
				});
				// Clear selected forge if it was the deleted one
				if (selectedForgeId[promptId] === forgeId) {
					if (remainingItems.length > 0) {
						selectedForgeId = { ...selectedForgeId, [promptId]: remainingItems[0].id };
					} else {
						delete selectedForgeId[promptId];
					}
				}
				toastState.show('Forge iteration deleted', 'success');
				historyState.loadHistory();
			} else {
				toastState.show('Failed to delete iteration', 'error');
			}
		} finally {
			deletingForgeId = null;
		}
	}

	async function toggleVersions(promptId: string) {
		if (expandedVersions === promptId) {
			expandedVersions = null;
			return;
		}
		expandedVersions = promptId;
		if (!versionData[promptId]) {
			versionData[promptId] = { items: [], total: 0, loading: true };
			const result = await fetchPromptVersions(project.id, promptId);
			versionData[promptId] = { items: result.items, total: result.total, loading: false };
		}
	}

	// Background-fetch forge lists for prompts with forge_count > 1.
	// Uses untrack for forgeData reads to avoid re-running when fetches complete.
	$effect(() => {
		const prompts = project.prompts;
		const pid = project.id;
		for (const p of prompts) {
			if (p.forge_count > 1 && !untrack(() => forgeData[p.id])) {
				forgeData[p.id] = { items: [], total: 0, loaded: false };
				fetchPromptForges(pid, p.id)
					.then((result) => {
						forgeData[p.id] = { items: result.items, total: result.total, loaded: true };
					})
					.catch(() => {
						// Mark as loaded with empty data so spinner stops
						forgeData[p.id] = { items: [], total: 0, loaded: true };
					});
			}
		}
	});

	interface ForgeDisplayEntry {
		id: string;
		title: string | null;
		task_type: string | null;
		complexity: string | null;
		framework_applied: string | null;
		overall_score: number | null;
		is_improvement: boolean | null;
		tags: string[];
		created_at: string | null;
	}

	function getForgeTimeline(prompt: ProjectPrompt): ForgeDisplayEntry[] {
		const data = forgeData[prompt.id];
		if (data?.loaded && data.items.length > 0) {
			return data.items.map((f) => ({
				id: f.id,
				title: f.title,
				task_type: f.task_type,
				complexity: f.complexity,
				framework_applied: f.framework_applied,
				overall_score: f.overall_score,
				is_improvement: f.is_improvement,
				tags: f.tags,
				created_at: f.created_at,
			}));
		}
		// Fall back to latest_forge for single-forge or not-yet-loaded
		if (prompt.latest_forge) {
			const lf = prompt.latest_forge;
			return [{
				id: lf.id,
				title: lf.title,
				task_type: lf.task_type,
				complexity: lf.complexity,
				framework_applied: lf.framework_applied,
				overall_score: lf.overall_score,
				is_improvement: lf.is_improvement,
				tags: lf.tags,
				created_at: null,
			}];
		}
		return [];
	}

	function getActiveForge(prompt: ProjectPrompt, timeline: ForgeDisplayEntry[]): ForgeDisplayEntry | null {
		if (timeline.length === 0) return null;
		const selected = selectedForgeId[prompt.id];
		if (selected) {
			const found = timeline.find((f) => f.id === selected);
			if (found) return found;
		}
		// Default to first (latest)
		return timeline[0];
	}

	function selectForge(promptId: string, forgeId: string) {
		selectedForgeId = { ...selectedForgeId, [promptId]: forgeId };
	}

	function handleCardClick(event: MouseEvent, forgeId: string) {
		const target = event.target as HTMLElement;
		if (target.closest('button, a, input, textarea, [data-no-navigate]')) return;
		goto('/optimize/' + forgeId);
	}

	function optimizePrompt(p: ProjectPrompt) {
		promptState.set(p.content, project.name, p.id);
		goto('/');
	}

	async function movePrompt(index: number, direction: -1 | 1) {
		const newIndex = index + direction;
		if (newIndex < 0 || newIndex >= project.prompts.length) return;
		const ids = project.prompts.map((p) => p.id);
		[ids[index], ids[newIndex]] = [ids[newIndex], ids[index]];
		const success = await projectsState.reorderPrompts(project.id, ids);
		if (success) {
			const prompts = [...project.prompts];
			[prompts[index], prompts[newIndex]] = [prompts[newIndex], prompts[index]];
			const reordered = prompts.map((p, i) => ({ ...p, order_index: i }));
			syncProject({ ...project, prompts: reordered });
		}
	}

	// --- Metadata filter state ---
	type FilterCategory = 'task_type' | 'complexity' | 'framework' | 'tag';
	let activeFilters: Map<FilterCategory, Set<string>> = $state(new Map());

	let allMetadata = $derived.by(() => {
		const task_types = new Set<string>();
		const complexities = new Set<string>();
		const frameworks = new Set<string>();
		const tags = new Set<string>();
		for (const p of project.prompts) {
			const f = p.latest_forge;
			if (!f) continue;
			if (f.task_type) task_types.add(f.task_type);
			if (f.complexity) complexities.add(f.complexity);
			if (f.framework_applied) frameworks.add(f.framework_applied);
			for (const t of f.tags) tags.add(t);
		}
		return { task_types, complexities, frameworks, tags };
	});

	let hasAnyMetadata = $derived(
		allMetadata.task_types.size > 0 ||
		allMetadata.complexities.size > 0 ||
		allMetadata.frameworks.size > 0 ||
		allMetadata.tags.size > 0
	);

	let hasActiveFilters = $derived(
		Array.from(activeFilters.values()).some((s) => s.size > 0)
	);

	let filteredPrompts = $derived.by(() => {
		if (!hasActiveFilters) return project.prompts;
		return project.prompts.filter((p) => {
			const f = p.latest_forge;
			if (!f) return false; // no metadata = hidden when filters active
			for (const [category, values] of activeFilters) {
				if (values.size === 0) continue;
				let match = false;
				if (category === 'task_type') match = !!f.task_type && values.has(f.task_type);
				else if (category === 'complexity') match = !!f.complexity && values.has(f.complexity);
				else if (category === 'framework') match = !!f.framework_applied && values.has(f.framework_applied);
				else if (category === 'tag') match = f.tags.some((t) => values.has(t));
				if (!match) return false; // AND across categories
			}
			return true;
		});
	});

	function toggleFilter(category: FilterCategory, value: string) {
		const next = new Map(activeFilters);
		const set = new Set(next.get(category) || []);
		if (set.has(value)) set.delete(value);
		else set.add(value);
		next.set(category, set);
		activeFilters = next;
	}

	function isFilterActive(category: FilterCategory, value: string): boolean {
		return activeFilters.get(category)?.has(value) ?? false;
	}

	function clearAllFilters() {
		activeFilters = new Map();
	}

	const COMPLEXITY_FILTER_CLASSES: Record<string, { active: string; inactive: string }> = {
		simple: {
			active: 'bg-neon-green/20 text-neon-green ring-1 ring-neon-green/40 shadow-[0_0_6px_rgba(0,255,136,0.15)]',
			inactive: 'border border-border-subtle/30 text-neon-green/40 hover:text-neon-green hover:border-neon-green/25',
		},
		moderate: {
			active: 'bg-neon-yellow/20 text-neon-yellow ring-1 ring-neon-yellow/40 shadow-[0_0_6px_rgba(255,204,0,0.15)]',
			inactive: 'border border-border-subtle/30 text-neon-yellow/40 hover:text-neon-yellow hover:border-neon-yellow/25',
		},
		complex: {
			active: 'bg-neon-red/20 text-neon-red ring-1 ring-neon-red/40 shadow-[0_0_6px_rgba(255,0,85,0.15)]',
			inactive: 'border border-border-subtle/30 text-neon-red/40 hover:text-neon-red hover:border-neon-red/25',
		},
	};
	const COMPLEXITY_FILTER_DEFAULT = {
		active: 'bg-neon-cyan/20 text-neon-cyan ring-1 ring-neon-cyan/40 shadow-[0_0_6px_rgba(0,240,255,0.15)]',
		inactive: 'border border-border-subtle/30 text-text-dim/40 hover:text-neon-cyan hover:border-neon-cyan/25',
	};

	function getComplexityFilterClass(cx: string, active: boolean): string {
		const entry = COMPLEXITY_FILTER_CLASSES[cx] ?? COMPLEXITY_FILTER_DEFAULT;
		return active ? entry.active : entry.inactive;
	}

	function getPromptTitle(p: ProjectPrompt, forge?: ForgeDisplayEntry | null): string {
		if (forge?.title) return forge.title;
		if (p.latest_forge?.title) return p.latest_forge.title;
		const firstLine = p.content.split('\n')[0];
		return truncateText(firstLine, 60);
	}

	type LifecycleState = 'fresh' | 'forged' | 'edited' | 'evolved';

	function getPromptLifecycle(p: ProjectPrompt): LifecycleState {
		const hasEdits = p.version > 1;
		const hasForges = p.forge_count > 0;
		if (hasEdits && hasForges) return 'evolved';
		if (hasEdits) return 'edited';
		if (hasForges) return 'forged';
		return 'fresh';
	}

	function getVersionBadgeClass(expanded: boolean): string {
		return `badge inline-flex items-center gap-1 rounded-full transition-all duration-150 cursor-pointer select-none ${
			expanded
				? 'bg-neon-purple/20 text-neon-purple ring-1 ring-neon-purple/30'
				: 'bg-neon-purple/10 text-neon-purple/80 hover:bg-neon-purple/20 hover:text-neon-purple'
		}`;
	}
</script>

<div class="space-y-6">
	<!-- Back link + breadcrumbs -->
	<div class="flex items-center gap-3">
		<a
			href={backDest.url}
			class="flex items-center gap-1.5 rounded-lg bg-bg-card/60 px-3 py-1.5 text-xs text-text-dim transition-colors hover:text-neon-cyan"
			data-testid="back-link"
		>
			<Icon name="chevron-left" size={12} />
			{backDest.label}
		</a>
		<span class="text-text-dim/30">|</span>
		<Breadcrumbs segments={[{ label: 'Home', href: '/' }, { label: project.name }]} />
	</div>

	<!-- Project header -->
	<div class="rounded-xl border border-border-subtle bg-bg-card p-5">
		<div class="flex items-start justify-between gap-4">
			<div class="min-w-0 flex-1">
				{#if editingName && !isArchived}
					<div class="flex items-center gap-2">
						<input
							type="text"
							bind:value={nameInput}
							onkeydown={(e) => { if (e.key === 'Enter') saveName(); if (e.key === 'Escape') { editingName = false; } }}
							class="input-field flex-1 py-1 text-xl font-display font-semibold"
							data-testid="project-name-edit"
						/>
						<button
							onclick={saveName}
							class="rounded-lg bg-neon-cyan/15 px-3 py-1.5 text-xs text-neon-cyan transition-colors hover:bg-neon-cyan/25"
						>
							Save
						</button>
					</div>
				{:else if isArchived}
					<span class="text-xl font-display font-semibold text-text-primary" data-testid="project-name">
						<Icon name="folder-open" size={20} class="mr-2 inline-block text-neon-yellow/60" />
						{project.name}
					</span>
				{:else}
					<button
						type="button"
						class="cursor-pointer text-left text-xl font-display font-semibold text-text-primary transition-colors hover:text-neon-cyan"
						onclick={() => { editingName = true; nameInput = project.name; }}
						data-testid="project-name"
					>
						<Icon name="folder-open" size={20} class="mr-2 inline-block text-neon-cyan/60" />
						{project.name}
					</button>
				{/if}

				{#if editingDescription && !isArchived}
					<div class="mt-2 flex items-end gap-2">
						<textarea
							bind:value={descInput}
							onkeydown={(e) => { if (e.key === 'Escape') { editingDescription = false; } }}
							rows="2"
							class="input-field flex-1 resize-none py-1 text-sm"
							data-testid="project-desc-edit"
						></textarea>
						<button
							onclick={saveDescription}
							class="rounded-lg bg-neon-cyan/15 px-3 py-1.5 text-xs text-neon-cyan transition-colors hover:bg-neon-cyan/25"
						>
							Save
						</button>
					</div>
				{:else if isArchived}
					<p class="mt-1 text-sm text-text-dim" data-testid="project-description">
						{project.description || 'No description'}
					</p>
				{:else}
					<button
						type="button"
						class="mt-1 block cursor-pointer text-left text-sm text-text-dim transition-colors hover:text-text-secondary"
						onclick={() => { editingDescription = true; descInput = project.description || ''; }}
						data-testid="project-description"
					>
						{project.description || 'Click to add a description...'}
					</button>
				{/if}

				<div class="mt-2 flex items-center gap-3 text-[11px] text-text-dim">
					<span>Created {formatRelativeTime(project.created_at)}</span>
					<span>Updated {formatRelativeTime(project.updated_at)}</span>
					{#if project.status === 'archived'}
						<span class="badge rounded-full bg-neon-yellow/10 text-neon-yellow">archived</span>
					{:else}
						<span class="badge rounded-full bg-neon-green/10 text-neon-green">{project.status}</span>
					{/if}
				</div>
			</div>

			<div class="flex shrink-0 items-center gap-1.5">
				{#if confirmDeleteProject}
					<span class="text-[10px] text-neon-red">Delete project?</span>
					<button
						onclick={handleDeleteProject}
						class="rounded-lg bg-neon-red/15 px-2.5 py-1 text-xs text-neon-red transition-colors hover:bg-neon-red/25"
						data-testid="confirm-delete-project"
					>
						Confirm
					</button>
					<button
						onclick={() => { confirmDeleteProject = false; }}
						class="rounded-lg bg-bg-hover px-2.5 py-1 text-xs text-text-dim transition-colors hover:bg-bg-hover/80"
					>
						Cancel
					</button>
				{:else}
					<button
						onclick={() => { sidebarState.setTab('history'); historyState.setFilterProjectId(project.id); }}
						class="inline-flex items-center gap-1 rounded-lg border border-neon-cyan/15 px-2.5 py-1 text-xs text-neon-cyan/70 transition-colors hover:bg-neon-cyan/8 hover:text-neon-cyan"
						data-testid="view-history-btn"
					>
						<Icon name="clock" size={12} />
						View history
					</button>
					<button
						onclick={handleExportProject}
						disabled={isExporting}
						class="inline-flex items-center gap-1 rounded-lg border border-neon-cyan/15 px-2.5 py-1 text-xs text-neon-cyan/70 transition-colors hover:bg-neon-cyan/8 hover:text-neon-cyan disabled:opacity-40"
						data-testid="export-project-btn"
					>
						{#if isExporting}
							<Icon name="spinner" size={12} class="animate-spin" />
							Exporting{exportProgress ? ` (${exportProgress.fetched}/${exportProgress.total})` : '...'}
						{:else}
							<Icon name="download" size={12} />
							Export
						{/if}
					</button>
					{#if project.status === 'archived'}
						<button
							onclick={handleArchiveToggle}
							class="inline-flex items-center gap-1 rounded-lg border border-neon-green/15 px-2.5 py-1 text-xs text-neon-green/70 transition-colors hover:bg-neon-green/8 hover:text-neon-green"
							data-testid="restore-project-btn"
						>
							<Icon name="refresh" size={12} />
							Restore
						</button>
					{:else}
						<button
							onclick={handleArchiveToggle}
							class="inline-flex items-center gap-1 rounded-lg border border-neon-yellow/15 px-2.5 py-1 text-xs text-neon-yellow/70 transition-colors hover:bg-neon-yellow/8 hover:text-neon-yellow"
							data-testid="archive-project-btn"
						>
							<Icon name="archive" size={12} />
							Archive
						</button>
					{/if}
					<button
						onclick={() => { confirmDeleteProject = true; }}
						class="inline-flex items-center gap-1 rounded-lg border border-neon-red/15 px-2.5 py-1 text-xs text-neon-red/70 transition-colors hover:bg-neon-red/8 hover:text-neon-red"
						data-testid="delete-project-btn"
					>
						<Icon name="trash-2" size={12} />
						Delete
					</button>
				{/if}
			</div>
		</div>
	</div>

	{#if isArchived}
		<div class="flex items-center gap-3 rounded-xl border border-neon-yellow/20 bg-neon-yellow/5 px-4 py-3">
			<Icon name="archive" size={16} class="text-neon-yellow" />
			<span class="text-sm text-neon-yellow">This project is archived and read-only.</span>
		</div>
	{/if}

	<!-- Prompts section -->
	<div>
		<div class="mb-3 flex items-center justify-between">
			<h2 class="text-sm font-medium text-text-secondary">
				{#if hasActiveFilters}
					Prompts ({filteredPrompts.length}/{project.prompts.length})
				{:else}
					Prompts ({project.prompts.length})
				{/if}
			</h2>
			{#if !isArchived}
				<button
					onclick={() => { showAddPrompt = !showAddPrompt; }}
					class="inline-flex items-center gap-1 rounded-lg border border-neon-cyan/20 px-2.5 py-1 text-xs text-neon-cyan transition-colors hover:bg-neon-cyan/8"
					data-testid="add-prompt-btn"
				>
					<Icon name="plus" size={12} />
					Add Prompt
				</button>
			{/if}
		</div>

		<!-- Metadata filter bar -->
		{#if hasAnyMetadata}
			{@const allTags = [...allMetadata.tags]}
			{@const visibleTags = showAllFilterTags ? allTags : allTags.slice(0, MAX_VISIBLE_FILTER_TAGS)}
			{@const hiddenTagCount = allTags.length - MAX_VISIBLE_FILTER_TAGS}
			<div class="relative mb-3 rounded-lg border border-border-subtle/50 bg-bg-card/40 py-2 pl-2 pr-12" data-testid="filter-bar">
				{#if hasActiveFilters}
					<button
						onclick={clearAllFilters}
						class="absolute right-2.5 top-2 rounded-full bg-bg-hover px-2 py-0.5 text-[10px] text-text-dim transition-colors hover:bg-bg-hover/80 hover:text-text-secondary"
						data-testid="clear-filters"
					>
						Clear
					</button>
				{/if}
				<div class="flex flex-col gap-1">
					<!-- Task type row -->
					{#if allMetadata.task_types.size > 0}
						<div class="flex items-baseline gap-2.5 rounded-md border-l-2 border-l-neon-cyan bg-neon-cyan/[0.03] py-1.5 pl-2.5 pr-2">
							<span class="w-[52px] shrink-0 select-none text-[9px] font-medium uppercase tracking-wider text-text-dim/70">Type</span>
							<div class="flex flex-wrap items-center gap-1.5">
								{#each [...allMetadata.task_types] as tt}
									<button
										onclick={() => toggleFilter('task_type', tt)}
										class="rounded-full px-2 py-0.5 text-[10px] font-medium transition-all duration-150
											{isFilterActive('task_type', tt)
												? 'bg-neon-cyan/20 text-neon-cyan ring-1 ring-neon-cyan/40 shadow-[0_0_6px_rgba(0,240,255,0.15)]'
												: 'border border-border-subtle/30 text-neon-cyan/40 hover:text-neon-cyan hover:border-neon-cyan/25'}"
										data-testid="filter-task-type"
									>
										{tt}
									</button>
								{/each}
							</div>
						</div>
					{/if}
					<!-- Complexity row -->
					{#if allMetadata.complexities.size > 0}
						<div class="flex items-baseline gap-2.5 rounded-md border-l-2 border-l-neon-yellow bg-neon-yellow/[0.02] py-1.5 pl-2.5 pr-2">
							<span class="w-[52px] shrink-0 select-none text-[9px] font-medium uppercase tracking-wider text-text-dim/70">Level</span>
							<div class="flex flex-wrap items-center gap-1.5">
								{#each [...allMetadata.complexities] as cx}
									<button
										onclick={() => toggleFilter('complexity', cx)}
										class="rounded-full px-2 py-0.5 text-[10px] font-medium transition-all duration-150
											{getComplexityFilterClass(cx, isFilterActive('complexity', cx))}"
										data-testid="filter-complexity"
									>
										{cx}
									</button>
								{/each}
							</div>
						</div>
					{/if}
					<!-- Framework/strategy row -->
					{#if allMetadata.frameworks.size > 0}
						<div class="flex items-baseline gap-2.5 rounded-md border-l-2 border-l-neon-purple bg-neon-purple/[0.03] py-1.5 pl-2.5 pr-2">
							<span class="w-[52px] shrink-0 select-none text-[9px] font-medium uppercase tracking-wider text-text-dim/70">Strategy</span>
							<div class="flex flex-wrap items-center gap-1.5">
								{#each [...allMetadata.frameworks] as fw}
									<button
										onclick={() => toggleFilter('framework', fw)}
										class="rounded-full px-2 py-0.5 text-[10px] font-medium transition-all duration-150
											{isFilterActive('framework', fw)
												? 'bg-neon-purple/20 text-neon-purple ring-1 ring-neon-purple/40 shadow-[0_0_6px_rgba(176,0,255,0.15)]'
												: 'border border-border-subtle/30 text-neon-purple/40 hover:text-neon-purple hover:border-neon-purple/25'}"
										data-testid="filter-framework"
									>
										{fw}
									</button>
								{/each}
							</div>
						</div>
					{/if}
					<!-- Tags row (collapsible) -->
					{#if allTags.length > 0}
						<div class="flex items-baseline gap-2.5 rounded-md border-l-2 border-l-neon-green bg-neon-green/[0.03] py-1.5 pl-2.5 pr-2">
							<span class="w-[52px] shrink-0 select-none text-[9px] font-medium uppercase tracking-wider text-text-dim/70">Tags</span>
							<div class="flex flex-wrap items-center gap-1.5">
								{#each visibleTags as tag}
									<button
										onclick={() => toggleFilter('tag', tag)}
										class="transition-all duration-150
											{isFilterActive('tag', tag)
												? 'rounded-full bg-neon-green/20 px-2 py-0.5 text-[10px] font-medium text-neon-green ring-1 ring-neon-green/40 shadow-[0_0_6px_rgba(34,255,136,0.15)]'
												: 'tag-chip hover:text-neon-green'}"
										data-testid="filter-tag"
									>
										#{tag}
									</button>
								{/each}
								{#if hiddenTagCount > 0}
									<button
										onclick={() => { showAllFilterTags = !showAllFilterTags; }}
										class="text-[10px] text-text-dim transition-colors hover:text-text-secondary"
										data-testid="toggle-filter-tags"
									>
										{showAllFilterTags ? 'Show less' : `+${hiddenTagCount} more`}
									</button>
								{/if}
							</div>
						</div>
					{/if}
				</div>
			</div>
		{/if}

		{#if showAddPrompt && !isArchived}
			<div class="animate-fade-in mb-3 rounded-xl border border-neon-cyan/15 bg-bg-card p-4" data-testid="add-prompt-form">
				<textarea
					bind:value={newPromptContent}
					placeholder="Enter prompt content..."
					rows="3"
					class="input-field w-full resize-y py-2 text-sm"
					data-testid="new-prompt-textarea"
				></textarea>
				<div class="mt-2 flex gap-2">
					<button
						onclick={handleAddPrompt}
						disabled={!newPromptContent.trim() || isAddingPrompt}
						class="rounded-lg bg-neon-cyan/15 px-4 py-1.5 text-xs font-medium text-neon-cyan transition-colors hover:bg-neon-cyan/25 disabled:opacity-40"
						data-testid="save-new-prompt"
					>
						{isAddingPrompt ? 'Adding...' : 'Add'}
					</button>
					<button
						onclick={() => { showAddPrompt = false; newPromptContent = ''; }}
						class="rounded-lg bg-bg-hover px-4 py-1.5 text-xs text-text-dim transition-colors hover:bg-bg-hover/80"
					>
						Cancel
					</button>
				</div>
			</div>
		{/if}

		{#if project.prompts.length === 0 && !showAddPrompt}
			<div class="flex flex-col items-center justify-center rounded-xl border border-border-subtle bg-bg-card px-6 py-12 text-center" data-testid="prompts-empty">
				<Icon name="edit" size={28} class="mb-3 text-text-dim/40" />
				<p class="text-sm text-text-dim">No prompts yet</p>
				<p class="mt-1 text-[11px] text-text-dim/60">{isArchived ? 'This archived project has no prompts' : 'Add prompts to this project to start optimizing'}</p>
			</div>
		{:else if filteredPrompts.length === 0 && hasActiveFilters}
			<div class="flex flex-col items-center justify-center rounded-xl border border-border-subtle bg-bg-card px-6 py-8 text-center" data-testid="prompts-empty-filtered">
				<Icon name="search" size={24} class="mb-2 text-text-dim/40" />
				<p class="text-sm text-text-dim">No prompts match the active filters</p>
				<button
					onclick={clearAllFilters}
					class="mt-2 rounded-lg bg-neon-cyan/10 px-3 py-1 text-xs text-neon-cyan transition-colors hover:bg-neon-cyan/20"
				>
					Clear filters
				</button>
			</div>
		{:else}
			<div class="space-y-2">
				{#each filteredPrompts as prompt, index (prompt.id)}
					{@const timeline = getForgeTimeline(prompt)}
					{@const activeForge = getActiveForge(prompt, timeline)}
					{@const lifecycle = getPromptLifecycle(prompt)}
					<!-- svelte-ignore a11y_click_events_have_key_events -->
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<div
						class="group rounded-xl border border-border-subtle bg-bg-card p-4 transition-[border-color] duration-200 hover:border-border-glow {activeForge ? 'cursor-pointer' : ''}"
						onclick={(e) => { if (activeForge) handleCardClick(e, activeForge.id); }}
						data-testid="prompt-card"
					>
						<div class="flex items-start gap-3">
							<!-- Reorder controls (hidden when filters active to avoid index mismatch) -->
							{#if !isArchived && !hasActiveFilters}
								<div class="flex shrink-0 flex-col gap-0.5 pt-0.5 opacity-0 transition-opacity duration-150 group-hover:opacity-100 focus-within:opacity-100" data-no-navigate>
									<button
										onclick={() => movePrompt(index, -1)}
										disabled={index === 0}
										class="rounded p-0.5 text-text-dim transition-colors hover:text-neon-cyan disabled:opacity-20"
										aria-label="Move up"
									>
										<Icon name="chevron-up" size={12} />
									</button>
									<button
										onclick={() => movePrompt(index, 1)}
										disabled={index === project.prompts.length - 1}
										class="rounded p-0.5 text-text-dim transition-colors hover:text-neon-cyan disabled:opacity-20"
										aria-label="Move down"
									>
										<Icon name="chevron-down" size={12} />
									</button>
								</div>
							{/if}

							<!-- Content -->
							<div class="min-w-0 flex-1">
								<!-- Title row with score (reads from activeForge) -->
								{#if activeForge}
									<div class="mb-1.5 flex items-center gap-2">
										<span class="truncate text-xs font-medium text-text-secondary" data-testid="prompt-title">
											{getPromptTitle(prompt, activeForge)}
										</span>
										{#if activeForge.overall_score != null}
											<span class="score-circle score-circle-sm shrink-0 {getScoreBadgeClass(activeForge.overall_score)}" data-testid="prompt-score">
												{normalizeScore(activeForge.overall_score)}
											</span>
										{/if}
									</div>
								{/if}

								{#if editingPromptId === prompt.id && !isArchived}
									<textarea
										bind:value={editPromptContent}
										onkeydown={(e) => { if (e.key === 'Escape') { editingPromptId = null; } }}
										rows="4"
										class="input-field w-full resize-y py-2 text-sm"
										data-testid="edit-prompt-textarea"
									></textarea>
									<div class="mt-2 flex gap-2">
										<button
											onclick={savePromptEdit}
											class="rounded-lg bg-neon-cyan/15 px-3 py-1 text-xs text-neon-cyan transition-colors hover:bg-neon-cyan/25"
										>
											Save
										</button>
										<button
											onclick={() => { editingPromptId = null; }}
											class="rounded-lg bg-bg-hover px-3 py-1 text-xs text-text-dim transition-colors hover:bg-bg-hover/80"
										>
											Cancel
										</button>
									</div>
								{:else}
									<button
										type="button"
										onclick={() => { expandedPromptText = expandedPromptText === prompt.id ? null : prompt.id; }}
										aria-expanded={expandedPromptText === prompt.id}
										class="w-full whitespace-pre-wrap text-left text-sm leading-relaxed text-text-primary transition-colors hover:text-text-primary/80 {expandedPromptText === prompt.id ? '' : 'line-clamp-3'}"
										data-testid="prompt-content"
									>
										{prompt.content}
									</button>
								{/if}

								<!-- Metadata summary (reads from activeForge) -->
								{#if activeForge}
									{@const forgeMeta = formatMetadataSummary({
										taskType: activeForge.task_type,
										framework: activeForge.framework_applied,
									})}
									<div class="mt-2 flex flex-col gap-1.5" data-testid="prompt-metadata">
										{#if forgeMeta.length > 0 || activeForge.complexity}
											<div class="flex items-center gap-2">
												<MetadataSummaryLine segments={forgeMeta} complexity={activeForge.complexity} size="sm" />
												{#if activeForge.is_improvement === true}
													<Icon name="arrow-up" size={12} class="text-neon-green" />
												{/if}
											</div>
										{/if}
										{#if activeForge.tags.length > 0}
											<div class="flex items-center gap-2">
												{#each activeForge.tags.slice(0, 3) as tag}
													<span class="tag-chip">#{tag}</span>
												{/each}
												{#if activeForge.tags.length > 3}
													<span class="text-[10px] text-text-dim">+{activeForge.tags.length - 3}</span>
												{/if}
											</div>
										{/if}
									</div>
								{/if}

								<!-- Iteration selector (replaces horizontal forge strip) -->
								{#if prompt.forge_count > 1}
									<div class="mt-2.5" data-no-navigate data-testid="forge-iterations">
										{#if !forgeData[prompt.id]?.loaded}
											<!-- Loading state: show spinner while forge data arrives -->
											<div class="flex items-center gap-2">
												<span class="text-[10px] font-medium text-text-dim">Iterations</span>
												<Icon name="spinner" size={12} class="animate-spin text-text-dim/40" />
											</div>
										{:else if timeline.length > 1}
											{@const maxVisible = 3}
											{@const isExpanded = expandedIterations[prompt.id] ?? false}
											{@const visibleForges = isExpanded ? timeline : timeline.slice(0, maxVisible)}
											{@const hiddenCount = timeline.length - maxVisible}
											<div class="flex items-center gap-2 mb-1.5">
												<span class="text-[10px] font-medium text-text-dim">Iterations ({timeline.length})</span>
											</div>
											<div class="flex flex-col gap-1">
												{#each visibleForges as forge, i (forge.id)}
													{@const isSelected = activeForge?.id === forge.id}
													{@const isConfirmingDelete = confirmDeleteForgeId === forge.id}
													{@const isDeleting = deletingForgeId === forge.id}
													<div class="group/iter relative flex items-center gap-0.5">
														<button
															onclick={() => selectForge(prompt.id, forge.id)}
															class="flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-[11px] transition-all duration-150
																{isSelected
																	? 'bg-neon-cyan/10 ring-1 ring-neon-cyan/30 text-text-primary'
																	: 'bg-bg-secondary/30 text-text-secondary hover:bg-bg-secondary/60'}"
															data-testid="forge-iteration"
														>
															{#if forge.overall_score != null}
																<span class="score-circle score-circle-sm shrink-0 {getScoreBadgeClass(forge.overall_score)}">
																	{normalizeScore(forge.overall_score)}
																</span>
															{:else}
																<span class="score-circle score-circle-sm shrink-0 bg-bg-hover text-text-dim">-</span>
															{/if}
															<span class="truncate">
																{forge.title ?? forge.framework_applied ?? `Forge #${timeline.length - i}`}
															</span>
															{#if isSelected}
																<Icon name="chevron-right" size={10} class="ml-auto shrink-0 text-neon-cyan/60" />
															{/if}
														</button>
														{#if !isArchived}
															{#if isDeleting}
																<span class="shrink-0 p-1">
																	<Icon name="spinner" size={12} class="animate-spin text-text-dim" />
																</span>
															{:else if isConfirmingDelete}
																<button
																	onclick={() => handleDeleteForge(prompt.id, forge.id)}
																	class="shrink-0 rounded p-1 text-neon-green transition-colors hover:bg-neon-green/10"
																	aria-label="Confirm delete iteration"
																	data-testid="confirm-delete-forge"
																>
																	<Icon name="check" size={12} />
																</button>
																<button
																	onclick={() => { confirmDeleteForgeId = null; }}
																	class="shrink-0 rounded p-1 text-text-dim transition-colors hover:bg-bg-hover"
																	aria-label="Cancel delete iteration"
																>
																	<Icon name="x" size={12} />
																</button>
															{:else}
																<button
																	onclick={() => { confirmDeleteForgeId = forge.id; }}
																	class="shrink-0 rounded p-1 text-text-dim opacity-0 transition-all hover:text-neon-red group-hover/iter:opacity-100"
																	aria-label="Delete iteration"
																	data-testid="delete-forge-btn"
																>
																	<Icon name="x" size={12} />
																</button>
															{/if}
														{/if}
													</div>
												{/each}
												{#if !isExpanded && hiddenCount > 0}
													<button
														onclick={() => { expandedIterations = { ...expandedIterations, [prompt.id]: true }; }}
														class="rounded-lg px-2.5 py-1 text-[10px] text-text-dim transition-colors hover:text-neon-cyan"
													>
														+{hiddenCount} more
													</button>
												{:else if isExpanded && hiddenCount > 0}
													<button
														onclick={() => { expandedIterations = { ...expandedIterations, [prompt.id]: false }; }}
														class="rounded-lg px-2.5 py-1 text-[10px] text-text-dim transition-colors hover:text-neon-cyan"
													>
														Show less
													</button>
												{/if}
											</div>
										{/if}
									</div>
								{/if}

								<!-- Footer: lifecycle badge + timestamp + actions -->
								<div class="mt-3 flex items-center gap-3 border-t border-border-subtle pt-2.5">
									{#if lifecycle === 'fresh'}
										<span class="badge inline-flex items-center rounded-full bg-bg-hover/60 text-text-dim/50" data-testid="prompt-lifecycle-badge">
											v1
										</span>
									{:else if lifecycle === 'forged'}
										<span
											class="badge inline-flex items-center gap-1 rounded-full bg-neon-cyan/10 text-neon-cyan/70"
											title="Forged {prompt.forge_count} time{prompt.forge_count === 1 ? '' : 's'}"
											data-testid="prompt-lifecycle-badge"
										>
											<Icon name="bolt" size={10} />
											v1
											{#if prompt.forge_count > 1}
												<span class="ml-0.5 inline-flex h-3.5 w-3.5 items-center justify-center rounded-full bg-neon-cyan/20 text-[8px] font-bold leading-none">
													{prompt.forge_count}
												</span>
											{/if}
										</span>
									{:else if lifecycle === 'edited'}
										{@const expanded = expandedVersions === prompt.id}
										<button
											onclick={() => toggleVersions(prompt.id)}
											class={getVersionBadgeClass(expanded)}
											data-testid="prompt-lifecycle-badge"
										>
											<Icon name="chevron-right" size={10} class="transition-all duration-200 {expanded ? 'rotate-90' : ''}" />
											v{prompt.version}
										</button>
									{:else}
										<!-- evolved: v>1 + forges -->
										{@const expanded = expandedVersions === prompt.id}
										<button
											onclick={() => toggleVersions(prompt.id)}
											class={getVersionBadgeClass(expanded)}
											title="Forged {prompt.forge_count} time{prompt.forge_count === 1 ? '' : 's'}"
											data-testid="prompt-lifecycle-badge"
										>
											<Icon name="chevron-right" size={10} class="transition-all duration-200 {expanded ? 'rotate-90' : ''}" />
											v{prompt.version}
											<span class="ml-0.5 inline-flex h-3.5 w-3.5 items-center justify-center rounded-full bg-neon-cyan/20 text-neon-cyan text-[8px] font-bold leading-none">
												{prompt.forge_count}
											</span>
										</button>
									{/if}
									<span class="text-[11px] text-text-dim">{formatRelativeTime(prompt.updated_at)}</span>
									{#if editingPromptId !== prompt.id && !isArchived}
										<div class="ml-auto flex items-center gap-1.5">
											<button
												onclick={() => optimizePrompt(prompt)}
												class="inline-flex items-center gap-1 rounded-lg bg-neon-cyan/8 px-2 py-1 text-[10px] text-neon-cyan transition-colors hover:bg-neon-cyan/15"
												data-testid="optimize-prompt-btn"
											>
												<Icon name="bolt" size={10} />
												Optimize
											</button>
											<button
												onclick={() => startEditPrompt(prompt)}
												class="inline-flex items-center gap-1 rounded-lg bg-neon-green/8 px-2 py-1 text-[10px] text-neon-green transition-colors hover:bg-neon-green/15"
												aria-label="Edit prompt"
												data-testid="edit-prompt-btn"
											>
												<Icon name="edit" size={10} />
												Edit
											</button>
											<button
												onclick={() => { deletePromptModalId = prompt.id; }}
												class="inline-flex items-center gap-1 rounded-lg bg-neon-red/8 px-2 py-1 text-[10px] text-neon-red transition-colors hover:bg-neon-red/15"
												aria-label="Delete prompt card"
												data-testid="delete-prompt-btn"
											>
												<Icon name="trash-2" size={10} />
											</button>
										</div>
									{/if}
								</div>

								<!-- Version history panel (only for v2+) -->
								{#if expandedVersions === prompt.id && prompt.version > 1}
									<div class="animate-fade-in mt-3 rounded-lg border border-border-subtle/50 bg-bg-primary/30 p-3" data-testid="versions-panel">
										{#if versionData[prompt.id]?.loading}
											<div class="flex items-center gap-2 py-2">
												<Icon name="spinner" size={14} class="animate-spin text-neon-purple/60" />
												<span class="text-xs text-text-dim">Loading versions...</span>
											</div>
										{:else if !versionData[prompt.id]?.items.length}
											<p class="text-[11px] text-text-dim">No snapshots yet — edits before versioning was deployed aren't captured</p>
										{:else}
											<div class="space-y-2">
												{#each versionData[prompt.id].items as ver}
													<div class="rounded-md bg-bg-secondary/40 p-2">
														<div class="flex items-center gap-2">
															<span class="badge rounded-full bg-neon-purple/10 text-neon-purple text-[9px]">v{ver.version}</span>
															<span class="text-[10px] text-text-dim">{formatRelativeTime(ver.created_at)}</span>
															{#if ver.optimization_id}
																<a
																	href="/optimize/{ver.optimization_id}"
																	class="text-[10px] text-neon-cyan/70 transition-colors hover:text-neon-cyan"
																>
																	via forge
																</a>
															{/if}
														</div>
														<p class="mt-1 line-clamp-3 text-[11px] leading-relaxed text-text-secondary">{ver.content}</p>
													</div>
												{/each}
											</div>
										{/if}
									</div>
								{/if}
							</div>
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>

<!-- Delete prompt card confirmation modal -->
{#if deletePromptModalId}
	{@const deletePrompt = project.prompts.find((p) => p.id === deletePromptModalId)}
	<ConfirmModal
		open={true}
		title="Delete prompt card"
		message={deletePrompt
			? `This will permanently delete this prompt and ${deletePrompt.forge_count > 0 ? `all ${deletePrompt.forge_count} forge iteration${deletePrompt.forge_count === 1 ? '' : 's'}` : 'its data'}. This action cannot be undone.`
			: ''}
		confirmLabel="Delete"
		variant="danger"
		onconfirm={() => { if (deletePromptModalId) handleDeletePrompt(deletePromptModalId); }}
		oncancel={() => { deletePromptModalId = null; }}
	/>
{/if}
