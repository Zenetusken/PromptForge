<script lang="ts">
	import PromptInput from '$lib/components/PromptInput.svelte';
	import PipelineProgress from '$lib/components/PipelineProgress.svelte';
	import ResultPanel from '$lib/components/ResultPanel.svelte';
	import { optimizationState } from '$lib/stores/optimization.svelte';

	function handleOptimize(prompt: string) {
		optimizationState.startOptimization(prompt);
	}
</script>

<div class="mx-auto flex max-w-6xl flex-col gap-6">
	<PromptInput onsubmit={handleOptimize} disabled={optimizationState.isRunning} />

	{#if optimizationState.error}
		<div class="rounded-xl border border-neon-red/30 bg-neon-red/5 p-4">
			<div class="flex items-center gap-2">
				<svg class="h-5 w-5 shrink-0 text-neon-red" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
					<circle cx="12" cy="12" r="10" />
					<line x1="15" y1="9" x2="9" y2="15" />
					<line x1="9" y1="9" x2="15" y2="15" />
				</svg>
				<p class="text-sm text-neon-red">{optimizationState.error}</p>
			</div>
		</div>
	{/if}

	{#if optimizationState.currentRun}
		<PipelineProgress steps={optimizationState.currentRun.steps} />
	{/if}

	{#if optimizationState.result}
		<ResultPanel result={optimizationState.result} />
	{/if}

	{#if !optimizationState.currentRun && !optimizationState.result && !optimizationState.error}
		<div class="flex flex-col items-center justify-center py-20">
			<div
				class="mb-6 text-6xl font-bold tracking-tight"
				style="background: linear-gradient(135deg, var(--color-neon-cyan), var(--color-neon-purple)); -webkit-background-clip: text; -webkit-text-fill-color: transparent;"
			>
				Forge Better Prompts
			</div>
			<p class="max-w-lg text-center text-lg text-text-secondary">
				Paste your prompt above and let PromptForge analyze, optimize, and validate it
				through a multi-stage AI pipeline.
			</p>
			<div class="mt-10 grid grid-cols-3 gap-6">
				<div class="rounded-xl border border-neon-cyan/20 bg-bg-card p-5 text-center">
					<div class="mb-2 font-mono text-2xl text-neon-cyan">01</div>
					<div class="mb-1 font-semibold text-text-primary">Analyze</div>
					<div class="text-sm text-text-secondary">
						Deep analysis of your prompt structure and intent
					</div>
				</div>
				<div class="rounded-xl border border-neon-purple/20 bg-bg-card p-5 text-center">
					<div class="mb-2 font-mono text-2xl text-neon-purple">02</div>
					<div class="mb-1 font-semibold text-text-primary">Optimize</div>
					<div class="text-sm text-text-secondary">
						AI-powered rewriting for maximum clarity and effect
					</div>
				</div>
				<div class="rounded-xl border border-neon-green/20 bg-bg-card p-5 text-center">
					<div class="mb-2 font-mono text-2xl text-neon-green">03</div>
					<div class="mb-1 font-semibold text-text-primary">Validate</div>
					<div class="text-sm text-text-secondary">
						Quality scoring and side-by-side comparison
					</div>
				</div>
			</div>
		</div>
	{/if}
</div>
