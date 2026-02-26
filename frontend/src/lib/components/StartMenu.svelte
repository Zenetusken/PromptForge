<script lang="ts">
	import { fly } from 'svelte/transition';
	import Icon from './Icon.svelte';
	import CreateProjectDialog from './CreateProjectDialog.svelte';
	import { Tooltip } from './ui';
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import { historyState } from '$lib/stores/history.svelte';
	import { projectsState } from '$lib/stores/projects.svelte';
	import { forgeSession, createEmptyDraft } from '$lib/stores/forgeSession.svelte';
	import { forgeMachine } from '$lib/stores/forgeMachine.svelte';
	import { optimizationState } from '$lib/stores/optimization.svelte';
	import { saveActiveTabState, restoreTabState } from '$lib/stores/tabCoherence';

	import { normalizeScore, getScoreBadgeClass } from '$lib/utils/format';
	import { onMount, tick } from 'svelte';

	let menuEl: HTMLDivElement | undefined = $state();
	let projectSearch = $state('');
	let showCreateProject = $state(false);
	let projectSearchInput: HTMLInputElement | undefined = $state();

	// Ensure data is loaded
	onMount(() => {
		if (!historyState.hasLoaded) historyState.loadHistory();
		if (!projectsState.allItemsLoaded) projectsState.loadAllProjects();
	});

	let recentForges = $derived(historyState.items.slice(0, 5));

	let filteredProjects = $derived.by(() => {
		const all = projectsState.allItems.filter((p) => p.status === 'active');
		if (!projectSearch.trim()) return all.slice(0, 10);
		const q = projectSearch.toLowerCase();
		return all.filter((p) => p.name.toLowerCase().includes(q)).slice(0, 10);
	});



	function close() {
		windowManager.closeStartMenu();
	}

	function handleNewForge() {
		close();
		if (forgeMachine.mode === 'forging') return;
		saveActiveTabState();
		forgeMachine.restore();
		const tab = {
			id: crypto.randomUUID(),
			name: 'Untitled',
			draft: createEmptyDraft(),
			resultId: null as string | null,
			mode: 'compose' as const,
		};
		forgeSession.tabs.push(tab);
		forgeSession.activeTabId = tab.id;
		restoreTabState(tab);
		forgeSession.activate();
		windowManager.openIDE();
		forgeSession.focusTextarea();
	}

	function handleNewProject() {
		showCreateProject = true;
	}

	function handleOpenIDE() {
		close();
		forgeMachine.restore();
		forgeSession.activate();
		windowManager.openIDE();
	}

	function handleForgeClick(id: string) {
		close();
		optimizationState.openInIDEFromHistory(id);
	}

	function handleProjectClick(id: string) {
		close();
		projectsState.navigateToProject(id);
		windowManager.openProjectsWindow();
	}

	function handleClickOutside(e: MouseEvent) {
		if (menuEl && !menuEl.contains(e.target as Node)) {
			// Check if click was on the start button
			const startBtn = document.querySelector('[data-testid="start-button"]');
			if (startBtn && startBtn.contains(e.target as Node)) return;
			close();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.preventDefault();
			close();
		}
	}

	$effect(() => {
		if (windowManager.startMenuOpen) {
			showCreateProject = false;
			// Defer listener registration so the opening click fully propagates
			// before the outside-click handler starts listening.
			const frame = requestAnimationFrame(() => {
				document.addEventListener('click', handleClickOutside);
				document.addEventListener('keydown', handleKeydown);
			});
			return () => {
				cancelAnimationFrame(frame);
				document.removeEventListener('click', handleClickOutside);
				document.removeEventListener('keydown', handleKeydown);
			};
		}
	});

	// Auto-focus project search when opened to projects section
	$effect(() => {
		if (windowManager.startMenuOpen && windowManager.startMenuSection === 'projects') {
			tick().then(() => projectSearchInput?.focus());
		}
	});

	let highlightHistory = $derived(windowManager.startMenuSection === 'history');
	let highlightProjects = $derived(windowManager.startMenuSection === 'projects');
</script>

