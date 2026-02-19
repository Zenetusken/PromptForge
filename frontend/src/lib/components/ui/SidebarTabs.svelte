<script lang="ts">
	import { Tabs } from "bits-ui";

	let {
		value,
		onValueChange,
		tabs,
		label = "Tabs",
	}: {
		value: string;
		onValueChange: (value: string) => void;
		tabs: { value: string; label: string; testid?: string; activeClass?: string }[];
		label?: string;
	} = $props();
</script>

<Tabs.Root {value} {onValueChange}>
	<Tabs.List class="sidebar-tabs" aria-label={label}>
		{#each tabs as tab}
			<Tabs.Trigger
				value={tab.value}
				class="sidebar-tab {tab.activeClass && value === tab.value ? tab.activeClass : ''}"
				data-testid={tab.testid}
			>
				{tab.label}
			</Tabs.Trigger>
		{/each}
	</Tabs.List>
</Tabs.Root>
