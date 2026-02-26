<script lang="ts">
	import Icon from '../Icon.svelte';

	interface Props {
		icon: string;
		message: string;
		submessage?: string;
	}

	let { icon, message, submessage }: Props = $props();
</script>

<div class="flex flex-col items-center justify-center h-full gap-2 text-text-dim">
	<Icon name={icon as any} size={24} class="opacity-30" />
	<span class="text-xs">{message}</span>
	{#if submessage}
		<span class="text-[10px] text-text-dim/60">{submessage}</span>
	{/if}
</div>
