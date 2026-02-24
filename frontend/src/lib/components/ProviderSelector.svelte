<script lang="ts">
	import { Popover } from "bits-ui";
	import { providerState } from "$lib/stores/provider.svelte";
	import type { ModelInfo } from "$lib/api/client";
	import Icon from "./Icon.svelte";
	import ApiKeyInput from "./ApiKeyInput.svelte";
	import { Switch, Separator, Tooltip } from "./ui";

	let open = $state(false);
	let focusIndex = $state(-1);
	let hoverIndex = $state(-1);

	let detectedProvider = $derived(
		providerState.providers.find((p) => p.is_default) ?? null,
	);

	let triggerLabel = $derived.by(() => {
		if (providerState.selectedProvider) {
			return (
				providerState.activeProvider?.display_name ??
				providerState.selectedProvider
			);
		}
		const hint = detectedProvider?.display_name;
		return hint ? `Auto (${hint})` : "Auto";
	});

	let isAvailable = $derived.by(() => {
		if (providerState.selectedProvider) {
			return providerState.isEffectivelyAvailable(
				providerState.selectedProvider,
			);
		}
		return providerState.activeProvider?.available === true;
	});

	function getSelectedModel(
		providerName: string,
		models: ModelInfo[],
	): string {
		const stored = providerState.getModel(providerName);
		if (stored && models.some((m) => m.id === stored)) return stored;
		return models[0]?.id ?? "";
	}

	function getModelDescription(
		providerName: string,
		models: ModelInfo[],
	): string {
		const selectedId = getSelectedModel(providerName, models);
		return models.find((m) => m.id === selectedId)?.description ?? "";
	}

	function select(name: string | null) {
		providerState.selectProvider(name);
		open = false;
	}

	function selectModel(providerName: string, modelId: string, e: MouseEvent) {
		e.stopPropagation();
		providerState.setModel(providerName, modelId);
	}

	let activeIndex = $derived(focusIndex >= 0 ? focusIndex : hoverIndex);

	function handleKeydown(e: KeyboardEvent) {
		if (!open) return;
		const items = providerState.providers;
		const total = items.length + 1;

		switch (e.key) {
			case "ArrowDown":
				e.preventDefault();
				focusIndex = (focusIndex + 1) % total;
				hoverIndex = -1;
				break;
			case "ArrowUp":
				e.preventDefault();
				focusIndex = (focusIndex - 1 + total) % total;
				hoverIndex = -1;
				break;
			case "Enter":
			case " ":
				e.preventDefault();
				if (focusIndex === 0) {
					select(null);
				} else if (focusIndex > 0) {
					const p = items[focusIndex - 1];
					if (p.available || providerState.hasKey(p.name))
						select(p.name);
				}
				break;
			case "Escape":
				e.preventDefault();
				open = false;
				break;
		}
	}
</script>

