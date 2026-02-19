<script lang="ts">
	import { Switch as SwitchPrimitive } from "bits-ui";

	let {
		checked,
		onCheckedChange,
		label = "",
	}: {
		checked: boolean;
		onCheckedChange: (checked: boolean) => void;
		label?: string;
	} = $props();
</script>

<SwitchPrimitive.Root
	{checked}
	{onCheckedChange}
	aria-label={label}
>
	<SwitchPrimitive.Thumb />
</SwitchPrimitive.Root>
