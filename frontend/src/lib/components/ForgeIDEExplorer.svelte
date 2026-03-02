<script lang="ts">
	import { Collapsible } from 'bits-ui';
	import { projectsState } from '$lib/stores/projects.svelte';
	import { forgeMachine } from '$lib/stores/forgeMachine.svelte';
	import { forgeSession } from '$lib/stores/forgeSession.svelte';
	import { promptAnalysis } from '$lib/stores/promptAnalysis.svelte';
	import { SECTION_COLORS } from '$lib/utils/promptParser';
	import ForgeMetadataSection from './ForgeMetadataSection.svelte';
	import ForgeContextSection from './ForgeContextSection.svelte';
	import Icon from './Icon.svelte';
	import { Tooltip, MetaBadge } from './ui';

	let { onjumpline }: { onjumpline?: (line: number) => void } = $props();

	let isResizing = $state(false);

	function onResizeStart(e: MouseEvent) {
		e.preventDefault();
		isResizing = true;
		const startX = e.clientX;
		const startWidth = forgeMachine.explorerWidth;

		function onMove(ev: MouseEvent) {
			const delta = ev.clientX - startX;
			forgeMachine.setExplorerWidth(startWidth + delta);
		}
		function onUp() {
			isResizing = false;
			window.removeEventListener('mousemove', onMove);
			window.removeEventListener('mouseup', onUp);
		}
		window.addEventListener('mousemove', onMove);
		window.addEventListener('mouseup', onUp);
	}

	function collapseAll() {
		forgeSession.showMetadata = false;
		forgeSession.showContext = false;
		forgeSession.showOutline = false;
		forgeSession.showAnalysis = false;
	}

	let sections = $derived(promptAnalysis.sections);
	let variables = $derived(promptAnalysis.variables);
	let heuristic = $derived(promptAnalysis.heuristic);
	let strategies = $derived(promptAnalysis.recommendedStrategies);
	let hasOutlineContent = $derived(sections.length > 0 || variables.length > 0);
	let outlineCount = $derived(sections.length + (variables.length > 0 ? 1 : 0));
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="relative flex h-full shrink-0 flex-col overflow-y-auto border-r border-white/[0.06] bg-bg-secondary p-2 gap-1.5"
	style="width: {forgeMachine.explorerWidth}px"
