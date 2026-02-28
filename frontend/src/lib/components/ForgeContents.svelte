<script lang="ts">
	import type { OptimizationResultState } from '$lib/stores/optimization.svelte';
	import { ARTIFACT_KINDS, toSubArtifactFilename } from '$lib/utils/fileTypes';
	import { normalizeScore, formatScore, getScoreBadgeClass } from '$lib/utils/format';
	import { ALL_DIMENSIONS, DIMENSION_LABELS, DIMENSION_COLORS } from '$lib/utils/scoreDimensions';
	import Icon from './Icon.svelte';

	let { result }: { result: OptimizationResultState } = $props();

	type SubArtifactKey = 'forge-analysis' | 'forge-scores' | 'forge-strategy';
	let expanded: Set<SubArtifactKey> = $state(new Set());

	function toggle(key: SubArtifactKey) {
		if (expanded.has(key)) {
			expanded = new Set([...expanded].filter(k => k !== key));
		} else {
			expanded = new Set([...expanded, key]);
		}
	}

	const subArtifacts: { kind: SubArtifactKey; iconName: 'search' | 'activity' | 'sliders' }[] = [
		{ kind: 'forge-analysis', iconName: 'search' },
		{ kind: 'forge-scores', iconName: 'activity' },
		{ kind: 'forge-strategy', iconName: 'sliders' },
	];
</script>

