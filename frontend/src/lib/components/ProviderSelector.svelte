<script lang="ts">
	import { providerState } from '$lib/stores/provider.svelte';
	import type { ModelInfo } from '$lib/api/client';
	import Icon from './Icon.svelte';
	import ApiKeyInput from './ApiKeyInput.svelte';

	let open = $state(false);
	let triggerEl: HTMLButtonElement | undefined = $state();
	let listEl: HTMLDivElement | undefined = $state();
	let focusIndex = $state(-1);
	let hoverIndex = $state(-1);

	// Fixed positioning to break out of overflow-hidden ancestors
	let dropdownStyle = $state('');
	let dropdownDirection: 'up' | 'down' = $state('up');

	const DROPDOWN_MAX_HEIGHT = 448; // matches old max-h-[28rem]
	const HEADER_HEIGHT = 56; // h-14
	const GAP = 8;

	function updateDropdownPosition() {
		if (!triggerEl) return;
		const rect = triggerEl.getBoundingClientRect();

		const spaceBelow = window.innerHeight - rect.bottom - GAP;
		const spaceAbove = rect.top - HEADER_HEIGHT - GAP;

		if (spaceBelow >= DROPDOWN_MAX_HEIGHT || spaceBelow >= spaceAbove) {
			// Open downward
			dropdownDirection = 'down';
			const maxH = Math.min(DROPDOWN_MAX_HEIGHT, spaceBelow);
			dropdownStyle = `position:fixed;left:${rect.left}px;top:${rect.bottom + GAP}px;max-height:${maxH}px;`;
		} else {
			// Open upward
			dropdownDirection = 'up';
			const maxH = Math.min(DROPDOWN_MAX_HEIGHT, spaceAbove);
			dropdownStyle = `position:fixed;left:${rect.left}px;bottom:${window.innerHeight - rect.top + GAP}px;max-height:${maxH}px;`;
		}
	}

	function handleResize() {
		if (open) updateDropdownPosition();
	}

	let detectedProvider = $derived(providerState.providers.find((p) => p.is_default) ?? null);

	let triggerLabel = $derived.by(() => {
		if (providerState.selectedProvider) {
			return providerState.activeProvider?.display_name ?? providerState.selectedProvider;
		}
		const hint = detectedProvider?.display_name;
		return hint ? `Auto (${hint})` : 'Auto';
	});

	let isAvailable = $derived.by(() => {
		if (providerState.selectedProvider) {
			return providerState.isEffectivelyAvailable(providerState.selectedProvider);
		}
		return providerState.activeProvider?.available === true;
	});

	function getSelectedModel(providerName: string, models: ModelInfo[]): string {
		const stored = providerState.getModel(providerName);
		if (stored && models.some((m) => m.id === stored)) return stored;
		return models[0]?.id ?? '';
	}

	function getModelDescription(providerName: string, models: ModelInfo[]): string {
		const selectedId = getSelectedModel(providerName, models);
		return models.find((m) => m.id === selectedId)?.description ?? '';
	}

	function toggle() {
		open = !open;
		if (open) {
			focusIndex = -1;
			hoverIndex = -1;
			updateDropdownPosition();
		}
	}

	function select(name: string | null) {
		providerState.selectProvider(name);
		open = false;
		triggerEl?.focus();
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
			case 'ArrowDown':
				e.preventDefault();
				focusIndex = (focusIndex + 1) % total;
				hoverIndex = -1;
				break;
			case 'ArrowUp':
				e.preventDefault();
				focusIndex = (focusIndex - 1 + total) % total;
				hoverIndex = -1;
				break;
			case 'Enter':
			case ' ':
				e.preventDefault();
				if (focusIndex === 0) {
					select(null);
				} else if (focusIndex > 0) {
					const p = items[focusIndex - 1];
					if (p.available || providerState.hasKey(p.name)) select(p.name);
				}
				break;
			case 'Escape':
				e.preventDefault();
				open = false;
				triggerEl?.focus();
				break;
		}
	}

	function handleClickOutside(e: MouseEvent) {
		if (
			open &&
			triggerEl &&
			!triggerEl.contains(e.target as Node) &&
			listEl &&
			!listEl.contains(e.target as Node)
		) {
			open = false;
		}
	}
</script>

<svelte:window onclick={handleClickOutside} onresize={handleResize} />

