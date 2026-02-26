<script lang="ts">
	import { forgeMachine } from '$lib/stores/forgeMachine.svelte';
	import { forgeSession } from '$lib/stores/forgeSession.svelte';
	import type { OptimizationResultState } from '$lib/stores/optimization.svelte';
	import Icon from './Icon.svelte';

	let {
		slotA,
		slotB,
	}: {
		slotA: OptimizationResultState | null;
		slotB: OptimizationResultState | null;
	} = $props();

	/** Load a result's optimized text into the composer for further iteration. */
	function selectAndIterate(slot: OptimizationResultState | null) {
		if (!slot?.optimized?.trim()) return;
		forgeSession.loadRequest({
			text: slot.optimized,
			sourceAction: 'reiterate',
			project: slot.project,
			strategy: 'auto',
		});
		forgeMachine.back();
	}
</script>

<div class="flex flex-wrap gap-1.5 px-2 py-1.5 border-t border-neon-cyan/8">
	<button onclick={() => selectAndIterate(slotA)} class="forge-action-btn">
		<Icon name="check" size={10} />
		Keep A
	</button>
	<button onclick={() => selectAndIterate(slotB)} class="forge-action-btn text-neon-cyan">
		<Icon name="check" size={10} />
		Keep B
	</button>
	<button onclick={() => forgeMachine.back()} class="forge-action-btn">
		<Icon name="chevron-left" size={10} />
		Back
	</button>
</div>
