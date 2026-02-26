<script lang="ts">
	import Icon from '../Icon.svelte';

	interface Tab {
		id: string;
		label: string;
		icon?: string;
	}

	interface Props {
		tabs: Tab[];
		activeTab: string;
		onTabChange: (id: string) => void;
		accent?: 'cyan' | 'green';
	}

	let { tabs, activeTab, onTabChange, accent = 'cyan' }: Props = $props();
</script>

<div class="flex border-b {accent === 'green' ? 'border-neon-green/10' : 'border-neon-cyan/10'}">
	{#each tabs as tab (tab.id)}
		<button
			class="flex items-center gap-1.5 px-3 py-2 text-[11px] transition-colors
				{activeTab === tab.id
					? accent === 'green'
						? 'border-b border-neon-green text-neon-green bg-neon-green/5'
						: 'border-b border-neon-cyan text-neon-cyan bg-neon-cyan/5'
					: 'text-text-dim hover:text-text-secondary hover:bg-bg-hover'}"
			onclick={() => onTabChange(tab.id)}
		>
			{#if tab.icon}
				<Icon name={tab.icon as any} size={11} />
			{/if}
			{tab.label}
		</button>
	{/each}
</div>
