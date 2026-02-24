<script lang="ts">
	import { goto } from "$app/navigation";
	import { onDestroy, untrack } from "svelte";
	import { projectsState } from "$lib/stores/projects.svelte";
	import { forgeSession } from "$lib/stores/forgeSession.svelte";
	import { toastState } from "$lib/stores/toast.svelte";
	import { sidebarState } from "$lib/stores/sidebar.svelte";
	import { historyState } from "$lib/stores/history.svelte";
	import { statsState } from "$lib/stores/stats.svelte";
	import {
		formatRelativeTime,
		formatExactTime,
		normalizeScore,
		getScoreBadgeClass,
		truncateText,
		formatMetadataSummary,
	} from "$lib/utils/format";
	import { getTaskTypeColor } from "$lib/utils/taskTypes";
	import MetadataSummaryLine from "$lib/components/MetadataSummaryLine.svelte";
	import type {
		ProjectDetail,
		ProjectPrompt,
		PromptVersionListResponse,
		ForgeResultListResponse,
	} from "$lib/api/client";
	import {
		fetchPromptVersions,
		fetchPromptForges,
		deleteOptimization,
	} from "$lib/api/client";
	import Icon from "$lib/components/Icon.svelte";
	import ConfirmModal from "$lib/components/ConfirmModal.svelte";
	import ContextProfileEditor from "$lib/components/ContextProfileEditor.svelte";
	import { Separator, Tooltip, MetaBadge } from "$lib/components/ui";
	import Breadcrumbs from "$lib/components/Breadcrumbs.svelte";
	import { Collapsible } from "bits-ui";
	import {
		exportProjectAsZip,
		type ProjectExportProgress,
	} from "$lib/utils/exportProject";

	let { data } = $props();

	let _override: ProjectDetail | null = $state(null);
	let project: ProjectDetail = $derived.by(() => {
		// Reactive to data.project changes from navigation
		const base = data.project;
		// Return override if we have one for the same project, otherwise the fresh data
		if (_override && _override.id === base.id) return _override;
		return base;
	});
	let isArchived = $derived(project.status === "archived");

	// Sync store with current project
	$effect(() => {
		projectsState.activeProject = project;
	});

	// Scope header stats to this project
	$effect(() => {
		statsState.setContext(project.name);
		return () => statsState.clearProjectContext();
	});

	// Clear activeProject when leaving the page
	onDestroy(() => {
		projectsState.activeProject = null;
	});

	// Editing state
	let editingName = $state(false);
	let nameInput = $state("");
	let editingDescription = $state(false);
	let descInput = $state("");
	let editingPromptId: string | null = $state(null);
	let editPromptContent = $state("");

	// Add prompt
	let showAddPrompt = $state(false);
	let newPromptContent = $state("");
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

	// Context profile section
	let showContextProfile = $state(false);

	// Export state
	let isExporting = $state(false);
	let exportProgress: ProjectExportProgress | null = $state(null);

	async function handleExportProject() {
		const hasForges = project.prompts.some((p) => p.forge_count > 0);
		if (!hasForges) {
			toastState.show("No forge results to export", "info");
			return;
		}
		isExporting = true;
		exportProgress = null;
		try {
			const count = await exportProjectAsZip(project, (progress) => {
				exportProgress = progress;
			});
			toastState.show(
				`Exported ${count} forge result${count === 1 ? "" : "s"}`,
				"success",
			);
		} catch (err) {
			toastState.show(
				"Export failed: " +
					(err instanceof Error ? err.message : "Unknown error"),
				"error",
			);
		} finally {
			isExporting = false;
			exportProgress = null;
		}
	}

	// Text truncation expand/collapse
	let expandedPromptText: string | null = $state(null);

	// Content edit history panel, lazy-loaded per prompt
	let expandedContentHistory: string | null = $state(null);
	let versionData: Record<
		string,
		{
			items: PromptVersionListResponse["items"];
			total: number;
			loading: boolean;
		}
	> = $state({});

	// Forge timeline data per prompt (for inline score badges)
	let forgeData: Record<
		string,
		{
			items: ForgeResultListResponse["items"];
			total: number;
			loaded: boolean;
		}
	> = $state({});

	// Selected forge per prompt card (maps promptId → forgeId)
	let selectedForgeId: Record<string, string> = $state({});

	// Badge toggle: show/hide iteration list per prompt
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
		const updated = await projectsState.update(project.id, {
			name: trimmed,
		});
		if (updated) {
			syncProject(updated);
			toastState.show("Project renamed", "success");
		} else {
			toastState.show(
				"Failed to rename — name may already exist",
				"error",
			);
		}
		editingName = false;
	}

	async function saveDescription() {
		const updated = await projectsState.update(project.id, {
			description: descInput.trim() || "",
		});
		if (updated) {
			syncProject(updated);
		}
		editingDescription = false;
	}

	async function handleSaveContext(
		ctx: import("$lib/api/client").CodebaseContext,
	) {
		const updated = await projectsState.updateContextProfile(
			project.id,
			Object.keys(ctx).length > 0 ? ctx : null,
		);
		if (updated) {
			syncProject(updated);
			toastState.show("Context profile saved", "success");
		} else {
			toastState.show("Failed to save context profile", "error");
		}
	}

	async function handleArchiveToggle() {
		if (project.status === "active") {
			const result = await projectsState.archive(project.id);
			if (result) {
				syncProject({
					...project,
					status: "archived",
					updated_at: result.updated_at,
				});
				toastState.show("Project archived", "success");
			} else {
				toastState.show("Failed to archive project", "error");
			}
		} else {
			const result = await projectsState.unarchive(project.id);
			if (result) {
				syncProject({
					...project,
					status: "active",
					updated_at: result.updated_at,
				});
				toastState.show("Project restored", "success");
			} else {
				toastState.show("Failed to restore project", "error");
			}
		}
	}

	async function handleDeleteProject() {
		confirmDeleteProject = false;
		const success = await projectsState.remove(project.id);
		if (success) {
			toastState.show("Project deleted", "success");
			goto("/");
		} else {
			toastState.show("Failed to delete project", "error");
		}
	}

	async function handleAddPrompt() {
		const content = newPromptContent.trim();
		if (!content || isAddingPrompt) return;
		isAddingPrompt = true;
		try {
			const prompt = await projectsState.addPrompt(project.id, content);
			if (prompt) {
				syncProject({
					...project,
					prompts: [...project.prompts, prompt],
				});
				newPromptContent = "";
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
		const updated = await projectsState.updatePrompt(
			project.id,
			pid,
			editPromptContent,
		);
		if (updated) {
			syncProject({
				...project,
				prompts: project.prompts.map((p) => {
					if (p.id !== updated.id) return p;
					// Preserve latest_forge since single-prompt API doesn't return it
					return {
						...updated,
						latest_forge: updated.latest_forge ?? p.latest_forge,
					};
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
			syncProject({
				...project,
				prompts: project.prompts.filter((p) => p.id !== promptId),
			});
			delete forgeData[promptId];
			delete versionData[promptId];
			delete selectedForgeId[promptId];
			delete expandedIterations[promptId];
			toastState.show("Prompt card deleted", "success");
			historyState.loadHistory();
		} else {
			toastState.show("Failed to delete prompt card", "error");
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
								? {
										id: next.id,
										title: next.title,
										task_type: next.task_type,
										complexity: next.complexity,
										framework_applied:
											next.framework_applied,
										overall_score: next.overall_score,
										is_improvement: next.is_improvement,
										tags: next.tags,
										version: next.version,
									}
								: null;
						}
						return {
							...p,
							forge_count: newCount,
							latest_forge: latestForge,
						};
					}),
				});
				// Clear selected forge if it was the deleted one
				if (selectedForgeId[promptId] === forgeId) {
					if (remainingItems.length > 0) {
						selectedForgeId = {
							...selectedForgeId,
							[promptId]: remainingItems[0].id,
						};
					} else {
						delete selectedForgeId[promptId];
					}
				}
				toastState.show("Forge iteration deleted", "success");
				historyState.loadHistory();
			} else {
				toastState.show("Failed to delete iteration", "error");
			}
		} finally {
			deletingForgeId = null;
		}
	}

	async function toggleContentHistory(promptId: string) {
		if (expandedContentHistory === promptId) {
			expandedContentHistory = null;
			return;
		}
		expandedContentHistory = promptId;
		if (!versionData[promptId]) {
			versionData[promptId] = { items: [], total: 0, loading: true };
			const result = await fetchPromptVersions(project.id, promptId);
			versionData[promptId] = {
				items: result.items,
				total: result.total,
				loading: false,
			};
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
						forgeData[p.id] = {
							items: result.items,
							total: result.total,
							loaded: true,
						};
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
		version: string | null;
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
				version: f.version,
				created_at: f.created_at,
			}));
		}
		// Fall back to latest_forge for single-forge or not-yet-loaded
		if (prompt.latest_forge) {
			const lf = prompt.latest_forge;
			return [
				{
					id: lf.id,
					title: lf.title,
					task_type: lf.task_type,
					complexity: lf.complexity,
					framework_applied: lf.framework_applied,
					overall_score: lf.overall_score,
					is_improvement: lf.is_improvement,
					tags: lf.tags,
					version: lf.version,
					created_at: null,
				},
			];
		}
		return [];
	}

	function getActiveForge(
		prompt: ProjectPrompt,
		timeline: ForgeDisplayEntry[],
	): ForgeDisplayEntry | null {
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
		if (target.closest("button, a, input, textarea, [data-no-navigate]"))
			return;
		goto("/optimize/" + forgeId);
	}

	function generateDefaultTitle(content: string): string {
		const firstLine = content.split("\n")[0];
		return truncateText(firstLine, 60);
	}

	function computeNextVersion(p: ProjectPrompt): string {
		const data = forgeData[p.id];
		let maxVersion = 0;
		if (data?.loaded && data.items.length > 0) {
			for (const forge of data.items) {
				if (forge.version) {
					const match = forge.version.match(/^v(\d+)$/i);
					if (match) {
						maxVersion = Math.max(
							maxVersion,
							parseInt(match[1], 10),
						);
					}
				}
			}
		}
		if (maxVersion === 0) {
			return `v${p.forge_count + 1}`;
		}
		return `v${maxVersion + 1}`;
	}

	function optimizePrompt(p: ProjectPrompt) {
		const latestForge = p.latest_forge;
		forgeSession.loadRequest({
			text: p.content,
			project: project.name,
			promptId: p.id,
			title: latestForge?.title ?? generateDefaultTitle(p.content),
			tags: (latestForge?.tags ?? []).join(", "),
			version: latestForge?.version ?? "",
			sourceAction: "optimize",
			contextProfile: project.context_profile ?? null,
		});
		forgeSession.activate();
	}

	function reiteratePrompt(p: ProjectPrompt) {
		const latestForge = p.latest_forge;
		const nextVersion = computeNextVersion(p);
		forgeSession.loadRequest({
			text: p.content,
			project: project.name,
			promptId: p.id,
			title: latestForge?.title ?? generateDefaultTitle(p.content),
			tags: (latestForge?.tags ?? []).join(", "),
			version: nextVersion,
			sourceAction: "reiterate",
			contextProfile: project.context_profile ?? null,
		});
		forgeSession.activate();
	}

	// --- Metadata filter state ---
	type FilterCategory = "task_type" | "complexity" | "framework" | "tag";
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
			allMetadata.tags.size > 0,
	);

	let hasActiveFilters = $derived(
		Array.from(activeFilters.values()).some((s) => s.size > 0),
	);

	let filteredPrompts = $derived.by(() => {
		if (!hasActiveFilters) return project.prompts;
		return project.prompts.filter((p) => {
			const f = p.latest_forge;
			if (!f) return false; // no metadata = hidden when filters active
			for (const [category, values] of activeFilters) {
				if (values.size === 0) continue;
				let match = false;
				if (category === "task_type")
					match = !!f.task_type && values.has(f.task_type);
				else if (category === "complexity")
					match = !!f.complexity && values.has(f.complexity);
				else if (category === "framework")
					match =
						!!f.framework_applied &&
						values.has(f.framework_applied);
				else if (category === "tag")
					match = f.tags.some((t) => values.has(t));
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

	function getPromptTitle(
		p: ProjectPrompt,
		forge?: ForgeDisplayEntry | null,
	): string {
		if (forge?.title) return forge.title;
		if (p.latest_forge?.title) return p.latest_forge.title;
		const firstLine = p.content.split("\n")[0];
		return truncateText(firstLine, 60);
	}

	function getVersionBadgeClass(expanded: boolean): string {
		return `badge inline-flex items-center gap-1.5 rounded-full transition-all duration-150 cursor-pointer select-none ${
			expanded
				? "bg-neon-cyan/20 text-neon-cyan ring-1 ring-neon-cyan/30"
				: "bg-neon-cyan/10 text-neon-cyan/80 hover:bg-neon-cyan/20 hover:text-neon-cyan"
		}`;
	}
</script>

<div class="flex flex-col">
	<Breadcrumbs
		segments={[{ label: "Home", href: "/" }, { label: project.name }]}
	/>

	<!-- Project header -->
	<div class="project-header-card mt-1.5">
		<div class="flex items-start justify-between gap-2">
			<div>
				{#if editingName && !isArchived}
					<div class="flex items-center gap-2">
						<input
							type="text"
							bind:value={nameInput}
							onkeydown={(e) => {
								if (e.key === "Enter") saveName();
								if (e.key === "Escape") {
									editingName = false;
								}
							}}
							class="input-field flex-1 py-1 text-lg font-display font-bold tracking-tight"
							data-testid="project-name-edit"
						/>
						<button
							onclick={saveName}
							class="rounded-lg bg-neon-cyan/15 px-2 py-0.5 text-[11px] text-neon-cyan transition-colors hover:bg-neon-cyan/25"
						>
							Save
						</button>
					</div>
				{:else if isArchived}
					<span
						class="text-lg font-display font-bold tracking-tight text-text-primary"
						data-testid="project-name"
					>
						<Icon
							name="folder-open"
							size={16}
							class="mr-1.5 inline-block text-neon-yellow/60"
						/>
						{project.name}
					</span>
				{:else}
					<button
						type="button"
						class="cursor-pointer text-left text-lg font-display font-bold tracking-tight text-text-primary transition-colors hover:text-neon-cyan"
						onclick={() => {
							editingName = true;
							nameInput = project.name;
						}}
						data-testid="project-name"
					>
						<Icon
							name="folder-open"
							size={16}
							class="mr-1.5 inline-block text-neon-cyan/60"
						/>
						{project.name}
					</button>
				{/if}

				{#if editingDescription && !isArchived}
					<div class="mt-1 flex items-end gap-2">
						<textarea
							bind:value={descInput}
							onkeydown={(e) => {
								if (e.key === "Escape") {
									editingDescription = false;
								}
							}}
							rows="2"
							class="input-field flex-1 resize-none py-1 text-sm"
							data-testid="project-desc-edit"
						></textarea>
						<button
							onclick={saveDescription}
							class="rounded-lg bg-neon-cyan/15 px-2 py-0.5 text-[11px] text-neon-cyan transition-colors hover:bg-neon-cyan/25"
						>
							Save
						</button>
					</div>
				{:else if isArchived}
					<p
						class="mt-1 text-xs text-text-secondary/70"
						data-testid="project-description"
					>
						{project.description || "No description"}
					</p>
				{:else}
					<button
						type="button"
						class="mt-1 block cursor-pointer text-left text-xs text-text-secondary/70 transition-colors hover:text-text-primary/80"
						onclick={() => {
							editingDescription = true;
							descInput = project.description || "";
						}}
						data-testid="project-description"
					>
						{project.description || "Click to add a description..."}
					</button>
				{/if}

				<Separator class="divider-glow mt-1.5" />
				<div
					class="mt-1 flex items-center gap-2 text-[11px] text-text-dim"
				>
					<Tooltip text={formatExactTime(project.created_at)}
						><span
							>Created {formatRelativeTime(
								project.created_at,
							)}</span
						></Tooltip
					>
					<Tooltip text={formatExactTime(project.updated_at)}
						><span
							>Updated {formatRelativeTime(
								project.updated_at,
							)}</span
						></Tooltip
					>
					{#if project.status === "archived"}
						<span
							class="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider text-neon-yellow/70"
						>
							<span
								class="inline-block h-1.5 w-1.5 rounded-full bg-neon-yellow/60"
							></span>
							archived
						</span>
					{:else}
						<span
							class="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider text-neon-green/60"
						>
							<span
								class="inline-block h-1.5 w-1.5 rounded-full bg-neon-green"
							></span>
							active
						</span>
					{/if}
				</div>
			</div>

			<div class="flex shrink-0 items-center gap-1.5">
				{#if confirmDeleteProject}
					<span class="text-[11px] text-neon-red"
						>Delete project?</span
					>
					<button
						onclick={handleDeleteProject}
						class="rounded-lg bg-neon-red/15 px-2 py-0.5 text-[11px] text-neon-red transition-colors hover:bg-neon-red/25"
						data-testid="confirm-delete-project"
					>
						Confirm
					</button>
					<button
						onclick={() => {
							confirmDeleteProject = false;
						}}
						class="rounded-lg bg-bg-hover px-2 py-0.5 text-[11px] text-text-dim transition-colors hover:bg-bg-hover/80"
					>
						Cancel
					</button>
				{:else}
					<!-- Cyan group: View history + Export -->
					<div class="action-group">
						<Tooltip
							text="View forge history in sidebar"
							side="bottom"
						>
							<button
								onclick={() => {
									sidebarState.setTab("history");
									historyState.setFilterProjectId(project.id);
								}}
								class="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] text-neon-cyan/70 transition-colors hover:bg-neon-cyan/10 hover:text-neon-cyan"
								data-testid="view-history-btn"
							>
								<Icon name="clock" size={12} />
								History
							</button>
						</Tooltip>
						<Tooltip
							text="Export all forge results as Markdown"
							side="bottom"
						>
							<button
								onclick={handleExportProject}
								disabled={isExporting}
								class="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] text-neon-cyan/70 transition-colors hover:bg-neon-cyan/10 hover:text-neon-cyan disabled:opacity-40"
								data-testid="export-project-btn"
							>
								{#if isExporting}
									<Icon
										name="spinner"
										size={12}
										class="animate-spin"
									/>
									{exportProgress
										? `${exportProgress.fetched}/${exportProgress.total}`
										: "..."}
								{:else}
									<Icon name="download" size={12} />
									Export
								{/if}
							</button>
						</Tooltip>
					</div>
					<!-- Warm group: Archive/Restore + Delete -->
					<div class="action-group">
						{#if project.status === "archived"}
							<Tooltip
								text="Restore project to active"
								side="bottom"
							>
								<button
									onclick={handleArchiveToggle}
									class="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] text-neon-green/70 transition-colors hover:bg-neon-green/10 hover:text-neon-green"
									data-testid="restore-project-btn"
								>
									<Icon name="refresh" size={12} />
									Restore
								</button>
							</Tooltip>
						{:else}
							<Tooltip
								text="Archive project (read-only, keeps data)"
								side="bottom"
							>
								<button
									onclick={handleArchiveToggle}
									class="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] text-neon-yellow/70 transition-colors hover:bg-neon-yellow/10 hover:text-neon-yellow"
									data-testid="archive-project-btn"
								>
									<Icon name="archive" size={12} />
									Archive
								</button>
							</Tooltip>
						{/if}
						<Tooltip
							text="Permanently delete project and all data"
							side="bottom"
						>
							<button
								onclick={() => {
									confirmDeleteProject = true;
								}}
								class="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] text-neon-red/40 transition-colors hover:bg-neon-red/10 hover:text-neon-red"
								data-testid="delete-project-btn"
							>
								<Icon name="trash-2" size={12} />
								Delete
							</button>
						</Tooltip>
					</div>
				{/if}
			</div>
		</div>
	</div>

	{#if isArchived}
		<div
			class="mt-1.5 flex items-center gap-1.5 rounded-md border border-neon-yellow/20 bg-neon-yellow/5 px-2 py-1"
		>
			<Icon name="archive" size={14} class="text-neon-yellow" />
			<span class="text-xs text-neon-yellow"
				>This project is archived and read-only.</span
			>
		</div>
	{/if}

	<!-- Context Profile Section -->
	<Collapsible.Root bind:open={showContextProfile} class="mt-3">
		<Collapsible.Trigger
			class="collapsible-toggle collapsible-toggle-section"
			style="--toggle-accent: var(--color-neon-green)"
		>
			Context Profile
			{#if project.context_profile && Object.keys(project.context_profile).length > 0}
				<span
					class="ml-auto text-[10px] font-mono font-normal normal-case tracking-normal text-neon-green/50"
					>configured</span
				>
			{/if}
		</Collapsible.Trigger>
		<Collapsible.Content>
			<div
				class="mt-1.5 rounded-md border border-border-subtle bg-bg-card/50 p-2.5"
			>
				<ContextProfileEditor
					value={project.context_profile ?? {}}
					onsave={handleSaveContext}
					readonly={isArchived}
				/>
			</div>
		</Collapsible.Content>
	</Collapsible.Root>

	<!-- Prompts section -->
	<div class="mt-3">
		<div class="mb-1 flex items-center justify-between px-1">
			<h2 class="section-heading-dim">
				{#if hasActiveFilters}
					Prompts ({filteredPrompts.length}/{project.prompts.length})
				{:else}
					Prompts ({project.prompts.length})
				{/if}
			</h2>
			{#if !isArchived}
				<Tooltip text="Add a new prompt card" side="bottom">
					<button
						onclick={() => {
							showAddPrompt = !showAddPrompt;
						}}
						class="inline-flex items-center gap-1 rounded-lg border border-neon-cyan/20 px-2 py-0.5 text-[11px] text-neon-cyan transition-colors hover:bg-neon-cyan/8"
						data-testid="add-prompt-btn"
					>
						<Icon name="plus" size={12} />
						Add Prompt
					</button>
				</Tooltip>
			{/if}
		</div>

		<!-- Metadata filter bar -->
		{#if hasAnyMetadata}
			{@const allTags = [...allMetadata.tags]}
			{@const visibleTags = showAllFilterTags
				? allTags
				: allTags.slice(0, MAX_VISIBLE_FILTER_TAGS)}
			{@const hiddenTagCount = allTags.length - MAX_VISIBLE_FILTER_TAGS}
			<div class="filter-bar relative mb-1.5" data-testid="filter-bar">
				{#if hasActiveFilters}
					<button
						onclick={clearAllFilters}
						class="absolute right-1.5 top-1 z-10 rounded-full border border-border-subtle bg-bg-hover px-2 py-px text-[10px] text-text-dim transition-colors hover:bg-bg-hover/80 hover:text-text-secondary"
						data-testid="clear-filters"
					>
						Clear
					</button>
				{/if}
				<div class="flex flex-col gap-0.5">
					<!-- Task type row -->
					{#if allMetadata.task_types.size > 0}
						<div
							class="filter-row animate-stagger-fade-in flex items-baseline gap-2"
							style="--filter-accent: var(--color-neon-cyan); animation-delay: 0ms"
							data-testid="filter-row-type"
						>
							<span
								class="filter-label w-[46px] shrink-0 select-none"
								>Type</span
							>
							<div class="flex flex-wrap items-center gap-1">
								{#each [...allMetadata.task_types] as tt}
									{@const active = isFilterActive(
										"task_type",
										tt,
									)}
									<button
										onclick={() =>
											toggleFilter("task_type", tt)}
										class="transition-all active:scale-95 {active
											? ''
											: 'opacity-50 hover:opacity-100'}"
										data-testid="filter-task-type"
									>
										<MetaBadge
											type="task"
											value={tt}
											variant={active ? "solid" : "pill"}
											size="xs"
											showTooltip={false}
										/>
									</button>
								{/each}
							</div>
						</div>
					{/if}
					<!-- Complexity row -->
					{#if allMetadata.complexities.size > 0}
						<div
							class="filter-row animate-stagger-fade-in flex items-baseline gap-2"
							style="--filter-accent: var(--color-neon-yellow); animation-delay: 40ms"
							data-testid="filter-row-level"
						>
							<span
								class="filter-label w-[46px] shrink-0 select-none"
								>Level</span
							>
							<div class="flex flex-wrap items-center gap-1">
								{#each [...allMetadata.complexities] as cx}
									{@const active = isFilterActive(
										"complexity",
										cx,
									)}
									<button
										onclick={() =>
											toggleFilter("complexity", cx)}
										class="transition-all active:scale-95 {active
											? ''
											: 'opacity-50 hover:opacity-100'}"
										data-testid="filter-complexity"
									>
										<MetaBadge
											type="complexity"
											value={cx}
											variant={active ? "solid" : "pill"}
											size="xs"
											showTooltip={false}
										/>
									</button>
								{/each}
							</div>
						</div>
					{/if}
					<!-- Framework/strategy row -->
					{#if allMetadata.frameworks.size > 0}
						<div
							class="filter-row animate-stagger-fade-in flex items-baseline gap-2"
							style="--filter-accent: var(--color-neon-purple); animation-delay: 80ms"
							data-testid="filter-row-strategy"
						>
							<span
								class="filter-label w-[46px] shrink-0 select-none"
								>Strategy</span
							>
							<div class="flex flex-wrap items-center gap-1">
								{#each [...allMetadata.frameworks] as fw}
									{@const active = isFilterActive(
										"framework",
										fw,
									)}
									<button
										onclick={() =>
											toggleFilter("framework", fw)}
										class="transition-all active:scale-95 {active
											? ''
											: 'opacity-50 hover:opacity-100'}"
										data-testid="filter-framework"
									>
										<MetaBadge
											type="strategy"
											value={fw}
											variant={active ? "solid" : "pill"}
											size="xs"
											showTooltip={false}
										/>
									</button>
								{/each}
							</div>
						</div>
					{/if}
					<!-- Tags row (collapsible) -->
					{#if allTags.length > 0}
						<div
							class="filter-row animate-stagger-fade-in flex items-baseline gap-2"
							style="--filter-accent: var(--color-neon-green); animation-delay: 120ms"
							data-testid="filter-row-tags"
						>
							<span
								class="filter-label w-[46px] shrink-0 select-none"
								>Tags</span
							>
							<div class="flex flex-wrap items-center gap-1">
								{#each visibleTags as tag}
									{@const active = isFilterActive("tag", tag)}
									<button
										onclick={() => toggleFilter("tag", tag)}
										class="transition-all active:scale-95 {active
											? ''
											: 'opacity-50 hover:opacity-100'}"
										data-testid="filter-tag"
									>
										<MetaBadge
											type="tag"
											value={tag}
											variant={active ? "solid" : "pill"}
											size="xs"
											showTooltip={false}
										/>
									</button>
								{/each}
								{#if hiddenTagCount > 0}
									<button
										onclick={() => {
											showAllFilterTags =
												!showAllFilterTags;
										}}
										class="text-[11px] text-text-dim transition-colors hover:text-text-secondary"
										data-testid="toggle-filter-tags"
									>
										{showAllFilterTags
											? "Show less"
											: `+${hiddenTagCount} more`}
									</button>
								{/if}
							</div>
						</div>
					{/if}
				</div>
			</div>
		{/if}

		{#if showAddPrompt && !isArchived}
			<div
				class="animate-fade-in mb-1.5 rounded-md border border-neon-cyan/15 bg-bg-card/50 p-2"
				data-testid="add-prompt-form"
			>
				<textarea
					bind:value={newPromptContent}
					placeholder="Enter prompt content..."
					rows="3"
					class="input-field w-full resize-y rounded-lg py-2 text-[13px]"
					data-testid="new-prompt-textarea"
				></textarea>
				<div class="mt-2 flex gap-2">
					<button
						onclick={handleAddPrompt}
						disabled={!newPromptContent.trim() || isAddingPrompt}
						class="rounded-lg bg-neon-cyan/15 px-2 py-0.5 text-[11px] font-medium text-neon-cyan transition-colors hover:bg-neon-cyan/25 disabled:opacity-40"
						data-testid="save-new-prompt"
					>
						{isAddingPrompt ? "Adding..." : "Add"}
					</button>
					<button
						onclick={() => {
							showAddPrompt = false;
							newPromptContent = "";
						}}
						class="rounded-lg bg-bg-hover px-2 py-0.5 text-[11px] text-text-dim transition-colors hover:bg-bg-hover/80"
					>
						Cancel
					</button>
				</div>
			</div>
		{/if}

		{#if project.prompts.length === 0 && !showAddPrompt}
			<div
				class="flex flex-col items-center justify-center rounded-md border border-border-subtle bg-bg-card/50 px-3 py-6 text-center"
				data-testid="prompts-empty"
			>
				<div
					class="mb-1.5 flex h-8 w-8 items-center justify-center rounded-full bg-bg-hover/60"
				>
					<Icon name="edit" size={24} class="text-text-dim/40" />
				</div>
				<p class="text-sm text-text-dim">No prompts yet</p>
				<p class="mt-1 text-[11px] text-text-dim/60">
					{isArchived
						? "This archived project has no prompts"
						: "Add prompts to this project to start optimizing"}
				</p>
			</div>
		{:else if filteredPrompts.length === 0 && hasActiveFilters}
			<div
				class="flex flex-col items-center justify-center rounded-md border border-border-subtle bg-bg-card/50 px-3 py-3 text-center"
				data-testid="prompts-empty-filtered"
			>
				<div
					class="mb-1.5 flex h-8 w-8 items-center justify-center rounded-full bg-bg-hover/60"
				>
					<Icon name="search" size={16} class="text-text-dim/40" />
				</div>
				<p class="text-xs text-text-dim">
					No prompts match the active filters
				</p>
				<button
					onclick={clearAllFilters}
					class="mt-1.5 rounded-lg bg-neon-cyan/10 px-2.5 py-0.5 text-[11px] text-neon-cyan transition-colors hover:bg-neon-cyan/20"
				>
					Clear filters
				</button>
			</div>
		{:else}
			<div class="space-y-1.5">
				{#each filteredPrompts as prompt, index (prompt.id)}
					{@const timeline = getForgeTimeline(prompt)}
					{@const activeForge = getActiveForge(prompt, timeline)}
					<!-- svelte-ignore a11y_click_events_have_key_events -->
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<div
						class="prompt-card card-top-glow group animate-stagger-fade-in {activeForge
							? 'cursor-pointer'
							: ''}"
						style="animation-delay: {index * 60}ms"
						onclick={(e) => {
							if (activeForge) handleCardClick(e, activeForge.id);
						}}
						data-testid="prompt-card"
					>
						<!-- Title row with score (reads from activeForge) -->
						{#if activeForge}
							<div class="mb-1 flex items-center gap-1.5">
								{#if activeForge.overall_score != null}
									<Tooltip
										text="Overall quality score"
										class="shrink-0"
									>
										<span
											class="score-circle score-circle-sm {getScoreBadgeClass(
												activeForge.overall_score,
											)}"
											data-testid="prompt-score"
										>
											{normalizeScore(
												activeForge.overall_score,
											)}
										</span>
									</Tooltip>
								{/if}
								<span
									class="truncate text-sm font-semibold text-text-primary font-display"
									data-testid="prompt-title"
								>
									{getPromptTitle(prompt, activeForge)}
								</span>
							</div>
						{/if}

						{#if editingPromptId === prompt.id && !isArchived}
							<textarea
								bind:value={editPromptContent}
								onkeydown={(e) => {
									if (e.key === "Escape") {
										editingPromptId = null;
									}
								}}
								rows="4"
								class="input-field w-full resize-y py-2 text-sm"
								data-testid="edit-prompt-textarea"
							></textarea>
							<div class="mt-1.5 flex gap-2">
								<button
									onclick={savePromptEdit}
									class="rounded-lg bg-neon-cyan/15 px-2 py-0.5 text-[11px] text-neon-cyan transition-colors hover:bg-neon-cyan/25"
								>
									Save
								</button>
								<button
									onclick={() => {
										editingPromptId = null;
									}}
									class="rounded-lg bg-bg-hover px-2 py-0.5 text-[11px] text-text-dim transition-colors hover:bg-bg-hover/80"
								>
									Cancel
								</button>
							</div>
						{:else}
							<div class="prompt-content-well">
								<button
									type="button"
									onclick={() => {
										expandedPromptText =
											expandedPromptText === prompt.id
												? null
												: prompt.id;
									}}
									aria-expanded={expandedPromptText ===
										prompt.id}
									class="w-full whitespace-pre-wrap text-left text-[12px] leading-normal text-text-secondary transition-colors hover:text-text-primary {expandedPromptText ===
									prompt.id
										? ''
										: 'line-clamp-2'}"
									data-testid="prompt-content"
								>
									{prompt.content}
								</button>
							</div>
						{/if}

						<!-- Metadata summary (reads from activeForge) -->
						{#if activeForge}
							{@const forgeMeta = formatMetadataSummary({
								taskType: activeForge.task_type,
								framework: activeForge.framework_applied,
							})}
							{#if forgeMeta.length > 0 || activeForge.complexity || activeForge.tags.length > 0}
								<div
									class="mt-1 flex items-center gap-1.5 overflow-hidden"
									data-testid="prompt-metadata"
								>
									{#if forgeMeta.length > 0 || activeForge.complexity}
										<MetadataSummaryLine
											segments={forgeMeta}
											complexity={activeForge.complexity}
											size="sm"
											identityColor={getTaskTypeColor(
												activeForge.task_type,
											).cssColor}
										/>
									{/if}
									{#if activeForge.is_improvement === true}
										<Tooltip text="Improved over original"
											><Icon
												name="arrow-up"
												size={12}
												class="text-neon-green"
											/></Tooltip
										>
									{/if}
									{#if activeForge.tags.length > 0}
										{#if forgeMeta.length > 0 || activeForge.complexity}
											<span class="metadata-separator"
											></span>
										{/if}
										{#each activeForge.tags.slice(0, 2) as tag}
											<MetaBadge
												type="tag"
												value={tag}
												variant="pill"
												size="xs"
												showTooltip={false}
											/>
										{/each}
										{#if activeForge.tags.length > 2}
											<Tooltip
												text={activeForge.tags
													.slice(2)
													.join(", ")}
											>
												<span
													class="text-[11px] text-text-dim"
													>+{activeForge.tags.length -
														2}</span
												>
											</Tooltip>
										{/if}
									{/if}
								</div>
							{/if}
						{/if}

						<!-- Iteration selector (gated by badge toggle) -->
						{#if prompt.forge_count > 1 && (expandedIterations[prompt.id] ?? false)}
							<div
								class="mt-2"
								data-no-navigate
								data-testid="forge-iterations"
							>
								{#if !forgeData[prompt.id]?.loaded}
									<!-- Loading state: show spinner while forge data arrives -->
									<div class="flex items-center gap-2">
										<span
											class="text-[11px] font-semibold uppercase tracking-wide text-text-dim"
											>Iterations</span
										>
										<Icon
											name="spinner"
											size={12}
											class="animate-spin text-text-dim/40"
										/>
									</div>
								{:else if timeline.length > 1}
									<div class="flex items-center gap-2 mb-1">
										<span
											class="text-[11px] font-semibold uppercase tracking-wide text-text-dim"
											>Iterations ({timeline.length})</span
										>
									</div>
									<div class="flex flex-col gap-1">
										{#each timeline as forge, i (forge.id)}
											{@const isSelected =
												activeForge?.id === forge.id}
											{@const isConfirmingDelete =
												confirmDeleteForgeId ===
												forge.id}
											{@const isDeleting =
												deletingForgeId === forge.id}
											<div
												class="group/iter relative flex items-center gap-0.5"
											>
												<button
													onclick={() =>
														selectForge(
															prompt.id,
															forge.id,
														)}
													class="iteration-timeline-item flex min-w-0 flex-1 items-center gap-2 text-left text-[11px]
																{isSelected
														? 'iteration-timeline-item--active text-text-primary'
														: 'text-text-secondary'}"
													data-testid="forge-iteration"
												>
													{#if forge.overall_score != null}
														<Tooltip
															text="Overall score"
															><span
																class="score-circle score-circle-sm shrink-0 {getScoreBadgeClass(
																	forge.overall_score,
																)}"
															>
																{normalizeScore(
																	forge.overall_score,
																)}
															</span></Tooltip
														>
													{:else}
														<span
															class="score-circle score-circle-sm shrink-0 bg-bg-hover text-text-dim"
															>-</span
														>
													{/if}
													<span class="truncate">
														{forge.title ??
															forge.framework_applied ??
															`Forge #${timeline.length - i}`}
													</span>
													{#if isSelected}
														<Icon
															name="chevron-right"
															size={10}
															class="ml-auto shrink-0 text-neon-cyan/60"
														/>
													{/if}
												</button>
												{#if !isArchived}
													{#if isDeleting}
														<span
															class="shrink-0 p-1"
														>
															<Icon
																name="spinner"
																size={12}
																class="animate-spin text-text-dim"
															/>
														</span>
													{:else if isConfirmingDelete}
														<button
															onclick={() =>
																handleDeleteForge(
																	prompt.id,
																	forge.id,
																)}
															class="shrink-0 rounded p-1 text-neon-green transition-colors hover:bg-neon-green/10"
															aria-label="Confirm delete iteration"
															data-testid="confirm-delete-forge"
														>
															<Icon
																name="check"
																size={12}
															/>
														</button>
														<button
															onclick={() => {
																confirmDeleteForgeId =
																	null;
															}}
															class="shrink-0 rounded p-1 text-text-dim transition-colors hover:bg-bg-hover"
															aria-label="Cancel delete iteration"
														>
															<Icon
																name="x"
																size={12}
															/>
														</button>
													{:else}
														<Tooltip
															text="Delete this iteration"
															side="left"
														>
															<button
																onclick={() => {
																	confirmDeleteForgeId =
																		forge.id;
																}}
																class="shrink-0 rounded p-1 text-text-dim opacity-0 transition-all hover:text-neon-red group-hover/iter:opacity-100"
																aria-label="Delete iteration"
																data-testid="delete-forge-btn"
															>
																<Icon
																	name="x"
																	size={12}
																/>
															</button>
														</Tooltip>
													{/if}
												{/if}
											</div>
										{/each}
									</div>
								{/if}
							</div>
						{/if}

						<!-- Footer: lifecycle badge + timestamp + actions -->
						<Separator class="divider-glow mt-1.5" />
						<div class="mt-1.5 flex items-center gap-1.5">
							{#if prompt.forge_count === 0}
								<Tooltip text="Not yet optimized">
									<span
										class="inline-flex items-center gap-1.5 rounded-full bg-bg-hover/60 text-[11px] text-text-dim/50"
										data-testid="prompt-lifecycle-badge"
									>
										new
									</span>
								</Tooltip>
							{:else}
								{@const badgeVersion =
									activeForge?.version ??
									prompt.latest_forge?.version ??
									`v${prompt.forge_count}`}
								{#if prompt.forge_count === 1}
									<Tooltip text="Forged — click to view">
										<button
											onclick={() => {
												if (activeForge)
													goto(
														"/optimize/" +
															activeForge.id,
													);
											}}
											class="{getVersionBadgeClass(
												false,
											)} text-[11px]"
											data-testid="prompt-lifecycle-badge"
										>
											<Icon name="bolt" size={10} />
											{badgeVersion}
										</button>
									</Tooltip>
								{:else}
									{@const iterExpanded =
										expandedIterations[prompt.id] ?? false}
									<Tooltip
										text="Forged {prompt.forge_count} times — click to expand iterations"
									>
										<button
											onclick={() => {
												expandedIterations = {
													...expandedIterations,
													[prompt.id]: !iterExpanded,
												};
											}}
											class="{getVersionBadgeClass(
												iterExpanded,
											)} text-[11px]"
											data-testid="prompt-lifecycle-badge"
										>
											<Icon name="bolt" size={10} />
											{badgeVersion}
											<Icon
												name={iterExpanded
													? "chevron-down"
													: "chevron-right"}
												size={10}
												class="transition-all duration-200"
											/>
										</button>
									</Tooltip>
								{/if}
							{/if}
							<Tooltip text={formatExactTime(prompt.updated_at)}
								><span class="text-[11px] text-text-dim"
									>{formatRelativeTime(
										prompt.updated_at,
									)}</span
								></Tooltip
							>
							{#if editingPromptId !== prompt.id && !isArchived}
								<div class="ml-auto flex items-center gap-1.5">
									<!-- Optimize stands alone (primary action) -->
									<Tooltip
										text="Start new optimization with this prompt"
										side="bottom"
									>
										<button
											onclick={() =>
												optimizePrompt(prompt)}
											class="inline-flex items-center gap-1 rounded-lg bg-neon-cyan/10 px-2 py-0.5 text-[11px] font-medium text-neon-cyan transition-all hover:bg-neon-cyan/18"
											data-testid="optimize-prompt-btn"
										>
											<Icon name="bolt" size={12} />
											Optimize
										</button>
									</Tooltip>
									<!-- Grouped: Re-iterate + Edit + Version -->
									<div class="action-group">
										{#if prompt.forge_count > 0}
											<Tooltip
												text="Re-optimize using latest result as input"
												side="bottom"
											>
												<button
													onclick={() =>
														reiteratePrompt(prompt)}
													class="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] text-neon-purple transition-colors hover:bg-neon-purple/12"
													data-testid="reiterate-prompt-btn"
												>
													<Icon
														name="refresh"
														size={11}
													/>
													Re-iterate
												</button>
											</Tooltip>
										{/if}
										<Tooltip
											text="Edit prompt content"
											side="bottom"
										>
											<button
												onclick={() =>
													startEditPrompt(prompt)}
												class="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
												aria-label="Edit prompt"
												data-testid="edit-prompt-btn"
											>
												<Icon name="edit" size={11} />
												Edit
											</button>
										</Tooltip>
										{#if prompt.version > 1}
											<Tooltip
												text="View content edit history"
												side="bottom"
											>
												<button
													onclick={() =>
														toggleContentHistory(
															prompt.id,
														)}
													class="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] text-neon-purple transition-colors hover:bg-neon-purple/12"
													data-testid="version-history-btn"
												>
													<Icon
														name="clock"
														size={11}
													/>
													v{prompt.version}
												</button>
											</Tooltip>
										{/if}
									</div>
									<!-- Delete: icon-only, very dim -->
									<Tooltip
										text="Delete prompt card"
										side="top"
									>
										<button
											onclick={() => {
												deletePromptModalId = prompt.id;
											}}
											class="rounded-lg p-1 text-text-dim/30 transition-colors hover:bg-neon-red/10 hover:text-neon-red"
											aria-label="Delete prompt card"
											data-testid="delete-prompt-btn"
										>
											<Icon name="trash-2" size={11} />
										</button>
									</Tooltip>
								</div>
							{/if}
						</div>

						<!-- Version history panel (only for v2+) -->
						{#if expandedContentHistory === prompt.id && prompt.version > 1}
							<div
								class="animate-fade-in mt-2 version-panel"
								data-testid="versions-panel"
							>
								{#if versionData[prompt.id]?.loading}
									<div class="flex items-center gap-2 py-2">
										<Icon
											name="spinner"
											size={14}
											class="animate-spin text-neon-purple/60"
										/>
										<span class="text-xs text-text-dim"
											>Loading versions...</span
										>
									</div>
								{:else if !versionData[prompt.id]?.items.length}
									<p class="text-xs text-text-dim">
										No snapshots yet — edits before
										versioning was deployed aren't captured
									</p>
								{:else}
									<div class="space-y-1.5">
										{#each versionData[prompt.id].items as ver}
											<div class="version-panel-entry">
												<div
													class="flex items-center gap-2"
												>
													<span
														class="rounded-full bg-neon-purple/10 text-neon-purple text-[10px] px-1.5 py-0.5"
														>v{ver.version}</span
													>
													<span
														class="text-[11px] text-text-dim"
														>{formatRelativeTime(
															ver.created_at,
														)}</span
													>
													{#if ver.optimization_id}
														<a
															href="/optimize/{ver.optimization_id}"
															class="text-[11px] text-neon-cyan/70 transition-colors hover:text-neon-cyan"
														>
															via forge
														</a>
													{/if}
												</div>
												<p
													class="mt-1.5 line-clamp-3 text-xs leading-relaxed text-text-secondary"
												>
													{ver.content}
												</p>
											</div>
										{/each}
									</div>
								{/if}
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>

<!-- Delete prompt card confirmation modal -->
{#if deletePromptModalId}
	{@const deletePrompt = project.prompts.find(
		(p) => p.id === deletePromptModalId,
	)}
	<ConfirmModal
		open={true}
		title="Delete prompt card"
		message={deletePrompt
			? `This will permanently delete this prompt and ${deletePrompt.forge_count > 0 ? `all ${deletePrompt.forge_count} forge iteration${deletePrompt.forge_count === 1 ? "" : "s"}` : "its data"}. This action cannot be undone.`
			: ""}
		confirmLabel="Delete"
		variant="danger"
		onconfirm={() => {
			if (deletePromptModalId) handleDeletePrompt(deletePromptModalId);
		}}
		oncancel={() => {
			deletePromptModalId = null;
		}}
	/>
{/if}
