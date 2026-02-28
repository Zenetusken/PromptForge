<script lang="ts">
	import { Collapsible } from "bits-ui";
	import { forgeSession } from "$lib/stores/forgeSession.svelte";
	import { checkDuplicateTitle } from "$lib/api/client";
	import Icon from "./Icon.svelte";
	import { Tooltip } from "./ui";

	let { projectListId = undefined, compact = false }: { projectListId?: string; compact?: boolean } = $props();

	let duplicateCheckTimer: ReturnType<typeof setTimeout> | undefined;

	// Debounced duplicate title check
	$effect(() => {
		const currentTitle = forgeSession.draft.title;
		const currentProject = forgeSession.draft.project;
		clearTimeout(duplicateCheckTimer);
		forgeSession.duplicateTitleWarning = false;
		if (currentTitle.trim() && currentProject.trim()) {
			duplicateCheckTimer = setTimeout(async () => {
				const isDup = await checkDuplicateTitle(
					currentTitle.trim(),
					currentProject.trim(),
				);
				forgeSession.duplicateTitleWarning = isDup;
			}, 500);
		}
	});
</script>

<Collapsible.Root bind:open={forgeSession.showMetadata}>
	<Collapsible.Trigger
		class="collapsible-toggle"
		style="--toggle-accent: var(--color-neon-cyan)"
		data-testid="metadata-toggle"
	>
		<Icon
			name="chevron-right"
			size={12}
			class="transition-transform duration-200 {forgeSession.showMetadata
				? 'rotate-90'
				: ''}"
		/>
		<Tooltip text="Add title, tags, and project"
			><span>Metadata</span></Tooltip
		>
		{#if forgeSession.hasMetadata}
			<span class="collapsible-indicator bg-neon-cyan"></span>
		{/if}
	</Collapsible.Trigger>
	<Collapsible.Content>
		<div class="px-1.5 pt-0.5 pb-1" data-testid="metadata-fields">
			<div class="grid grid-cols-1 gap-1.5 {compact ? '' : 'sm:grid-cols-4'}">
				<div>
					<input
						id="meta-title"
						type="text"
						bind:value={forgeSession.draft.title}
						placeholder="Title"
						aria-label="Optimization title"
						data-testid="metadata-title"
						class="input-field w-full py-1 text-[11px] {forgeSession.validationErrors.title
							? 'border-neon-red/50'
							: ''}"
					/>
					{#if forgeSession.validationErrors.title}
						<p class="mt-0.5 text-[10px] text-neon-red">
							{forgeSession.validationErrors.title}
						</p>
					{/if}
					{#if forgeSession.duplicateTitleWarning}
						<p class="mt-0.5 text-[10px] text-neon-yellow">
							Title already exists in this project
						</p>
					{/if}
				</div>
				<div class="{compact ? '' : 'max-w-[100px]'}">
					<input
						id="meta-version"
						type="text"
						bind:value={forgeSession.draft.version}
						placeholder="Version"
						aria-label="Version"
						data-testid="metadata-version"
						class="input-field w-full py-1 text-[11px] {forgeSession.validationErrors.version
							? 'border-neon-red/50'
							: ''}"
					/>
					{#if forgeSession.validationErrors.version}
						<p class="mt-0.5 text-[10px] text-neon-red">
							{forgeSession.validationErrors.version}
						</p>
					{/if}
				</div>
				<div>
					<input
						id="meta-project"
						type="text"
						bind:value={forgeSession.draft.project}
						placeholder="Project"
						aria-label="Project name"
						data-testid="metadata-project"
						list={projectListId}
						disabled={!!forgeSession.draft.sourceAction}
						class="input-field w-full py-1 text-[11px] {forgeSession.validationErrors.project
							? 'border-neon-red/50'
							: ''} {forgeSession.draft.sourceAction
							? 'opacity-60 cursor-not-allowed'
							: ''}"
					/>
					{#if forgeSession.validationErrors.project}
						<p class="mt-0.5 text-[10px] text-neon-red">
							{forgeSession.validationErrors.project}
						</p>
					{/if}
				</div>
				<div>
					<input
						id="meta-tags"
						type="text"
						bind:value={forgeSession.draft.tags}
						placeholder="Tags (comma-separated)"
						aria-label="Tags"
						data-testid="metadata-tags"
						class="input-field w-full py-1 text-[11px] {forgeSession.validationErrors.tags
							? 'border-neon-red/50'
							: ''}"
					/>
					{#if forgeSession.validationErrors.tags}
						<p class="mt-0.5 text-[10px] text-neon-red">
							{forgeSession.validationErrors.tags}
						</p>
					{/if}
				</div>
			</div>
		</div>
	</Collapsible.Content>
</Collapsible.Root>
