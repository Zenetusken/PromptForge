<script lang="ts">
	import { historyState } from "$lib/stores/history.svelte";
	import { sidebarState } from "$lib/stores/sidebar.svelte";
	import {
		formatRelativeTime,
		formatScore,
		getScoreBadgeClass,
	} from "$lib/utils/format";
	import { MetaBadge, EntryTitle } from "./ui";

	let recentItems = $derived(historyState.items.slice(0, 6));

	let gridCols = $derived(
		sidebarState.isOpen
			? "grid-cols-1 sm:grid-cols-2"
			: "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3",
	);
</script>

{#if recentItems.length > 0}
	<div class="group/forges">
		<div class="mb-1 flex items-center justify-between px-1">
			<p
				class="section-heading-dim transition-colors duration-200 group-hover/forges:text-neon-cyan"
			>
				Jump back in
			</p>
			<button
				type="button"
				onclick={() => sidebarState.openTo("history")}
				class="text-[11px] font-medium text-text-dim transition-colors duration-300 hover:text-neon-cyan"
			>
				View all &rarr;
			</button>
		</div>

		<div class="grid gap-1.5 {gridCols}">
			{#each recentItems as item, i}
				{@const isError = item.status === "error"}

				<a
					href="/optimize/{item.id}"
					class="group flex items-start gap-1.5 overflow-hidden rounded-md px-1.5 py-1 no-underline animate-fade-in glass-panel-bleed card-hover-bleed"
					style="animation-delay: {i *
						75}ms; animation-fill-mode: both;"
				>
					<span
						class="score-circle score-circle-sm shrink-0 mt-0.5 {isError
							? 'text-neon-red'
							: getScoreBadgeClass(item.overall_score)}"
					>
						{isError ? "X" : formatScore(item.overall_score)}
					</span>
					<div class="flex min-w-0 flex-1 flex-col gap-px overflow-hidden">
						<EntryTitle
							title={item.title}
							maxLength={45}
							class="block truncate text-[12px] leading-snug font-medium text-text-primary/90 group-hover:text-white transition-colors"
						/>
						<div class="flex items-center gap-1.5 overflow-hidden">
							{#if item.task_type}
								<MetaBadge
									type="task"
									value={item.task_type}
									variant="pill"
									size="xs"
									showTooltip={false}
								/>
							{/if}
							{#if item.strategy}
								<MetaBadge
									type="strategy"
									value={item.strategy}
									variant="pill"
									size="xs"
									showTooltip={false}
								/>
							{/if}
						</div>
						<span
							class="font-mono text-[9px] leading-none uppercase tracking-widest text-text-dim/50 group-hover:text-neon-cyan/60 transition-colors"
						>
							{formatRelativeTime(item.created_at)}
						</span>
					</div>
				</a>
			{/each}
		</div>
	</div>
{/if}