<div data-testid="provider-selector">
	<!-- Trigger button -->
	<button
		type="button"
		bind:this={triggerEl}
		onclick={toggle}
		onkeydown={handleKeydown}
		class="flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs transition-all duration-200
			{open
			? 'border-neon-cyan/40 bg-bg-hover shadow-[0_0_12px_rgba(0,229,255,0.08)]'
			: 'border-border-subtle bg-bg-card/50 hover:border-neon-purple/30 hover:bg-bg-hover'}"
		aria-haspopup="listbox"
		aria-expanded={open}
		data-testid="provider-selector-trigger"
	>
		<span
			class="block h-2 w-2 rounded-full {isAvailable
				? 'bg-neon-green status-dot-pulse'
				: 'bg-neon-red'}"
		></span>
		<span class="text-text-secondary">{triggerLabel}</span>
		<Icon
			name="chevron-down"
			size={12}
			class="text-text-dim transition-transform duration-200 {open ? 'rotate-180' : ''}"
		/>
	</button>

	<!-- Dropdown (direction-aware: opens up or down based on available space) -->
	{#if open}
		<div
			bind:this={listEl}
			role="listbox"
			tabindex="-1"
			aria-label="Select LLM provider"
			onkeydown={handleKeydown}
			class="z-[100] min-w-72 overflow-y-auto rounded-xl border border-border-subtle bg-bg-card p-1.5 shadow-2xl {dropdownDirection === 'up' ? 'dropdown-enter-up' : 'dropdown-enter'}"
			style={dropdownStyle}
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
					class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-neon-purple/15"
				>
					<Icon name="sparkles" size={13} class="text-neon-purple" />
				</div>
				<div class="min-w-0 flex-1">
					<div class="text-[13px] font-medium text-text-primary">Auto-detect</div>
					<div class="text-[11px] text-text-dim">
						{detectedProvider
							? `Using ${detectedProvider.display_name}`
							: 'Best available provider'}
					</div>
				</div>
				{#if providerState.selectedProvider === null}
					<Icon name="check" size={16} class="shrink-0 text-neon-cyan" />
				{/if}
			</button>

			<div class="my-1 h-px bg-border-subtle"></div>

			<!-- Provider options -->
			{#each providerState.providers as provider, i}
				{@const isSelected = providerState.selectedProvider === provider.name}
				{@const isAutoDefault =
					providerState.selectedProvider === null && provider.is_default}
				{@const effectivelyAvailable = provider.available || providerState.hasKey(provider.name)}
				{@const selectedModelId = getSelectedModel(provider.name, provider.models)}
				{@const modelDesc = getModelDescription(provider.name, provider.models)}
				<div
					role="option"
					tabindex="0"
					aria-selected={isSelected}
					aria-disabled={!effectivelyAvailable && !provider.requires_api_key}
					class="flex w-full items-start gap-3 rounded-lg px-3 py-2 text-left transition-colors duration-150 hover:bg-bg-hover cursor-pointer
						{!effectivelyAvailable && !provider.requires_api_key ? 'cursor-not-allowed opacity-35' : ''}
						{activeIndex === i + 1 ? 'bg-bg-hover' : ''}"
					onclick={() => effectivelyAvailable && select(provider.name)}
					onkeydown={(e) => {
						if (e.key === 'Enter' || e.key === ' ') {
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
						class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full mt-0.5
							{effectivelyAvailable
							? 'bg-neon-green/10'
							: 'bg-neon-red/10'}"
					>
						<span
							class="block h-2 w-2 rounded-full {effectivelyAvailable
								? 'bg-neon-green'
								: 'bg-neon-red'}"
						></span>
					</div>
					<!-- Content -->
					<div class="min-w-0 flex-1">
						<!-- Row 1: Name + badge + key indicator (right-aligned) -->
						<div class="flex items-center gap-2">
							<span class="text-[13px] font-medium text-text-primary">
								{provider.display_name}
							</span>
							{#if isAutoDefault}
								<span
									class="rounded bg-neon-cyan/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-neon-cyan"
								>
									Default
								</span>
							{/if}
							{#if provider.requires_api_key}
								<span class="ml-auto">
									<ApiKeyInput
										maskedKey={providerState.apiKeys[provider.name] ?? ''}
										validating={providerState.validating[provider.name] ?? false}
										validationResult={providerState.validationResult[provider.name]}
										onKeySet={(key) => {
											providerState.setApiKey(provider.name, key);
											providerState.validateKey(provider.name, key);
										}}
										onKeyClear={() => {
											providerState.clearApiKey(provider.name);
											providerState.clearValidation(provider.name);
										}}
									/>
								</span>
							{/if}
						</div>

						<!-- Row 2: Model pills -->
						{#if provider.models.length > 0}
							<div class="mt-1 flex flex-wrap gap-1">
								{#each provider.models as model}
									{@const isModelSelected = model.id === selectedModelId}
									<button
										type="button"
										onclick={(e) => selectModel(provider.name, model.id, e)}
										class="rounded-md border px-2 py-0.5 text-[10px] font-medium transition-all duration-150
											{isModelSelected
												? 'border-neon-cyan/50 bg-neon-cyan/10 text-neon-cyan'
												: 'border-border-subtle bg-bg-primary/50 text-text-dim hover:border-neon-purple/30 hover:text-text-secondary'}"
										aria-label="Select {model.name}"
									>
										{model.name}
									</button>
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
						<Icon name="check" size={16} class="shrink-0 text-neon-cyan mt-0.5" />
					{/if}
				</div>
			{/each}

			<!-- Remember keys toggle -->
			<div class="my-1 h-px bg-border-subtle"></div>
			<label
				class="flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-[11px] text-text-dim hover:bg-bg-hover cursor-pointer transition-colors"
			>
				<input
					type="checkbox"
					checked={providerState.rememberKeys}
					onchange={(e) => providerState.setRememberKeys((e.target as HTMLInputElement).checked)}
					class="h-3 w-3 rounded border-border-subtle accent-neon-cyan"
				/>
				Remember API keys across sessions
			</label>
		</div>
	{/if}
</div>
