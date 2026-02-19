<script lang="ts">
	import { Tooltip as TooltipPrimitive } from "bits-ui";
	import type { Snippet } from "svelte";

	let {
		text,
		children,
		side = "top",
		sideOffset = 8,
		class: className = "",
	}: {
		text: string;
		children: Snippet;
		side?: "top" | "bottom" | "left" | "right";
		sideOffset?: number;
		class?: string;
	} = $props();
</script>

<TooltipPrimitive.Root>
	<TooltipPrimitive.Trigger tabindex={-1}>
		{#snippet child({ props })}
			<span class="inline-flex {className}" {...props}>
				{@render children()}
			</span>
		{/snippet}
	</TooltipPrimitive.Trigger>
	<TooltipPrimitive.Portal>
		<TooltipPrimitive.Content {side} {sideOffset} avoidCollisions collisionPadding={8}>
			{text}
			<TooltipPrimitive.Arrow />
		</TooltipPrimitive.Content>
	</TooltipPrimitive.Portal>
</TooltipPrimitive.Root>
