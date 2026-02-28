<script lang="ts">
	import { fly } from 'svelte/transition';
	import Icon from './Icon.svelte';
	import type { ContextAction } from '$lib/stores/desktopStore.svelte';

	let {
		open = false,
		x = 0,
		y = 0,
		actions = [],
		onaction,
		onclose,
	}: {
		open: boolean;
		x: number;
		y: number;
		actions: ContextAction[];
		onaction: (id: string) => void;
		onclose: () => void;
	} = $props();

	let menuRef: HTMLDivElement | undefined = $state();

	// Clamp menu position to viewport
	let menuWidth = 180;
	let separatorCount = $derived(actions.filter((a) => a.separator).length);
	let menuHeight = $derived(actions.length * 28 + separatorCount * 12 + 8);
	let vpWidth = $derived(typeof window !== 'undefined' ? window.innerWidth : 1920);
	let vpHeight = $derived(typeof window !== 'undefined' ? window.innerHeight : 1080);
	let clampedX = $derived(Math.min(x, vpWidth - menuWidth - 8));
	let clampedY = $derived(Math.min(y, vpHeight - menuHeight - 8));

	$effect(() => {
		if (open) {
			const frame = requestAnimationFrame(() => {
				document.addEventListener('click', handleOutsideClick);
				document.addEventListener('keydown', handleKeydown);
			});
			return () => {
				cancelAnimationFrame(frame);
				document.removeEventListener('click', handleOutsideClick);
				document.removeEventListener('keydown', handleKeydown);
			};
		}
	});

	function handleOutsideClick(e: MouseEvent) {
		if (menuRef && menuRef.contains(e.target as Node)) return;
		onclose();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.preventDefault();
			onclose();
		}
	}

	function handleAction(actionId: string) {
		onaction(actionId);
	}
</script>

{#if open}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		bind:this={menuRef}
		class="desktop-context-menu"
		style="left: {clampedX}px; top: {clampedY}px"
		transition:fly={{ y: 4, duration: 120 }}
		onmousedown={(e: MouseEvent) => e.stopPropagation()}
		data-testid="desktop-context-menu"
	>
		{#each actions as action (action.id)}
			{#if action.separator}
				<div class="mx-2 my-1 h-px bg-border-subtle"></div>
			{/if}
			<button
				class="context-menu-item {action.danger ? 'context-menu-item--danger' : ''}"
				onclick={() => handleAction(action.id)}
				data-testid="context-action-{action.id}"
			>
				{#if action.icon}
					<Icon name={action.icon as any} size={12} />
				{/if}
				{action.label}
			</button>
		{/each}
	</div>
{/if}
