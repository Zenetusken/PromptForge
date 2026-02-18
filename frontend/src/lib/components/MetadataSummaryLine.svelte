<script lang="ts">
	import type { MetadataSegment } from '$lib/utils/format';
	import { formatComplexityDots } from '$lib/utils/format';

	let {
		segments,
		complexity = undefined,
		lowConfidence = false,
		confidenceValue,
		size = 'md',
	}: {
		segments: MetadataSegment[];
		complexity?: string | null;
		lowConfidence?: boolean;
		confidenceValue?: number;
		size?: 'sm' | 'md';
	} = $props();

	let dots = $derived(complexity ? formatComplexityDots(complexity) : null);
	let sizeClass = $derived(size === 'sm' ? 'text-[9px]' : 'text-[10px]');

	// Index of the framework segment (first process-type) for the low-confidence asterisk
	let frameworkIndex = $derived(segments.findIndex(s => s.type === 'process'));
</script>

<div class="metadata-line {sizeClass}" data-testid="metadata-summary-line">
	{#each segments as segment, i}
		{#if i > 0}
			<span class="metadata-separator" aria-hidden="true"></span>
		{/if}
		<span
			class="metadata-{segment.type}"
			title={segment.tooltip ?? undefined}
		>
			{segment.value}{#if lowConfidence && i === frameworkIndex}<span class="text-neon-yellow" title="Low confidence ({confidenceValue != null ? Math.round(confidenceValue * 100) : '?'}%)">*</span>{/if}
		</span>
	{/each}

	{#if dots}
		{#if segments.length > 0}
			<span class="metadata-separator" aria-hidden="true"></span>
		{/if}
		<span class="complexity-dots" title="Complexity: {complexity}">
			{#each Array(dots.total) as _, i}
				<span class="dot {i < dots.filled ? 'filled' : ''}"></span>
			{/each}
		</span>
	{/if}
</div>
