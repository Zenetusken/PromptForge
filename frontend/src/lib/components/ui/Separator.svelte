<script lang="ts">
	import { Separator as SeparatorPrimitive } from "bits-ui";

	let {
		class: className = "divider-glow",
		orientation = "horizontal",
	}: {
		class?: string;
		orientation?: "horizontal" | "vertical";
	} = $props();
</script>

<SeparatorPrimitive.Root class={className} {orientation} />
