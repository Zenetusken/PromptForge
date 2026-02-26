<script lang="ts">
	interface Props {
		percent: number;
		color?: 'cyan' | 'green' | 'yellow';
		class?: string;
	}

	let { percent, color = 'cyan', class: className = '' }: Props = $props();
</script>

<div class="h-1 bg-bg-input {className}">
	<div
		class="h-full transition-all duration-300
			{color === 'green' ? 'bg-neon-green'
			: color === 'yellow' ? 'bg-neon-yellow'
			: 'bg-neon-cyan'}"
		style="width: {percent}%"
	></div>
</div>
