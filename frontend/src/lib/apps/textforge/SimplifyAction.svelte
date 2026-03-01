<script lang="ts">
	/**
	 * Extension component for PromptForge's review-actions slot.
	 * Offers "Simplify with TextForge" button that opens TextForge
	 * with the current optimization result.
	 */
	import Icon from '$lib/components/Icon.svelte';
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import { systemBus } from '$lib/services/systemBus.svelte';

	interface Props {
		resultId?: string;
		optimizedPrompt?: string;
	}

	let { resultId, optimizedPrompt }: Props = $props();

	function handleSimplify() {
		// Open or focus TextForge window
		windowManager.openWindow({
			id: 'textforge',
			title: 'TextForge',
			icon: 'zap',
		});
		// Send prefill data via system bus so TextForgeWindow can consume it
		systemBus.emit('textforge:prefill', 'promptforge', {
			text: optimizedPrompt ?? '',
			sourceOptimization: resultId ?? '',
			autoTransform: 'simplify',
		});
	}
</script>

<button
	class="flex items-center gap-1.5 px-2 py-1 text-[10px] border border-neon-orange/20 text-neon-orange
		hover:bg-neon-orange/10 hover:border-neon-orange/40 transition-colors"
	onclick={handleSimplify}
	title="Simplify this prompt with TextForge"
>
	<Icon name="layers" size={10} />
	Simplify
</button>
