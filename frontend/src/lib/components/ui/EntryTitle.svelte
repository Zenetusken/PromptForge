<script lang="ts">
	import { truncateText } from '$lib/utils/format';

	let {
		title,
		maxLength,
		placeholder = 'Untitled',
		class: className = '',
	}: {
		title: string | null | undefined;
		maxLength?: number;
		placeholder?: string;
		class?: string;
	} = $props();

	let displayText = $derived(
		title
			? (maxLength ? truncateText(title, maxLength) : title)
			: placeholder
	);
</script>

{#if title}
	<span class={className} data-testid="entry-title">{displayText}</span>
{:else}
	<span class="{className} italic text-text-dim" data-testid="entry-title-placeholder">{displayText}</span>
{/if}
