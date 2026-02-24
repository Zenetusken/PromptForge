<script lang="ts">
	import { Select } from "bits-ui";
	import Icon from "./Icon.svelte";

	type Option = { value: string; label: string; group?: string };

	let {
		value,
		options,
		label,
		onchange,
		testid = "",
		itemContent,
	}: {
		value: string;
		options: Option[];
		label: string;
		onchange: (value: string) => void;
		testid?: string;
		itemContent?: import("svelte").Snippet<[Option]>;
	} = $props();

	let open = $state(false);
	let expandedGroups: Set<string> = $state(new Set());

	let selectedOption = $derived(options.find((o) => o.value === value));
	let selectedLabel = $derived(selectedOption?.label ?? "");

	// Ordered unique group names
	let groups = $derived.by(() => {
		const seen = new Set<string>();
		const result: string[] = [];
		for (const opt of options) {
			if (opt.group && !seen.has(opt.group)) {
				seen.add(opt.group);
				result.push(opt.group);
			}
		}
		return result;
	});

	let hasGroups = $derived(groups.length > 0);

	// Items per group
	let groupCounts = $derived.by(() => {
		const counts: Record<string, number> = {};
		for (const opt of options) {
			if (opt.group) counts[opt.group] = (counts[opt.group] || 0) + 1;
		}
		return counts;
	});

	// Precomputed option partitions — avoids inline .filter() in template on every render
	let ungroupedOptions = $derived(options.filter((o) => !o.group));
	let groupedItems = $derived.by(() => {
		const map: Record<string, Option[]> = {};
		for (const opt of options) {
			if (opt.group) (map[opt.group] ??= []).push(opt);
		}
		return map;
	});

	function toggleGroup(group: string, e: MouseEvent) {
		e.preventDefault();
		e.stopPropagation();
		const next = new Set(expandedGroups);
		if (next.has(group)) {
			next.delete(group);
		} else {
			next.add(group);
		}
		expandedGroups = next;
	}

	// Auto-expand the group containing the current selection when opening
	function handleOpenChange(isOpen: boolean) {
		open = isOpen;
		// Reuse the already-derived selectedOption instead of calling options.find() again
		if (
			isOpen &&
			hasGroups &&
			selectedOption?.group &&
			!expandedGroups.has(selectedOption.group)
		) {
			expandedGroups = new Set([...expandedGroups, selectedOption.group]);
		}
	}
</script>

<div class="relative flex-1" data-testid={testid}>
	<Select.Root
		type="single"
		{value}
		onValueChange={(v) => {
			if (v !== undefined) onchange(v);
		}}
		{open}
		onOpenChange={handleOpenChange}
	>
		<Select.Trigger
			class="select-field w-full text-left"
			aria-label={label}
		>
			{#if itemContent && selectedOption}
				{@render itemContent(selectedOption)}
			{:else}
				{selectedLabel}
			{/if}
		</Select.Trigger>

		<Select.Portal>
			<Select.Content
				class="mt-1 border-t border-t-neon-cyan/8 shadow-xl shadow-black/50"
				sideOffset={4}
				side="bottom"
				align="start"
			>
				{#if !hasGroups}
					{#each options as opt (opt.value)}
						<Select.Item value={opt.value} label={opt.label}>
							{opt.label}
						</Select.Item>
					{/each}
				{:else}
					<!-- Ungrouped options first -->
					{#each ungroupedOptions as opt (opt.value)}
						<Select.Item value={opt.value} label={opt.label}>
							{opt.label}
						</Select.Item>
					{/each}
					<!-- Grouped options -->
					{#each groups as group}
						{@const expanded = expandedGroups.has(group)}
						<Select.Group>
							<!-- svelte-ignore a11y_no_static_element_interactions -->
							<div
								class="flex w-full items-center gap-1.5 px-2 py-1 text-left text-[10px] font-semibold uppercase tracking-wider cursor-pointer
									text-text-dim/70 hover:text-text-dim transition-colors"
								onclick={(e) => toggleGroup(group, e)}
								onkeydown={(e) => {
									if (e.key === "Enter" || e.key === " ") {
										e.preventDefault();
										toggleGroup(
											group,
											e as unknown as MouseEvent,
										);
									}
								}}
								role="button"
								tabindex="0"
								aria-expanded={expanded}
							>
								<Icon
									name={expanded
										? "chevron-down"
										: "chevron-right"}
									size={10}
									class="shrink-0"
								/>
								{group}
								<span
									class="font-mono font-normal text-text-dim/40"
									>({groupCounts[group]})</span
								>
							</div>
							{#if expanded}
								{#each groupedItems[group] ?? [] as opt (opt.value)}
									<Select.Item
										value={opt.value}
										label={opt.label}
										class="!pl-6"
									>
										{opt.label}
									</Select.Item>
								{/each}
							{/if}
						</Select.Group>
					{/each}
				{/if}
				{#if options.length === 0}
					<div
						class="px-2 py-3 text-center text-[11px] text-text-dim"
					>
						No options available
					</div>
				{/if}
			</Select.Content>
		</Select.Portal>
	</Select.Root>
</div>
