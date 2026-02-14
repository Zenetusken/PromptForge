<script lang="ts">
	import { useCopyFeedback } from '$lib/utils/useCopyFeedback.svelte';
	import Icon from './Icon.svelte';

	let { text }: { text: string } = $props();

	const feedback = useCopyFeedback();
</script>

<button
	onclick={() => feedback.copy(text)}
	class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs transition-[background-color,color] duration-200 hover:bg-bg-hover"
	class:text-neon-green={feedback.copied}
	class:text-text-dim={!feedback.copied}
>
	{#if feedback.copied}
		<Icon name="check" size={13} />
		Copied!
	{:else}
		<Icon name="clipboard" size={13} />
		Copy
	{/if}
</button>