>
	<!-- Resize handle (right edge) -->
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<div
		class="absolute inset-y-0 right-0 z-10 w-1 cursor-col-resize transition-colors {isResizing ? 'bg-neon-cyan/30' : 'hover:bg-neon-cyan/20'}"
		onmousedown={onResizeStart}
		role="separator"
		aria-orientation="vertical"
		aria-label="Resize explorer panel"
	></div>

	<div class="flex items-center justify-between">
		<div class="text-[10px] font-bold uppercase tracking-widest text-text-dim">Workspace Explorer</div>
		<Tooltip text="Collapse all sections" side="bottom">
			<button
				onclick={collapseAll}
				class="flex h-5 w-5 items-center justify-center rounded hover:bg-bg-hover text-text-dim hover:text-text-secondary transition-colors"
				aria-label="Collapse all sections"
			>
				<Icon name="minimize-2" size={12} />
			</button>
		</Tooltip>
	</div>

	<!-- Metadata (title, version, project, tags) -->
	<ForgeMetadataSection projectListId="ide-project-suggestions" compact />

	<!-- Outline (prompt sections + variables) -->
	{#if hasOutlineContent}
		<Collapsible.Root bind:open={forgeSession.showOutline}>
			<Collapsible.Trigger
				class="collapsible-toggle"
				style="--toggle-accent: var(--color-neon-yellow)"
			>
				<Icon
					name="chevron-right"
					size={12}
					class="transition-transform duration-200 {forgeSession.showOutline ? 'rotate-90' : ''}"
				/>
				<span>Outline</span>
				<span class="ml-auto rounded-sm bg-neon-yellow/10 px-1 py-px text-[9px] font-mono text-neon-yellow/70 tabular-nums">{outlineCount}</span>
			</Collapsible.Trigger>
			<Collapsible.Content>
				<div class="px-1 pt-0.5 pb-1 space-y-px">
					{#each sections as section}
						<button
							class="flex w-full items-center gap-1.5 rounded-sm px-1.5 py-0.5 text-left text-[11px] hover:bg-bg-hover transition-colors group"
							onclick={() => onjumpline?.(section.lineNumber)}
							title="{section.label} ({section.type}) — line {section.lineNumber}"
						>
							<span
								class="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
								style="background-color: var(--color-{SECTION_COLORS[section.type]})"
							></span>
							<span class="truncate text-text-secondary group-hover:text-text-primary">{section.label}</span>
							<span class="ml-auto shrink-0 font-mono text-[9px] text-text-dim/40 tabular-nums">:{section.lineNumber}</span>
						</button>
					{/each}
					{#if variables.length > 0}
						<div class="flex items-center gap-1.5 px-1.5 py-0.5 text-[10px] text-neon-teal/70">
							<span class="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-neon-teal/50"></span>
							<span>{variables.length} variable{variables.length !== 1 ? 's' : ''}</span>
						</div>
					{/if}
				</div>
			</Collapsible.Content>
		</Collapsible.Root>
	{/if}

	<!-- Analysis (heuristic task type + strategies) -->
	{#if heuristic}
		<Collapsible.Root bind:open={forgeSession.showAnalysis}>
			<Collapsible.Trigger
				class="collapsible-toggle"
				style="--toggle-accent: var(--color-neon-orange)"
			>
				<Icon
					name="chevron-right"
					size={12}
					class="transition-transform duration-200 {forgeSession.showAnalysis ? 'rotate-90' : ''}"
				/>
				<span>Analysis</span>
				{#if !forgeSession.showAnalysis}
					<span class="collapsible-indicator bg-neon-orange"></span>
				{/if}
			</Collapsible.Trigger>
			<Collapsible.Content>
				<div class="px-1 pt-0.5 pb-1 space-y-1.5">
					<!-- Task type + confidence -->
					<div class="flex items-center gap-1.5 px-1.5">
						<MetaBadge type="task" value={heuristic.taskType} size="xs" />
						<span class="font-mono text-[9px] text-text-dim tabular-nums">{Math.round(heuristic.confidence * 100)}%</span>
					</div>

					<!-- Matched keywords -->
					{#if heuristic.matchedKeywords.length > 0}
						<div class="flex flex-wrap gap-1 px-1.5">
							{#each heuristic.matchedKeywords.slice(0, 6) as kw}
								<span class="rounded-sm border border-white/[0.06] bg-bg-hover px-1 py-px text-[9px] font-mono text-text-dim">{kw}</span>
							{/each}
						</div>
					{/if}

					<!-- Recommended strategies -->
					{#if strategies.length > 0}
						<div class="px-1.5 space-y-px">
							<div class="text-[9px] font-medium uppercase tracking-wider text-text-dim/50 mb-0.5">Strategies</div>
							{#each strategies as strat}
								<div class="flex items-center gap-1.5 py-0.5 text-[10px]">
									<Icon name="zap" size={9} class="text-neon-purple/60 shrink-0" />
									<span class="truncate text-text-secondary">{strat.label}</span>
									<span class="ml-auto shrink-0 font-mono text-[9px] text-text-dim/40 tabular-nums">{Math.round(strat.compositeScore * 100)}%</span>
								</div>
							{/each}
						</div>
					{/if}
				</div>
			</Collapsible.Content>
		</Collapsible.Root>
	{/if}

	<!-- Context (stack templates, project fields) -->
	<ForgeContextSection />

	<!-- Project autocomplete datalist -->
	<datalist id="ide-project-suggestions">
		{#each projectsState.allItems as p}
			<option value={p.name}></option>
		{/each}
	</datalist>
</div>
