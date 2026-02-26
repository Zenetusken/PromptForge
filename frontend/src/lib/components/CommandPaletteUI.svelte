<script lang="ts">
	import { commandPalette } from '$lib/services/commandPalette.svelte';
	import Icon from './Icon.svelte';
	import { onMount } from 'svelte';

	let inputRef: HTMLInputElement = $state(null as unknown as HTMLInputElement);
	let selectedIndex = $state(0);

	const filtered = $derived(commandPalette.filteredCommands);

	// Reset selection when results change
	$effect(() => {
		if (filtered.length > 0) {
			selectedIndex = 0;
		}
	});

	// Auto-focus on open
	$effect(() => {
		if (commandPalette.isOpen && inputRef) {
			requestAnimationFrame(() => inputRef?.focus());
		}
	});

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.preventDefault();
			commandPalette.close();
			return;
		}
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			selectedIndex = Math.min(selectedIndex + 1, filtered.length - 1);
			return;
		}
		if (e.key === 'ArrowUp') {
			e.preventDefault();
			selectedIndex = Math.max(selectedIndex - 1, 0);
			return;
		}
		if (e.key === 'Enter' && filtered[selectedIndex]) {
			e.preventDefault();
			commandPalette.execute(filtered[selectedIndex].id);
			return;
		}
	}

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) {
			commandPalette.close();
		}
	}
</script>

{#if commandPalette.isOpen}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]"
		onclick={handleBackdropClick}
		onkeydown={handleKeydown}
	>
		<div
			class="w-full max-w-lg border border-neon-cyan/20 bg-bg-card font-mono"
			role="dialog"
			aria-label="Command Palette"
		>
			<!-- Search input -->
			<div class="flex items-center gap-2 border-b border-neon-cyan/10 px-3 py-2">
				<Icon name="search" size={14} class="text-neon-cyan/60 shrink-0" />
				<input
					bind:this={inputRef}
					bind:value={commandPalette.searchQuery}
					type="text"
					placeholder="Type a command..."
					class="flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-dim outline-none"
				/>
				<span class="text-[10px] text-text-dim/40 border border-text-dim/20 px-1 py-0.5">ESC</span>
			</div>

			<!-- Results -->
			<div class="max-h-[300px] overflow-y-auto">
				{#if filtered.length === 0}
					<div class="px-3 py-4 text-center text-xs text-text-dim">
						No matching commands
					</div>
				{:else}
					{#each filtered as cmd, i (cmd.id)}
						<div
							class="flex items-center gap-2 px-3 py-1.5 cursor-pointer transition-colors text-sm
								{i === selectedIndex ? 'bg-neon-cyan/10 text-neon-cyan' : 'text-text-secondary hover:bg-bg-hover'}"
							onclick={() => commandPalette.execute(cmd.id)}
						onkeydown={(e) => { if (e.key === 'Enter') commandPalette.execute(cmd.id); }}
							onmouseenter={() => selectedIndex = i}
							role="option"
						tabindex="-1"
							aria-selected={i === selectedIndex}
						>
							{#if cmd.icon}
								<Icon name={cmd.icon as any} size={12} class="shrink-0 opacity-60" />
							{/if}
							<span class="flex-1 truncate">{cmd.label}</span>
							<span class="text-[10px] text-text-dim/50 uppercase">{cmd.category}</span>
							{#if cmd.shortcut}
								<span class="text-[10px] text-text-dim/40 border border-text-dim/20 px-1 py-0.5 shrink-0">{cmd.shortcut}</span>
							{/if}
						</div>
					{/each}
				{/if}
			</div>
		</div>
	</div>
{/if}
