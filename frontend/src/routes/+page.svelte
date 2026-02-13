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

	{#if optimizationState.currentRun}
		<PipelineProgress steps={optimizationState.currentRun.steps} />
	{/if}

	{#if optimizationState.result}
		<ResultPanel
			original={optimizationState.result.original}
			optimized={optimizationState.result.optimized}
			scores={optimizationState.result.scores}
			explanation={optimizationState.result.explanation}
		/>
	{/if}

	{#if !optimizationState.currentRun && !optimizationState.result}
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