<div class="border-t border-white/5">
	<details class="group">
		<summary class="flex items-center gap-1.5 px-2 py-1 cursor-pointer text-[10px] text-text-dim hover:text-text-secondary transition-colors select-none">
			<Icon name="chevron-right" size={10} class="transition-transform group-open:rotate-90" />
			<span class="font-medium uppercase tracking-wider">Forge Contents</span>
			<span class="text-text-dim/40">{subArtifacts.length} files</span>
		</summary>

		<div class="pb-1">
			{#each subArtifacts as sub}
				{@const meta = ARTIFACT_KINDS[sub.kind]}
				{@const filename = toSubArtifactFilename(sub.kind)}
				{@const isExpanded = expanded.has(sub.kind)}

				<!-- Sub-artifact row -->
				<button
					class="w-full flex items-center gap-2 px-3 py-1 text-left hover:bg-bg-hover/30 transition-colors"
					onclick={() => toggle(sub.kind)}
				>
					<Icon name={isExpanded ? 'chevron-down' : 'chevron-right'} size={10} class="text-text-dim shrink-0" />
					<Icon name={sub.iconName} size={12} class="text-neon-{meta.color} shrink-0" />
					<span class="text-[10px] text-text-primary font-mono">{filename}</span>
				</button>

				<!-- Expanded content -->
				{#if isExpanded}
					<div class="px-4 py-1.5 ml-5 border-l border-white/5">
						{#if sub.kind === 'forge-analysis'}
							<!-- Analysis: task type, complexity, strengths, weaknesses, changes -->
							<div class="space-y-1.5 text-[10px]">
								<div class="flex gap-3">
									{#if result.task_type}
										<div>
											<span class="text-text-dim">Task:</span>
											<span class="text-text-primary ml-1">{result.task_type}</span>
										</div>
									{/if}
									{#if result.complexity}
										<div>
											<span class="text-text-dim">Complexity:</span>
											<span class="text-text-primary ml-1">{result.complexity}</span>
										</div>
									{/if}
								</div>
								{#if Array.isArray(result.strengths) && result.strengths.length > 0}
									<div>
										<span class="text-neon-green font-medium">Strengths</span>
										<ul class="mt-0.5 space-y-0.5 text-text-secondary">
											{#each result.strengths as s}
												<li class="flex gap-1"><span class="text-neon-green/50 shrink-0">+</span> {s}</li>
											{/each}
										</ul>
									</div>
								{/if}
								{#if Array.isArray(result.weaknesses) && result.weaknesses.length > 0}
									<div>
										<span class="text-neon-red font-medium">Weaknesses</span>
										<ul class="mt-0.5 space-y-0.5 text-text-secondary">
											{#each result.weaknesses as w}
												<li class="flex gap-1"><span class="text-neon-red/50 shrink-0">-</span> {w}</li>
											{/each}
										</ul>
									</div>
								{/if}
								{#if Array.isArray(result.changes_made) && result.changes_made.length > 0}
									<div>
										<span class="text-neon-cyan font-medium">Changes Made</span>
										<ul class="mt-0.5 space-y-0.5 text-text-secondary">
											{#each result.changes_made as c}
												<li class="flex gap-1"><span class="text-neon-cyan/50 shrink-0">~</span> {c}</li>
											{/each}
										</ul>
									</div>
								{/if}
							</div>

						{:else if sub.kind === 'forge-scores'}
							<!-- Scores: 5 dimension scores + verdict -->
							<div class="space-y-1 text-[10px]">
								{#each ALL_DIMENSIONS as dim}
									{@const score = result.scores[dim]}
									{@const normalized = normalizeScore(score)}
									<div class="flex items-center gap-1.5">
										<span class="w-16 text-text-dim truncate">{DIMENSION_LABELS[dim]}</span>
										<div class="flex-1 h-1 rounded-full bg-bg-primary/60 overflow-hidden">
											<div
												class="h-full rounded-full"
												style="width: {normalized ?? 0}%; background-color: var(--color-{DIMENSION_COLORS[dim]})"
											></div>
										</div>
										<span class="w-5 text-right font-mono text-text-dim">{formatScore(score)}</span>
									</div>
								{/each}
								{#if result.scores.overall}
									<div class="flex items-center gap-1.5 pt-0.5 border-t border-white/5">
										<span class="w-16 text-text-secondary font-medium">Overall</span>
										<span class="font-mono font-bold {getScoreBadgeClass(result.scores.overall)}">
											{normalizeScore(result.scores.overall)}/10
										</span>
									</div>
								{/if}
								{#if result.is_improvement !== null && result.is_improvement !== undefined}
									<div class="flex items-center gap-1 pt-0.5">
										<Icon name={result.is_improvement ? 'arrow-up' : 'minus'} size={10}
											class={result.is_improvement ? 'text-neon-green' : 'text-text-dim'} />
										<span class="text-text-secondary">
											{result.is_improvement ? 'Improvement detected' : 'No improvement'}
										</span>
									</div>
								{/if}
								{#if result.verdict}
									<p class="italic text-text-dim leading-snug pt-0.5">{result.verdict}</p>
								{/if}
							</div>

						{:else if sub.kind === 'forge-strategy'}
							<!-- Strategy: name, reasoning, confidence, secondary, detected patterns -->
							<div class="space-y-1.5 text-[10px]">
								{#if result.strategy}
									<div>
										<span class="text-text-dim">Strategy:</span>
										<span class="text-text-primary font-medium ml-1">{result.strategy}</span>
									</div>
								{/if}
								{#if result.strategy_confidence}
									<div>
										<span class="text-text-dim">Confidence:</span>
										<span class="font-mono ml-1 {result.strategy_confidence >= 0.8 ? 'text-neon-green' : result.strategy_confidence >= 0.6 ? 'text-neon-yellow' : 'text-neon-red'}">
											{Math.round(result.strategy_confidence * 100)}%
										</span>
									</div>
								{/if}
								{#if Array.isArray(result.secondary_frameworks) && result.secondary_frameworks.length > 0}
									<div>
										<span class="text-text-dim">Secondary:</span>
										<span class="text-text-secondary ml-1">{result.secondary_frameworks.join(', ')}</span>
									</div>
								{/if}
								{#if result.strategy_reasoning}
									<div>
										<span class="text-text-dim">Reasoning:</span>
										<p class="text-text-secondary leading-snug mt-0.5">{result.strategy_reasoning}</p>
									</div>
								{/if}
							</div>
						{/if}
					</div>
				{/if}
			{/each}
		</div>
	</details>
</div>
