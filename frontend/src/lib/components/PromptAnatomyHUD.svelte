<script lang="ts">
	import { SECTION_COLORS, type SectionType } from '$lib/utils/promptParser';
	import { slide } from 'svelte/transition';

	interface SectionItem {
		label: string;
		lineNumber: number;
		type: string;
	}

	interface VariableItem {
		name: string;
		occurrences: number;
	}

	interface Props {
		sections?: SectionItem[];
		variables?: VariableItem[];
		mode?: 'compose' | 'review';
		onjumpline?: (line: number) => void;
		totalLines?: number;
	}

	let {
		sections = [],
		variables = [],
		mode = 'compose',
		onjumpline,
		totalLines,
	}: Props = $props();

	let sectionCount = $derived(sections.length);
	let variableCount = $derived(variables.length);
	let isEmpty = $derived(sectionCount === 0 && variableCount === 0);

	function sectionColor(type: string): string {
		return SECTION_COLORS[type as SectionType] ?? 'text-dim';
	}

	function pluralize(n: number, word: string): string {
		return `${n} ${word}${n !== 1 ? 's' : ''}`;
	}
</script>

{#if isEmpty}
	<div class="flex items-center justify-center py-2">
		<span class="text-[10px] italic text-text-dim">No structure detected</span>
	</div>
{:else}
	<div class="space-y-1.5" data-testid="prompt-anatomy-hud">
		<!-- Summary bar -->
		<div class="flex items-center gap-1.5 px-1.5">
			<span class="text-[9px] font-mono tabular-nums text-text-dim">
				{pluralize(sectionCount, 'section')} · {pluralize(variableCount, 'var')}
			</span>
		</div>

		<!-- Coverage bar (compose mode only, when totalLines is available) -->
		{#if mode === 'compose' && totalLines && sectionCount > 0}
			<div class="mx-1.5 flex h-0.5 overflow-hidden rounded-full bg-bg-primary/60">
				{#each sections as section, i}
					{@const nextLine = i + 1 < sections.length ? sections[i + 1].lineNumber : totalLines + 1}
					{@const span = nextLine - section.lineNumber}
					{@const pct = (span / totalLines) * 100}
					<div
						class="h-full"
						style="width: {pct}%; background-color: var(--color-{sectionColor(section.type)}); opacity: 0.5;"
					></div>
				{/each}
			</div>
		{/if}

		<!-- Section rows -->
		{#if sectionCount > 0}
			<div class="space-y-px px-0.5">
				{#each sections as section, i}
					{@const color = sectionColor(section.type)}
					{#if mode === 'compose'}
						<button
							class="anatomy-row group"
							style="--row-color: var(--color-{color}); border-left: 2px solid var(--color-{color}); animation-delay: {i * 50}ms;"
							onclick={() => onjumpline?.(section.lineNumber)}
							aria-label="{section.label} ({section.type}) — line {section.lineNumber}"
							transition:slide={{ duration: 150 }}
						>
							<span class="anatomy-type-badge" style="--badge-color: var(--color-{color})">
								{section.type}
							</span>
							<span class="min-w-0 flex-1 truncate text-[10px] text-text-secondary transition-colors duration-200 group-hover:text-text-primary">
								{section.label}
							</span>
							<span class="ml-auto shrink-0 font-mono text-[9px] tabular-nums text-text-dim/40">
								:{section.lineNumber}
							</span>
						</button>
					{:else}
						<div
							class="anatomy-row"
							style="--row-color: var(--color-{color}); border-left: 2px solid var(--color-{color}); animation: stagger-fade-in 350ms cubic-bezier(0.16, 1, 0.3, 1) forwards; animation-delay: {i * 50}ms; opacity: 0;"
							aria-label="{section.label} ({section.type}) — line {section.lineNumber}"
						>
							<span class="anatomy-type-badge" style="--badge-color: var(--color-{color})">
								{section.type}
							</span>
							<span class="min-w-0 flex-1 truncate text-[10px] text-text-secondary">
								{section.label}
							</span>
							<span class="ml-auto shrink-0 font-mono text-[9px] tabular-nums text-text-dim/40">
								:{section.lineNumber}
							</span>
						</div>
					{/if}
				{/each}
			</div>
		{/if}

		<!-- Variable chips -->
		{#if variableCount > 0}
			<div class="flex flex-wrap gap-1 px-1.5">
				{#each variables as variable}
					<span
						class="anatomy-var-chip"
						title="{variable.name}: {variable.occurrences} occurrence{variable.occurrences !== 1 ? 's' : ''}"
					>
						<span class="text-neon-teal/70">{`{{${variable.name}}}`}</span>
						{#if variable.occurrences > 1}
							<span class="text-neon-teal/40">&times;{variable.occurrences}</span>
						{/if}
					</span>
				{/each}
			</div>
		{/if}
	</div>
{/if}

<style>
	.anatomy-row {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.125rem 0.375rem;
		border-radius: 2px;
		transition: background-color 200ms, border-color 200ms;
		cursor: default;
	}

	button.anatomy-row {
		width: 100%;
		text-align: left;
		cursor: pointer;
	}

	button.anatomy-row:hover {
		background-color: var(--color-bg-hover);
		border-left-color: var(--row-color);
	}

	button.anatomy-row:focus-visible {
		outline: 1px solid rgba(0, 229, 255, 0.3);
		outline-offset: 2px;
	}

	.anatomy-type-badge {
		display: inline-block;
		padding: 0 0.25rem;
		border-radius: 2px;
		font-family: var(--font-mono);
		font-size: 8px;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		line-height: 1.5;
		background: color-mix(in srgb, var(--badge-color) 8%, transparent);
		border: 1px solid color-mix(in srgb, var(--badge-color) 15%, transparent);
		color: color-mix(in srgb, var(--badge-color) 70%, transparent);
	}

	.anatomy-var-chip {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		padding: 1px 0.375rem;
		border-radius: 9999px;
		font-family: var(--font-mono);
		font-size: 10px;
		background: color-mix(in srgb, var(--color-neon-teal) 6%, transparent);
		border: 1px solid color-mix(in srgb, var(--color-neon-teal) 15%, transparent);
		transition: background-color 200ms, border-color 200ms, color 200ms;
	}

	.anatomy-var-chip:hover {
		background: color-mix(in srgb, var(--color-neon-teal) 10%, transparent);
		border-color: color-mix(in srgb, var(--color-neon-teal) 25%, transparent);
	}

	.anatomy-var-chip:hover :global(span) {
		opacity: 1;
	}

	@keyframes stagger-fade-in {
		from {
			opacity: 0;
			transform: translateY(4px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		@keyframes stagger-fade-in {
			from { opacity: 1; }
			to { opacity: 1; }
		}

		.anatomy-row,
		.anatomy-var-chip {
			transition-duration: 0.01ms !important;
		}
	}
</style>
