<script lang="ts">
  import { forgeStore } from '$lib/stores/forge.svelte';
  import { refinementStore } from '$lib/stores/refinement.svelte';
  import ScoreCard from '$lib/components/shared/ScoreCard.svelte';
  import ScoreSparkline from '$lib/components/refinement/ScoreSparkline.svelte';

  const PHASE_LABELS: Record<string, string> = {
    analyzing: 'Analyzing',
    optimizing: 'Optimizing',
    scoring: 'Scoring',
  };

  const isPassthrough = $derived(forgeStore.status === 'passthrough');
  const isHeuristicScored = $derived(forgeStore.result?.scoring_mode === 'heuristic');

  // Sync feedback state from real-time events (e.g. MCP or cross-tab submissions)
  $effect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.optimization_id && detail.optimization_id === forgeStore.result?.id) {
        forgeStore.feedback = detail.rating;
      }
    };
    window.addEventListener('feedback-event', handler);
    return () => window.removeEventListener('feedback-event', handler);
  });
</script>

<aside
  class="inspector"
  aria-label="Inspector panel"
  style="background: var(--color-bg-secondary); border-left: 1px solid var(--color-border-subtle);"
>
  <!-- Header -->
  <div class="inspector-header">
    <span class="section-heading">Inspector</span>
  </div>

  <!-- Body -->
  <div class="inspector-body">

    {#if forgeStore.status === 'idle'}
      <!-- Empty state -->
      <div class="empty-state">
        <span class="empty-text">Enter a prompt and synthesize</span>
      </div>

    {:else if forgeStore.status === 'analyzing' || forgeStore.status === 'optimizing' || forgeStore.status === 'scoring'}
      <!-- Active phase -->
      <div class="phase-state">
        <div class="spinner" aria-label="Processing" role="status"></div>
        <span class="phase-label">
          {PHASE_LABELS[forgeStore.status] ?? forgeStore.status}
        </span>
        {#if forgeStore.currentPhase}
          <span class="phase-detail">{forgeStore.currentPhase}</span>
        {/if}
      </div>

    {:else if isPassthrough}
      <!-- Passthrough — awaiting external LLM result -->
      <div class="passthrough-state">
        <span class="passthrough-icon" aria-hidden="true">&#8644;</span>
        <span class="passthrough-label">Manual passthrough</span>
        <span class="passthrough-detail">
          {#if forgeStore.assembledPrompt}
            Copy the assembled prompt to your LLM, then paste the result back.
          {:else}
            Preparing prompt...
          {/if}
        </span>
        {#if forgeStore.passthroughStrategy}
          <span class="passthrough-strategy">{forgeStore.passthroughStrategy}</span>
        {/if}
      </div>

    {:else if forgeStore.status === 'complete'}
      <!-- Complete — scores + strategy -->
      <div class="complete-state">

        {#if forgeStore.scores}
          <ScoreCard
            scores={forgeStore.scores}
            originalScores={forgeStore.originalScores}
            deltas={forgeStore.scoreDeltas}
            overallScore={forgeStore.result?.overall_score ?? null}
          />
        {:else}
          <div class="scoring-disabled">
            <span class="scoring-disabled-label">Scoring</span>
            <span class="scoring-disabled-value">disabled</span>
          </div>
        {/if}

        <!-- Strategy + scoring mode metadata -->
        <div class="meta-section">
          {#if forgeStore.result?.strategy_used}
            <div class="meta-row">
              <span class="meta-label">Strategy</span>
              <span class="meta-value meta-value--cyan">{forgeStore.result.strategy_used}</span>
            </div>
          {/if}
          {#if isHeuristicScored}
            <div class="meta-row">
              <span class="meta-label">Scoring</span>
              <span class="meta-value meta-value--yellow">heuristic</span>
            </div>
          {/if}
          {#if forgeStore.result?.provider}
            <div class="meta-row">
              <span class="meta-label">Provider</span>
              <span class="meta-value">{forgeStore.result.provider}</span>
            </div>
          {/if}
        </div>

        {#if refinementStore.scoreProgression.length >= 2}
          <div class="sparkline-section">
            <div class="section-heading" style="margin-bottom: 4px;">Score Trend</div>
            <ScoreSparkline scores={refinementStore.scoreProgression} />
            <span class="sparkline-label">{refinementStore.turns.length} versions</span>
          </div>
        {/if}

      </div>

    {:else if forgeStore.status === 'error'}
      <div class="error-state">
        <span class="error-icon" aria-hidden="true">!</span>
        <span class="error-text">{forgeStore.error ?? 'Unknown error'}</span>
      </div>
    {/if}

  </div>
</aside>

<style>
  .inspector {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .inspector-header {
    display: flex;
    align-items: center;
    height: 24px;
    padding: 0 6px;
    border-bottom: 1px solid var(--color-border-subtle);
    flex-shrink: 0;
  }

  .inspector-body {
    flex: 1;
    overflow-y: auto;
    padding: 6px;
  }

  /* Empty state */
  .empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 80px;
  }

  .empty-text {
    font-size: 11px;
    color: var(--color-text-dim);
    font-family: var(--font-sans);
    text-align: center;
  }

  /* Phase / spinner state */
  .phase-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 6px 0;
  }

  .spinner {
    width: 20px;
    height: 20px;
    border: 1px solid var(--color-border-subtle);
    border-top-color: var(--color-neon-cyan);
    animation: spin 800ms linear infinite;
    flex-shrink: 0;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .phase-label {
    font-size: 11px;
    color: var(--color-text-secondary);
    font-family: var(--font-sans);
  }

  .phase-detail {
    font-size: 10px;
    color: var(--color-text-dim);
    font-family: var(--font-mono);
  }

  /* Passthrough state */
  .passthrough-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    padding: 6px 0;
  }

  .passthrough-icon {
    font-size: 16px;
    color: var(--color-neon-yellow);
    font-family: var(--font-mono);
  }

  .passthrough-label {
    font-size: 11px;
    color: var(--color-neon-yellow);
    font-family: var(--font-sans);
  }

  .passthrough-detail {
    font-size: 10px;
    color: var(--color-text-dim);
    font-family: var(--font-sans);
    text-align: center;
    line-height: 1.4;
    padding: 0 6px;
  }

  .passthrough-strategy {
    font-size: 10px;
    color: var(--color-text-dim);
    font-family: var(--font-mono);
  }

  /* Complete state */
  .complete-state {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  /* Metadata rows (strategy, scoring mode, provider) */
  .meta-section {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .meta-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 2px 6px;
    background: var(--color-bg-card);
    border: 1px solid var(--color-border-subtle);
  }

  .meta-label {
    font-size: 10px;
    font-family: var(--font-sans);
    color: var(--color-text-dim);
  }

  .meta-value {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--color-text-secondary);
  }

  .meta-value--cyan {
    color: var(--color-neon-cyan);
  }

  .meta-value--yellow {
    color: var(--color-neon-yellow);
  }

  /* Error state */
  .error-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 6px 0;
  }

  .error-icon {
    font-size: 16px;
    font-weight: bold;
    color: var(--color-neon-red);
    font-family: var(--font-mono);
  }

  .error-text {
    font-size: 10px;
    color: var(--color-text-dim);
    font-family: var(--font-sans);
    text-align: center;
    word-break: break-word;
  }

  /* Scoring disabled state */
  .scoring-disabled {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px;
    background: var(--color-bg-card);
    border: 1px solid var(--color-border-subtle);
  }

  .scoring-disabled-label {
    font-size: 10px;
    font-family: var(--font-sans);
    color: var(--color-text-dim);
  }

  .scoring-disabled-value {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--color-neon-yellow);
  }

  /* Sparkline section */
  .sparkline-section {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .sparkline-label {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--color-text-dim);
  }
</style>