<div data-testid="provider-selector">
	<Popover.Root
		bind:open
		onOpenChange={(o) => {
			if (o) {
				focusIndex = -1;
				hoverIndex = -1;
			}
		}}
	>
		<Popover.Trigger
			class="flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-medium transition-all duration-200
				{open
				? 'border-neon-cyan/40 bg-bg-hover shadow-[0_0_12px_rgba(0,229,255,0.08)]'
				: 'border-border-subtle bg-bg-card/50 hover:border-neon-purple/30 hover:bg-bg-hover hover:shadow-[0_0_10px_rgba(168,85,247,0.06)]'}"
			data-testid="provider-selector-trigger"
		>
			<Tooltip
				text={isAvailable
					? "Provider available"
					: "Provider unavailable"}
				side="bottom"
			>
				<span
					class="block h-1.5 w-1.5 rounded-full ring-2 {isAvailable
						? 'bg-neon-green ring-neon-green/20 status-dot-pulse shadow-[0_0_6px_var(--color-neon-green)]'
						: 'bg-neon-red ring-neon-red/20'}"
				></span>
			</Tooltip>
			<span class="text-text-secondary">{triggerLabel}</span>
			<Icon
				name="chevron-down"
				size={12}
				class="text-text-dim transition-transform duration-200 {open
					? 'rotate-180'
					: ''}"
			/>
		</Popover.Trigger>

		<Popover.Portal>
			<Popover.Content
				side="bottom"
				align="start"
				sideOffset={8}
				class="z-[100] min-w-72 overflow-y-auto border-t border-t-neon-cyan/10 p-1.5"
				onkeydown={handleKeydown}
				data-testid="provider-selector-list"
			>
				<!-- Auto-detect option -->
				<button
					type="button"
					role="option"
					aria-selected={providerState.selectedProvider === null}
					class="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors duration-150 hover:bg-bg-hover
					{activeIndex === 0 ? 'bg-bg-hover' : ''}"
					onclick={() => select(null)}
					onmouseenter={() => {
						hoverIndex = 0;
						focusIndex = -1;
					}}
					onmouseleave={() => (hoverIndex = -1)}
					data-testid="provider-option-auto"
				>
					<div
						class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full ring-1 ring-neon-purple/20 bg-neon-purple/8"
					>
						<Icon
							name="sparkles"
							size={13}
							class="text-neon-purple"
						/>
					</div>
					<div class="min-w-0 flex-1">
						<div class="text-[13px] font-medium text-text-primary">
							Auto-detect
						</div>
						<div class="text-[11px] text-text-dim">
							{detectedProvider
								? `Using ${detectedProvider.display_name}`
								: "Best available provider"}
						</div>
					</div>
					{#if providerState.selectedProvider === null}
						<Icon
							name="check"
							size={16}
							class="shrink-0 text-neon-cyan"
						/>
					{/if}
				</button>

				<Separator
					class="my-1.5 h-px bg-gradient-to-r from-transparent via-border-glow to-transparent"
				/>

				<!-- Provider options -->
				{#each providerState.providers as provider, i}
					{@const isSelected =
						providerState.selectedProvider === provider.name}
					{@const isAutoDefault =
						providerState.selectedProvider === null &&
						provider.is_default}
					{@const effectivelyAvailable =
						provider.available ||
						providerState.hasKey(provider.name)}
					{@const selectedModelId = getSelectedModel(
						provider.name,
						provider.models,
					)}
					{@const modelDesc = getModelDescription(
						provider.name,
						provider.models,
					)}
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<div
						role="option"
						tabindex="0"
						aria-selected={isSelected}
						aria-disabled={!effectivelyAvailable &&
							!provider.requires_api_key}
						class="flex w-full items-start gap-3 rounded-lg px-3 py-2 text-left transition-colors duration-150 hover:bg-bg-hover
						{!effectivelyAvailable && !provider.requires_api_key
							? 'cursor-not-allowed opacity-35'
							: 'cursor-pointer'}
						{activeIndex === i + 1 ? 'bg-bg-hover' : ''}"
						onclick={() =>
							effectivelyAvailable && select(provider.name)}
						onkeydown={(e) => {
							if (e.key === "Enter" || e.key === " ") {
								e.preventDefault();
								if (effectivelyAvailable) select(provider.name);
							}
						}}
						onmouseenter={() => {
							hoverIndex = i + 1;
							focusIndex = -1;
						}}
						onmouseleave={() => (hoverIndex = -1)}
						data-testid="provider-option-{provider.name}"
					>
						<!-- Status dot -->
						<div
							class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full ring-1 mt-0.5
							{effectivelyAvailable
								? 'bg-neon-green/8 ring-neon-green/20'
								: 'bg-neon-red/8 ring-neon-red/20'}"
						>
							<span
								class="block h-1.5 w-1.5 rounded-full {effectivelyAvailable
									? 'bg-neon-green'
									: 'bg-neon-red'}"
							></span>
						</div>
						<!-- Content -->
						<div class="min-w-0 flex-1">
							<!-- Row 1: Name + badge + key indicator (right-aligned) -->
							<div class="flex items-center gap-2">
								<span
									class="text-[13px] font-medium text-text-primary"
								>
									{provider.display_name}
								</span>
								{#if isAutoDefault}
									<Tooltip
										text="Auto-detected default provider"
										side="top"
									>
										<span
											class="rounded-md border border-neon-cyan/25 bg-transparent px-1.5 py-[2px] text-[9px] font-semibold uppercase tracking-wider text-neon-cyan"
										>
											Default
										</span>
									</Tooltip>
								{/if}
								{#if provider.requires_api_key}
									<span class="ml-auto">
										<ApiKeyInput
											maskedKey={providerState.apiKeys[
												provider.name
											] ?? ""}
											validating={providerState
												.validating[provider.name] ??
												false}
											validationResult={providerState
												.validationResult[
												provider.name
											]}
											onKeySet={(key) => {
												providerState.setApiKey(
													provider.name,
													key,
												);
												providerState.validateKey(
													provider.name,
													key,
												);
											}}
											onKeyClear={() => {
												providerState.clearApiKey(
													provider.name,
												);
												providerState.clearValidation(
													provider.name,
												);
											}}
										/>
									</span>
								{/if}
							</div>

							<!-- Row 2: Model pills -->
							{#if provider.models.length > 0}
								<div class="mt-1 flex flex-wrap gap-1">
									{#each provider.models as model}
										{@const isModelSelected =
											model.id === selectedModelId}
										<Tooltip text={model.id} side="bottom">
											<button
												type="button"
												onclick={(e) =>
													selectModel(
														provider.name,
														model.id,
														e,
													)}
												class="chip chip-rect chip-interactive border transition-all duration-150
											{isModelSelected
													? 'border-neon-cyan/40 bg-transparent text-neon-cyan'
													: 'border-border-subtle bg-bg-primary/50 text-text-dim hover:border-neon-purple/30 hover:text-text-secondary hover:bg-bg-hover/30'}"
												aria-label="Select {model.name}"
											>
												{model.name}
											</button>
										</Tooltip>
									{/each}
								</div>
							{/if}

							<!-- Row 3: Model description -->
							{#if modelDesc}
								<div class="mt-0.5 text-[11px] text-text-dim">
									{modelDesc}
								</div>
							{/if}
						</div>
						<!-- Checkmark for selected -->
						{#if isSelected}
							<Icon
								name="check"
								size={16}
								class="shrink-0 text-neon-cyan mt-0.5"
							/>
						{/if}
					</div>
				{/each}

				<!-- Remember keys toggle -->
				<Separator
					class="my-1.5 h-px bg-gradient-to-r from-transparent via-border-glow to-transparent"
				/>
				<!-- svelte-ignore a11y_click_events_have_key_events -->
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div
					class="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-[11px] text-text-dim hover:bg-bg-hover cursor-pointer transition-colors"
					onclick={() =>
						providerState.setRememberKeys(
							!providerState.rememberKeys,
						)}
				>
					<Switch
						checked={providerState.rememberKeys}
						onCheckedChange={(v) =>
							providerState.setRememberKeys(v)}
						label="Remember API keys across sessions"
					/>
					<Tooltip text="Keys stored in browser localStorage"
						><span>Remember API keys across sessions</span></Tooltip
					>
				</div>
			</Popover.Content>
		</Popover.Portal>
	</Popover.Root>
</div>
