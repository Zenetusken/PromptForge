<script lang="ts">
	import { Collapsible } from "bits-ui";
	import { forgeSession } from "$lib/stores/forgeSession.svelte";
	import {
		ALL_STRATEGIES,
		STRATEGY_LABELS,
		STRATEGY_DESCRIPTIONS,
	} from "$lib/utils/strategies";
	import type { StrategyName } from "$lib/utils/strategies";
	import Icon from "./Icon.svelte";
	import { Tooltip, MetaBadge } from "./ui";

	const STRATEGY_CATEGORIES: Record<StrategyName, string> = {
		"co-star": "Frameworks",
		risen: "Frameworks",
		"role-task-format": "Frameworks",
		"chain-of-thought": "Techniques",
		"few-shot-scaffolding": "Techniques",
		"step-by-step": "Techniques",
		"structured-output": "Techniques",
		"constraint-injection": "Techniques",
		"context-enrichment": "Techniques",
		"persona-assignment": "Techniques",
	};

	const STRATEGY_OPTIONS: {
		value: string;
		label: string;
		description: string;
		category?: string;
	}[] = [
		{
			value: "auto",
			label: "Auto",
			description: "AI selects the best framework combination",
		},
		...ALL_STRATEGIES.map((s) => ({
			value: s,
			label: STRATEGY_LABELS[s],
			description: STRATEGY_DESCRIPTIONS[s],
			category: STRATEGY_CATEGORIES[s],
		})),
	];

	const strategyCategories = (() => {
		const ungrouped = STRATEGY_OPTIONS.filter((o) => !o.category);
		const categoryMap = new Map<string, typeof STRATEGY_OPTIONS>();
		for (const opt of STRATEGY_OPTIONS) {
			if (opt.category) {
				if (!categoryMap.has(opt.category))
					categoryMap.set(opt.category, []);
				categoryMap.get(opt.category)!.push(opt);
			}
		}
		return { ungrouped, categories: [...categoryMap.entries()] };
	})();

	function toggleSecondary(value: string) {
		const current = forgeSession.draft.secondaryStrategies;
		if (current.includes(value)) {
			forgeSession.updateDraft({
				secondaryStrategies: current.filter((v) => v !== value),
			});
		} else if (current.length < 2) {
			forgeSession.updateDraft({
				secondaryStrategies: [...current, value],
			});
		} else {
			forgeSession.updateDraft({
				secondaryStrategies: [current[1], value],
			});
		}
	}

	// Clear secondaries that match the new primary
	$effect(() => {
		if (
			forgeSession.draft.strategy !== "auto" &&
			forgeSession.draft.secondaryStrategies.includes(
				forgeSession.draft.strategy,
			)
		) {
			forgeSession.updateDraft({
				secondaryStrategies:
					forgeSession.draft.secondaryStrategies.filter(
						(v) => v !== forgeSession.draft.strategy,
					),
			});
		}
	});
</script>

