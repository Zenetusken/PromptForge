<script lang="ts">
	import { Collapsible } from "bits-ui";
	import { forgeSession } from "$lib/stores/forgeSession.svelte";
	import { optimizationState } from "$lib/stores/optimization.svelte";
	import { checkDuplicateTitle } from "$lib/api/client";
	import Icon from "./Icon.svelte";
	import { Tooltip } from "./ui";

	let { projectListId = undefined, compact = false }: { projectListId?: string; compact?: boolean } = $props();

	let duplicateCheckTimer: ReturnType<typeof setTimeout> | undefined;
	let suggestedVersion: string | null = $state(null);

	// Debounced duplicate title check — re-runs when title, project, OR version change.
	$effect(() => {
		const currentTitle = forgeSession.draft.title;
		const currentProject = forgeSession.draft.project;
		const currentVersion = forgeSession.draft.version; // version is part of the uniqueness key
		clearTimeout(duplicateCheckTimer);
		forgeSession.duplicateTitleWarning = false;
		suggestedVersion = null;
		if (currentTitle.trim() && currentProject.trim()) {
			duplicateCheckTimer = setTimeout(async () => {
				// Exclude the currently-viewed result AND its retry_of ancestor so that
				// a re-forge chain with the same title+project+version doesn't self-warn.
				const excludeIds: string[] = [];
				const cur = optimizationState.result;
				if (cur?.id) excludeIds.push(cur.id);
				if (cur?.retry_of) excludeIds.push(cur.retry_of);

				const res = await checkDuplicateTitle(
					currentTitle.trim(),
					currentProject.trim(),
					excludeIds.length > 0 ? excludeIds : undefined,
					currentVersion.trim() || undefined,
				);
				forgeSession.duplicateTitleWarning = res.duplicate;
				suggestedVersion = res.suggested_version;
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
					<label for="meta-title" class="flex items-center gap-1 mb-0.5 text-[9px] font-bold uppercase tracking-wider text-text-dim/50">
						<Icon name="edit" size={9} class="text-text-dim/40" />
						Title
					</label>
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
						<p class="mt-0.5 text-[10px] text-neon-yellow flex items-center gap-1 flex-wrap">
							Title already exists in this project
							{#if suggestedVersion}
								—
								<button
									class="underline hover:text-neon-cyan transition-colors"
									onclick={() => forgeSession.updateDraft({ version: suggestedVersion! })}
								>use {suggestedVersion}</button>
							{/if}
						</p>
					{/if}
				</div>
				<div class="{compact ? '' : 'max-w-[100px]'}">
					<label for="meta-version" class="flex items-center gap-1 mb-0.5 text-[9px] font-bold uppercase tracking-wider text-text-dim/50">
						<Icon name="git-branch" size={9} class="text-text-dim/40" />
						Version
					</label>
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
					<label for="meta-project" class="flex items-center gap-1 mb-0.5 text-[9px] font-bold uppercase tracking-wider text-text-dim/50">
						<Icon name="folder" size={9} class="text-text-dim/40" />
						Project
						{#if forgeSession.draft.sourceAction}
							<span class="rounded-sm px-1 py-px text-[8px] font-medium {forgeSession.draft.sourceAction === 'optimize' ? 'text-neon-purple/70' : 'text-neon-cyan/70'}">
								{forgeSession.draft.sourceAction === 'optimize' ? 'OPT' : 'RET'}
							</span>
						{/if}
						{#if forgeSession.draft.promptId}
							<Icon name="link" size={8} class="text-neon-green/50" />
						{/if}
					</label>
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
					<label for="meta-tags" class="flex items-center gap-1 mb-0.5 text-[9px] font-bold uppercase tracking-wider text-text-dim/50">
						<Icon name="layers" size={9} class="text-text-dim/40" />
						Tags
					</label>
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
