<script lang="ts">
	import PromptInput from '$lib/components/PromptInput.svelte';
	import PipelineProgress from '$lib/components/PipelineProgress.svelte';
	import ResultPanel from '$lib/components/ResultPanel.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { optimizationState } from '$lib/stores/optimization.svelte';
	import { promptState } from '$lib/stores/prompt.svelte';
	import type { OptimizeMetadata } from '$lib/api/client';

	function handleOptimize(prompt: string, metadata?: OptimizeMetadata) {
		promptState.set(prompt);
		optimizationState.startOptimization(prompt, metadata);
	}

	function handleRetry() {
		if (promptState.text) {
			optimizationState.error = null;
			optimizationState.startOptimization(promptState.text);
		}
	}
</script>

<div class="flex flex-col gap-5">
	{#if !optimizationState.currentRun && !optimizationState.result && !optimizationState.error}
		<div class="hero-section flex flex-col items-center pt-4">
			<!-- Title -->
			<h1
				class="animate-fade-in-up text-center text-gradient-forge font-display text-3xl font-extrabold leading-normal tracking-tight sm:text-4xl"
			>
				Forge Better Prompts
			</h1>
			<p
				class="animate-fade-in-up mt-2 max-w-lg text-center text-sm leading-relaxed text-text-secondary"
				style="--delay: 150ms;"
			>
				Analyze, optimize, and validate your prompts through a multi-stage AI pipeline.
			</p>

			<!-- Pipeline cards -->
			<div
				class="animate-fade-in-up mt-5 grid w-full max-w-2xl grid-cols-3 gap-3"
				style="--delay: 300ms;"
			>
				<div class="card-glow group relative overflow-hidden rounded-lg border border-neon-cyan/10 bg-bg-card/60 px-3 py-2.5">
					<div class="absolute -right-4 -top-4 h-14 w-14 rounded-full bg-neon-cyan/5 blur-2xl transition-[background-color] duration-500 group-hover:bg-neon-cyan/10"></div>
					<div class="relative flex items-center gap-2.5">
						<div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-neon-cyan/10">
							<Icon name="info" size={13} class="text-neon-cyan" />
						</div>
						<div>
							<div class="font-display text-xs font-bold text-text-primary">Analyze</div>
							<div class="text-[10px] leading-tight text-text-dim">Structure & intent</div>
						</div>
					</div>
				</div>

				<div class="card-glow group relative overflow-hidden rounded-lg border border-neon-purple/10 bg-bg-card/60 px-3 py-2.5">
					<div class="absolute -right-4 -top-4 h-14 w-14 rounded-full bg-neon-purple/5 blur-2xl transition-[background-color] duration-500 group-hover:bg-neon-purple/10"></div>
					<div class="relative flex items-center gap-2.5">
						<div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-neon-purple/10">
							<Icon name="sparkles" size={13} class="text-neon-purple" />
						</div>
						<div>
							<div class="font-display text-xs font-bold text-text-primary">Optimize</div>
							<div class="text-[10px] leading-tight text-text-dim">AI-powered rewriting</div>
						</div>
					</div>
				</div>

				<div class="card-glow group relative overflow-hidden rounded-lg border border-neon-green/10 bg-bg-card/60 px-3 py-2.5">
					<div class="absolute -right-4 -top-4 h-14 w-14 rounded-full bg-neon-green/5 blur-2xl transition-[background-color] duration-500 group-hover:bg-neon-green/10"></div>
					<div class="relative flex items-center gap-2.5">
						<div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-neon-green/10">
							<Icon name="check" size={13} class="text-neon-green" />
						</div>
						<div>
							<div class="font-display text-xs font-bold text-text-primary">Validate</div>
							<div class="text-[10px] leading-tight text-text-dim">Scoring & comparison</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	{/if}

	<PromptInput onsubmit={handleOptimize} disabled={optimizationState.isRunning} />

	{#if optimizationState.error}
		<div class="animate-fade-in rounded-xl border border-neon-red/20 bg-neon-red/5 p-4" role="alert" data-testid="error-display">
			<div class="flex items-center gap-3">
				<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-neon-red/10">
					<Icon name="alert-circle" size={16} class="text-neon-red" />
				</div>
				<div class="flex-1">
					<p class="text-sm font-medium text-neon-red">Optimization failed</p>
					<p class="mt-0.5 text-sm text-text-secondary">{optimizationState.error}</p>
				</div>
				{#if promptState.text}
					<button
						onclick={handleRetry}
						class="shrink-0 rounded-lg border border-neon-cyan/20 bg-neon-cyan/5 px-4 py-1.5 font-mono text-xs text-neon-cyan transition-[background-color] hover:bg-neon-cyan/10"
						data-testid="retry-button"
					>
						Retry
					</button>
				{/if}
			</div>
		</div>
	{/if}

	{#if optimizationState.currentRun}
		<PipelineProgress steps={optimizationState.currentRun.steps} />
	{/if}

	{#if optimizationState.result}
		<ResultPanel result={optimizationState.result} />
	{/if}
</div>