<Collapsible.Root bind:open={forgeSession.showStrategy}>
	<Collapsible.Trigger
		class="collapsible-toggle"
		style="--toggle-accent: var(--color-neon-purple)"
		data-testid="advanced-toggle"
	>
		<Icon
			name="chevron-right"
			size={12}
			class="transition-transform duration-200 {forgeSession.showStrategy
				? 'rotate-90'
				: ''}"
		/>
		<Tooltip text="Override automatic strategy selection"
			><span>Strategy</span></Tooltip
		>
		{#if forgeSession.draft.strategy !== "auto"}
			<span class="collapsible-indicator bg-neon-purple"></span>
			<MetaBadge
				type="strategy"
				value={forgeSession.draft.strategy}
				variant="pill"
				size="xs"
				showTooltip={false}
			/>
			{#if forgeSession.draft.secondaryStrategies.length > 0}
				<Tooltip
					text="{forgeSession.draft.secondaryStrategies
						.length} secondary {forgeSession.draft
						.secondaryStrategies.length === 1
						? 'framework'
						: 'frameworks'} selected"
				>
					<span
						class="rounded-full border border-neon-cyan/30 bg-transparent px-1.5 py-0.5 text-[9px] font-semibold text-neon-cyan"
					>
						+{forgeSession.draft.secondaryStrategies.length}
					</span>
				</Tooltip>
			{/if}
		{/if}
	</Collapsible.Trigger>
	<Collapsible.Content>
		<div class="px-3 pt-1 pb-2" data-testid="advanced-fields">
			<!-- Ungrouped (Auto) -->
			{#each strategyCategories.ungrouped as option}
				<label
					class="mb-1.5 flex cursor-pointer items-start gap-2 rounded-sm px-2 py-1.5 transition-colors focus-within:ring-2 focus-within:ring-neon-cyan/40
						{forgeSession.draft.strategy === option.value
						? 'bg-neon-purple/10 border-l-2 border-neon-purple'
						: 'border-l-2 border-transparent hover:bg-bg-hover/40'}"
				>
					<input
						type="radio"
						name="popover-strategy"
						value={option.value}
						bind:group={forgeSession.draft.strategy}
						class="mt-0.5 accent-neon-purple"
						data-testid="strategy-option-{option.value}"
					/>
					<div class="min-w-0">
						<span
							class="text-[12px] font-medium {forgeSession.draft
								.strategy === option.value
								? 'text-neon-purple'
								: 'text-text-primary'}"
						>
							{option.label}
						</span>
						<p class="text-[11px] text-text-dim">
							{option.description}
						</p>
					</div>
				</label>
			{/each}

			<!-- Category groups -->
			{#each strategyCategories.categories as [categoryName, categoryOptions]}
				<div class="mt-2 mb-1">
					<span
						class="text-[10px] font-semibold uppercase tracking-wider text-text-dim/60"
					>
						{categoryName}
					</span>
				</div>
				<div class="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
					{#each categoryOptions as option}
						<label
							class="flex cursor-pointer items-start gap-2 rounded-sm px-2 py-1.5 transition-colors focus-within:ring-2 focus-within:ring-neon-cyan/40
								{forgeSession.draft.strategy === option.value
								? 'bg-neon-purple/10 border-l-2 border-neon-purple'
								: 'border-l-2 border-transparent hover:bg-bg-hover/40'}"
						>
							<input
								type="radio"
								name="popover-strategy"
								value={option.value}
								bind:group={forgeSession.draft.strategy}
								class="mt-0.5 accent-neon-purple"
								data-testid="strategy-option-{option.value}"
							/>
							<div class="min-w-0">
								<span
									class="text-[12px] font-medium {forgeSession
										.draft.strategy === option.value
										? 'text-neon-purple'
										: 'text-text-primary'}"
								>
									{option.label}
								</span>
								<p class="text-[11px] text-text-dim">
									{option.description}
								</p>
							</div>
						</label>
					{/each}
				</div>
			{/each}

			{#if forgeSession.draft.strategy !== "auto"}
				<div class="mt-2 border-t border-border-subtle pt-1.5">
					<p class="mb-1.5 text-[11px] text-text-dim">
						Secondary frameworks <span class="text-text-dim/50"
							>(optional, max 2)</span
						>
					</p>
					<div class="flex flex-wrap gap-1.5">
						{#each STRATEGY_OPTIONS.filter((o) => o.value !== "auto" && o.value !== forgeSession.draft.strategy) as option}
							<Tooltip text={option.description}>
								<button
									type="button"
									onclick={() =>
										toggleSecondary(option.value)}
									data-testid="secondary-{option.value}"
									class="transition-all active:scale-95 {forgeSession.draft.secondaryStrategies.includes(
										option.value,
									)
										? ''
										: 'opacity-60 hover:opacity-100'}"
								>
									<MetaBadge
										type="strategy"
										value={option.value}
										variant={forgeSession.draft.secondaryStrategies.includes(
											option.value,
										)
											? "solid"
											: "pill"}
										showTooltip={false}
									/>
								</button>
							</Tooltip>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	</Collapsible.Content>
</Collapsible.Root>

<!-- ARIA live region for strategy changes -->
<div class="sr-only" role="status" aria-live="polite">
	{#if forgeSession.draft.strategy !== "auto"}
		Strategy selected: {STRATEGY_OPTIONS.find(
			(o) => o.value === forgeSession.draft.strategy,
		)?.label}
		{#if forgeSession.draft.secondaryStrategies.length > 0}
			with {forgeSession.draft.secondaryStrategies.length} secondary {forgeSession
				.draft.secondaryStrategies.length === 1
				? "framework"
				: "frameworks"}
		{/if}
	{/if}
</div>
