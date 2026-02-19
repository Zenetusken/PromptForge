<script lang="ts">
	import type { MetadataSegment } from '$lib/utils/format';
	import { formatComplexityDots } from '$lib/utils/format';
	import { Tooltip } from './ui';

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

	function getSegmentTooltip(segment: MetadataSegment, i: number): string | null {
		const hasConfidence = lowConfidence && i === frameworkIndex;
		const confText = hasConfidence
			? `Low confidence (${confidenceValue != null ? Math.round(confidenceValue * 100) : '?'}%)`
			: null;
		if (segment.tooltip && confText) return `${segment.tooltip} · ${confText}`;
		if (segment.tooltip) return segment.tooltip;
		if (confText) return confText;
		return null;
	}
</script>

<div class="metadata-line {sizeClass}" data-testid="metadata-summary-line">
	{#each segments as segment, i}
		{#if i > 0}
			<span class="metadata-separator" aria-hidden="true"></span>
		{/if}
		{@const tooltip = getSegmentTooltip(segment, i)}
		{@const hasConfidence = lowConfidence && i === frameworkIndex}
		{#if tooltip}
			<Tooltip text={tooltip}>
				<span class="metadata-{segment.type}">
					{segment.value}{#if hasConfidence}<span class="text-neon-yellow">*</span>{/if}
				</span>
			</Tooltip>
		{:else}
			<span class="metadata-{segment.type}">
				{segment.value}{#if hasConfidence}<span class="text-neon-yellow">*</span>{/if}
			</span>
		{/if}
	{/each}

	{#if dots}
		{#if segments.length > 0}
			<span class="metadata-separator" aria-hidden="true"></span>
		{/if}
		<Tooltip text="Complexity: {complexity}"><span class="complexity-dots">
			{#each Array(dots.total) as _, i}
				<span class="dot {i < dots.filled ? 'filled' : ''}"></span>
			{/each}
		</span></Tooltip>
	{/if}
</div>
