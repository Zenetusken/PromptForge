<script lang="ts">
    import { forgeSession } from "$lib/stores/forgeSession.svelte";
    import { optimizationState } from "$lib/stores/optimization.svelte";
    import { forgeMachine } from "$lib/stores/forgeMachine.svelte";
    import { promptAnalysis } from "$lib/stores/promptAnalysis.svelte";
    import ForgeStrategySection from "./ForgeStrategySection.svelte";
    import ForgePipelineInline from "./ForgePipelineInline.svelte";
    import ForgeAnalysisPreview from "./ForgeAnalysisPreview.svelte";
    import ForgeReview from "./ForgeReview.svelte";
    import ForgeCompare from "./ForgeCompare.svelte";
    import Icon from "./Icon.svelte";
    import { MetaBadge } from "./ui";

    function handleAnalyze() {
        optimizationState.runNodeAnalyze({
            prompt: forgeSession.draft.text,
            codebase_context: forgeSession.draft.contextProfile,
        });
    }

    function handleForge() {
        if (!forgeSession.validate()) {
            forgeSession.showMetadata = true;
            return;
        }
        optimizationState.startOptimization(
            forgeSession.draft.text,
            forgeSession.buildMetadata(),
        );
        forgeMachine.forge();
    }

    function handleCancelPipeline() {
        optimizationState.reset();
        forgeMachine.reset();
    }

    let canForge = $derived(forgeSession.hasText && !optimizationState.isRunning);
    let isAnalyzing = $derived(optimizationState.isAnalyzing);
    let hasError = $derived(!!optimizationState.error && !optimizationState.isRunning);
</script>

<div
    class="flex h-full w-80 shrink-0 flex-col overflow-y-auto border-l border-neon-cyan/10 bg-bg-secondary"
>
    {#if forgeMachine.mode === 'compose'}
        <!-- COMPOSE MODE: Strategy recommendations + picker + actions -->
        <div class="flex flex-col gap-3 p-3">
            <div class="text-[10px] font-bold uppercase tracking-widest text-text-dim">
                Orchestrator
            </div>

            <!-- Strategy recommendations from prompt analysis -->
            {#if forgeSession.hasText && promptAnalysis.recommendedStrategies.length > 0}
                <div class="flex flex-col gap-1.5">
                    <div class="flex items-center gap-1.5">
                        <span class="text-[10px] font-bold uppercase tracking-wider text-text-secondary">Recommended</span>
                        {#if promptAnalysis.heuristic}
                            <MetaBadge type="task" value={promptAnalysis.heuristic.taskType} size="xs" />
                        {/if}
                    </div>
                    <div class="flex flex-wrap gap-1.5">
                        {#each promptAnalysis.recommendedStrategies as rec}
                            <button
                                type="button"
                                onclick={() => forgeSession.updateDraft({ strategy: rec.name })}
                                class="inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-[10px] font-mono transition-colors
                                    {forgeSession.draft.strategy === rec.name
                                        ? 'border-neon-purple/40 bg-neon-purple/10 text-neon-purple'
                                        : 'border-neon-cyan/15 text-text-secondary hover:border-neon-cyan/30 hover:text-text-primary'}"
                            >
                                <span>{rec.label}</span>
                                <span class="text-[8px] text-text-dim">{Math.round(rec.compositeScore * 100)}%</span>
                            </button>
                        {/each}
                    </div>
                </div>
            {/if}

            <!-- Strategy Section (full picker) -->
            <ForgeStrategySection />

            <!-- Actions -->
            <div class="flex flex-col gap-2">
                <button
                    onclick={handleAnalyze}
                    class="flex items-center justify-center gap-2 rounded bg-neon-cyan/10 px-3 py-2 text-xs font-bold uppercase tracking-wider text-neon-cyan transition-colors hover:bg-neon-cyan/20 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-neon-cyan/10"
                    disabled={!canForge}
                >
                    {#if isAnalyzing}
                        <Icon name="spinner" size={14} class="animate-spin" />
                        Analyzing...
                    {:else}
                        <Icon name="search" size={14} />
                        Analyze Only
                    {/if}
                </button>
                <button
                    onclick={handleForge}
                    class="flex items-center justify-center gap-2 rounded bg-neon-purple/10 px-3 py-2 text-xs font-bold uppercase tracking-wider text-neon-purple transition-colors hover:bg-neon-purple/20 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-neon-purple/10"
                    disabled={!canForge}
                >
                    <Icon name="zap" size={14} />
                    Full Optimization
                </button>
            </div>

            <!-- Analysis preview (standalone analyze result) -->
            <ForgeAnalysisPreview />
        </div>

    {:else if forgeMachine.mode === 'forging'}
        <!-- FORGING MODE: Pipeline progress -->
        <div class="flex flex-col gap-3 p-3">
            <div class="flex items-center justify-between">
                <div class="text-[10px] font-bold uppercase tracking-widest text-text-dim">
                    Pipeline
                </div>
                <button
                    onclick={handleCancelPipeline}
                    class="text-[10px] text-text-dim hover:text-text-primary transition-colors"
                    aria-label="Cancel and return to compose"
                >
                    <Icon name="x" size={12} />
                </button>
            </div>
        </div>
        <ForgePipelineInline />

        <!-- Error recovery: explicit back-to-compose when pipeline errors out -->
        {#if hasError}
            <div class="shrink-0 border-t border-neon-cyan/10 px-3 py-2">
                <button
                    onclick={handleCancelPipeline}
                    class="flex w-full items-center justify-center gap-1.5 rounded bg-bg-hover/50 px-3 py-1.5 text-[10px] font-medium text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                >
                    <Icon name="chevron-left" size={10} />
                    Back to compose
                </button>
            </div>
        {/if}

    {:else if forgeMachine.mode === 'review'}
        <!-- REVIEW MODE: Full result view -->
        <ForgeReview />

    {:else if forgeMachine.mode === 'compare'}
        <!-- COMPARE MODE: Side-by-side comparison -->
        <ForgeCompare />
    {/if}
</div>
