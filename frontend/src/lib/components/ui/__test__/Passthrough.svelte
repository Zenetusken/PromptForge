<script lang="ts">
	import type { Snippet } from 'svelte';
	let { children, child, ...rest }: { children?: Snippet; child?: Snippet<[any]>; [key: string]: any } = $props();
</script>

{#if child}
	{@render child({ props: {} })}
{:else if children}
	{@render children()}
{/if}
