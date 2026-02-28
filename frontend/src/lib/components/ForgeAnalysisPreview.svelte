<script lang="ts">
    import { optimizationState, type AnalysisStepData } from "$lib/stores/optimization.svelte";
    import { MetaBadge } from "./ui";
    import Icon from "./Icon.svelte";

    let analysis = $derived(optimizationState.analysisResult);

    function dismiss() {
        optimizationState.clearAnalysis();
    }
</script>

{#if analysis}
    {@const data = analysis as AnalysisStepData}
    <div class="animate-fade-in flex flex-col gap-1.5 rounded border border-neon-cyan/10 bg-bg-card/50 p-2">
        <!-- Header -->
        <div class="flex items-center justify-between">
            <span class="text-[10px] font-bold uppercase tracking-widest text-neon-cyan">Analysis</span>
            <button
                type="button"
                onclick={dismiss}
                class="text-text-dim transition-colors hover:text-text-primary"
                aria-label="Dismiss analysis"
            >
                <Icon name="x" size={12} />
            </button>
        </div>

        <!-- Classification badges -->
        <div class="flex flex-wrap items-center gap-1.5">
            {#if data.task_type}
                <MetaBadge type="task" value={data.task_type} size="xs" />
            {/if}
            {#if data.complexity}
                <MetaBadge type="complexity" value={data.complexity} size="xs" variant="pill" />
            {/if}
            {#if data.step_duration_ms}
                <span class="text-[9px] font-mono text-text-dim">
                    {(data.step_duration_ms / 1000).toFixed(1)}s
                </span>
            {/if}
        </div>

        <!-- Strengths -->
        {#if Array.isArray(data.strengths) && data.strengths.length > 0}
            <div class="flex flex-col gap-1.5">
                <span class="text-[10px] font-medium uppercase tracking-wider text-neon-green">Strengths ({data.strengths.length})</span>
                <ul class="flex flex-col gap-0.5">
                    {#each data.strengths as strength}
                        <li class="flex items-start gap-1.5 text-[11px] leading-snug text-text-secondary">
                            <span class="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-neon-green"></span>
                            {strength}
                        </li>
                    {/each}
                </ul>
            </div>
        {/if}

        <!-- Weaknesses -->
        {#if Array.isArray(data.weaknesses) && data.weaknesses.length > 0}
            <div class="flex flex-col gap-1.5">
                <span class="text-[10px] font-medium uppercase tracking-wider text-neon-red">Weaknesses ({data.weaknesses.length})</span>
                <ul class="flex flex-col gap-0.5">
                    {#each data.weaknesses as weakness}
                        <li class="flex items-start gap-1.5 text-[11px] leading-snug text-text-secondary">
                            <span class="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-neon-red"></span>
                            {weakness}
                        </li>
                    {/each}
                </ul>
            </div>
        {/if}
    </div>
{/if}
