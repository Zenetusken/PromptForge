<script lang="ts">
	import { onMount } from 'svelte';
	import { fetchPromptForges, type ForgeResultSummary } from '$lib/api/client';
	import { normalizeScore, getScoreBadgeClass, formatRelativeTime } from '$lib/utils/format';
	import Icon from './Icon.svelte';
	import { Tooltip } from './ui';

	let {
		currentForgeId,
		projectId,
		promptId,
	}: {
		currentForgeId: string;
		projectId: string;
		promptId: string;
	} = $props();

	let forges: ForgeResultSummary[] = $state([]);
	let loaded = $state(false);

	let currentIndex = $derived(forges.findIndex((f) => f.id === currentForgeId));
	let prevForge = $derived(currentIndex > 0 ? forges[currentIndex - 1] : null);
	let nextForge = $derived(currentIndex < forges.length - 1 ? forges[currentIndex + 1] : null);

	onMount(async () => {
		try {
			const result = await fetchPromptForges(projectId, promptId);
			forges = result.items;
		} catch {
			// Silently fail — page works fine without this
		}
		loaded = true;
	});
</script>

{#if loaded && forges.length > 1 && currentIndex >= 0}
	<div
		class="flex flex-col gap-2.5 rounded-xl border border-border-subtle/60 bg-bg-card/40 px-4 py-3"
		data-testid="forge-siblings"
	>
		<!-- Navigation row -->
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-2">
				{#if prevForge}
					<Tooltip text="Previous forge result" side="bottom">
					<a
						href="/optimize/{prevForge.id}"
						class="flex items-center gap-1 rounded-lg bg-bg-hover px-2 py-1 text-xs text-text-dim transition-colors hover:text-neon-cyan"
						data-testid="prev-forge"
					>
						<Icon name="chevron-left" size={12} />
						Prev
					</a>
					</Tooltip>
				{:else}
					<Tooltip text="No previous results">
					<span class="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-text-dim/30">
						<Icon name="chevron-left" size={12} />
						Prev
					</span>
					</Tooltip>
				{/if}

				<span class="text-xs font-medium text-text-secondary">
					Forge {currentIndex + 1} of {forges.length}
				</span>

				{#if nextForge}
					<Tooltip text="Next forge result" side="bottom">
					<a
						href="/optimize/{nextForge.id}"
						class="flex items-center gap-1 rounded-lg bg-bg-hover px-2 py-1 text-xs text-text-dim transition-colors hover:text-neon-cyan"
						data-testid="next-forge"
					>
						Next
						<Icon name="chevron-right" size={12} />
					</a>
					</Tooltip>
				{:else}
					<Tooltip text="No more results">
					<span class="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-text-dim/30">
						Next
						<Icon name="chevron-right" size={12} />
					</span>
					</Tooltip>
				{/if}
			</div>
		</div>

		<!-- Score badges row -->
		<div class="flex flex-wrap gap-1.5">
			{#each forges as forge, i (forge.id)}
				<Tooltip text="{forge.title ?? forge.framework_applied ?? `Forge ${i + 1}`} — {formatRelativeTime(forge.created_at)}">
				<a
					href="/optimize/{forge.id}"
					class="inline-flex max-w-[240px] items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] transition-all duration-150
						{forge.id === currentForgeId
							? 'ring-2 ring-neon-cyan/40 bg-bg-secondary/80 shadow-[0_0_8px_rgba(0,240,255,0.08)]'
							: 'bg-bg-secondary/40 hover:bg-bg-secondary/70'}"
					data-testid="forge-badge"
				>
					<span class="score-circle score-circle-sm shrink-0 {getScoreBadgeClass(forge.overall_score)}">
						{normalizeScore(forge.overall_score) ?? '-'}
					</span>
					{#if forge.title}
						<span class="min-w-0 truncate text-text-dim">{forge.title}</span>
					{:else if forge.framework_applied}
						<span class="min-w-0 truncate text-text-dim">{forge.framework_applied}</span>
					{/if}
				</a>
				</Tooltip>
			{/each}
		</div>
	</div>
{/if}
