<script lang="ts">
	import { truncateText } from "$lib/utils/format";

	let {
		title,
		maxLength,
		placeholder = "Untitled",
		class: className = "",
	}: {
		title: string | null | undefined;
		maxLength?: number;
		placeholder?: string;
		class?: string;
	} = $props();

	let displayText = $derived(
		title
			? maxLength
				? truncateText(title, maxLength)
				: title
			: placeholder,
	);
</script>

{#if title}
	<span
		class="font-display font-bold tracking-tight {className}"
		data-testid="entry-title">{displayText}</span
	>
{:else}
	<span
		class="font-display font-bold tracking-tight italic text-text-dim {className}"
		data-testid="entry-title-placeholder">{displayText}</span
	>
{/if}
