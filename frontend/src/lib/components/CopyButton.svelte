<script lang="ts">
	import { copyToClipboard } from '$lib/utils/clipboard';

	let { text }: { text: string } = $props();

	let copied = $state(false);

	async function handleCopy() {
		const success = await copyToClipboard(text);
		if (success) {
			copied = true;
			setTimeout(() => {
				copied = false;
			}, 2000);
		}
	}
</script>

<button
	onclick={handleCopy}
	class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors hover:bg-bg-input"
	class:text-neon-green={copied}
	class:text-text-secondary={!copied}
>
	{#if copied}
		<svg
			xmlns="http://www.w3.org/2000/svg"
			width="14"
			height="14"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			stroke-width="2"
			stroke-linecap="round"
			stroke-linejoin="round"
		>
			<polyline points="20 6 9 17 4 12" />
		</svg>
		Copied!
	{:else}
		<svg
			xmlns="http://www.w3.org/2000/svg"
			width="14"
			height="14"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			stroke-width="2"
			stroke-linecap="round"
			stroke-linejoin="round"
		>
			<rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
			<path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
		</svg>
		Copy
	{/if}
</button>
