<script lang="ts">
	interface Props {
		color: 'green' | 'yellow' | 'red' | 'cyan' | 'orange';
		class?: string;
	}

	let { color, class: className = '' }: Props = $props();
</script>

<span
	class="inline-block h-1.5 w-1.5 rounded-full shrink-0 {className}
		{color === 'green' ? 'bg-neon-green'
		: color === 'yellow' ? 'bg-neon-yellow'
		: color === 'red' ? 'bg-neon-red'
		: color === 'cyan' ? 'bg-neon-cyan'
		: 'bg-neon-orange'}"
></span>