{#if windowManager.startMenuOpen}
	<div
		bind:this={menuEl}
		class="start-menu"
		transition:fly={{ y: 12, duration: 180 }}
		role="menu"
		data-testid="start-menu"
	>
		<!-- Header -->
		<div class="flex items-center justify-between px-4 pt-3 pb-2">
			<div>
				<h2 class="text-[13px] font-bold text-text-primary tracking-wide font-display">PROMPTFORGE</h2>
			</div>
			<button class="wc-btn wc-close" onclick={close} aria-label="Close menu">
				<Icon name="x" size={12} />
			</button>
		</div>

		<div class="h-px bg-gradient-to-r from-transparent via-border-glow to-transparent mx-3"></div>

		<!-- Quick actions -->
		<div class="flex items-center gap-2 px-4 py-2.5">
			<button
				class="flex-1 flex items-center justify-center gap-1.5 rounded border border-neon-cyan/20 bg-neon-cyan/5 px-3 py-1.5 text-[11px] font-medium text-neon-cyan transition-colors hover:bg-neon-cyan/10 hover:border-neon-cyan/30"
				onclick={handleNewForge}
			>
				<Icon name="plus" size={12} />
				New Forge
			</button>
			<button
				class="flex-1 flex items-center justify-center gap-1.5 rounded border border-neon-purple/20 bg-neon-purple/5 px-3 py-1.5 text-[11px] font-medium text-neon-purple transition-colors hover:bg-neon-purple/10 hover:border-neon-purple/30"
				onclick={handleNewProject}
			>
				<Icon name="folder" size={12} />
				New Project
			</button>
		</div>

		<!-- Two columns: pinned+recent / projects -->
		<div class="flex min-h-0 max-h-[calc(70vh-120px)]">
			<!-- Left column: Pinned + Recent -->
			<div class="w-1/2 border-r border-border-subtle overflow-y-auto {highlightHistory ? 'ring-1 ring-inset ring-neon-blue/20' : ''} transition-shadow">
				<!-- Pinned items -->
				<div class="px-3 pt-2 pb-1">
					<p class="section-heading-dim text-[9px] mb-1.5">Pinned</p>
					<div class="space-y-0.5">
						<button
							class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-[11px] text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
							onclick={handleOpenIDE}
						>
							<Icon name="terminal" size={13} class="text-neon-cyan" />
							Forge IDE
						</button>
						<button
							class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-[11px] text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
							onclick={() => { windowManager.openWorkspaceHub(); close(); }}
						>
							<Icon name="git-branch" size={13} class="text-neon-green" />
							Workspace Hub
						</button>
						<a
							href={import.meta.env.VITE_API_URL ? `${import.meta.env.VITE_API_URL}/docs` : '/docs'}
							target="_blank"
							rel="noopener noreferrer"
							class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-[11px] text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary no-underline"
							onclick={close}
						>
							<Icon name="code" size={13} class="text-neon-blue" />
							API Docs
						</a>
					</div>
				</div>

				<!-- Recent forges -->
				{#if recentForges.length > 0}
					<div class="px-3 pt-2 pb-2">
						<p class="section-heading-dim text-[9px] mb-1.5">Recent</p>
						<div class="space-y-0.5">
							{#each recentForges as forge}
								<button
									class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left transition-colors hover:bg-bg-hover group"
									onclick={() => handleForgeClick(forge.id)}
								>
									{#if forge.overall_score}
										<span class="score-circle text-[8px] w-[16px] h-[16px] {getScoreBadgeClass(forge.overall_score)}">
											{normalizeScore(forge.overall_score)}
										</span>
									{:else}
										<span class="h-[16px] w-[16px] flex items-center justify-center">
											<Icon name="circle" size={8} class="text-text-dim" />
										</span>
									{/if}
									<span class="truncate text-[11px] text-text-secondary group-hover:text-text-primary">
										{forge.title || forge.raw_prompt.slice(0, 40)}
									</span>
								</button>
							{/each}
						</div>
					</div>
				{/if}
			</div>

			<!-- Right column: Projects -->
			<div class="w-1/2 overflow-y-auto {highlightProjects ? 'ring-1 ring-inset ring-neon-yellow/20' : ''} transition-shadow">
				<div class="px-3 pt-2 pb-2">
					<p class="section-heading-dim text-[9px] mb-1.5">Projects</p>
					<input
						bind:this={projectSearchInput}
						type="text"
						placeholder="Search..."
						class="input-field mb-1.5 text-[10px] py-1"
						bind:value={projectSearch}
					/>
					<div class="space-y-0.5">
						{#each filteredProjects as project}
							<button
								class="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left transition-colors hover:bg-bg-hover group"
								onclick={() => handleProjectClick(project.id)}
							>
								<Icon
									name={project.status === 'archived' ? 'archive' : 'folder'}
									size={13}
									class="text-neon-yellow flex-shrink-0"
								/>
								<div class="min-w-0 flex-1">
									<span class="block truncate text-[11px] text-text-secondary group-hover:text-text-primary">
										{project.name}
									</span>
									{#if project.prompt_count > 0}
										<span class="text-[9px] text-text-dim">{project.prompt_count} prompts</span>
									{/if}
								</div>
								{#if project.has_context}
									<span class="h-1.5 w-1.5 rounded-full bg-neon-green flex-shrink-0" title="Has context profile"></span>
								{/if}
							</button>
						{/each}
						{#if filteredProjects.length === 0}
							<p class="text-[10px] text-text-dim px-2 py-2">
								{projectSearch ? 'No matches' : 'No projects yet'}
							</p>
						{/if}
					</div>
				</div>
			</div>
		</div>

		{#if showCreateProject}
			<div class="border-t border-border-subtle px-1">
				<CreateProjectDialog onclose={() => { showCreateProject = false; close(); }} />
			</div>
		{/if}
	</div>
{/if}
