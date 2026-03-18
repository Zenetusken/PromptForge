<script lang="ts">
  import { forgeStore } from '$lib/stores/forge.svelte';
  import { refinementStore } from '$lib/stores/refinement.svelte';
  import { patternsStore } from '$lib/stores/patterns.svelte';
  import { editorStore } from '$lib/stores/editor.svelte';
  import ScoreCard from '$lib/components/shared/ScoreCard.svelte';
  import ScoreSparkline from '$lib/components/refinement/ScoreSparkline.svelte';

  const PHASE_LABELS: Record<string, string> = {
    analyzing: 'Analyzing',
    optimizing: 'Optimizing',
    scoring: 'Scoring',
  };

  const DOMAIN_COLORS: Record<string, string> = {
    backend: '#a855f7',
    frontend: '#f59e0b',
    database: '#10b981',
    security: '#ef4444',
    devops: '#3b82f6',
    fullstack: '#00e5ff',
    general: '#6b7280',
  };

  const isPassthrough = $derived(forgeStore.status === 'passthrough');
  const isHeuristicScored = $derived(forgeStore.result?.scoring_mode === 'heuristic');
  const showFamilyDetail = $derived(patternsStore.selectedFamilyId !== null);

  function domainColor(domain: string): string {
    return DOMAIN_COLORS[domain] ?? DOMAIN_COLORS.general;
  }

  function truncatePrompt(text: string, maxLen = 80): string {
    if (text.length <= maxLen) return text;
    return text.slice(0, maxLen).trimEnd() + '...';
  }

  function formatScore(score: number | null): string {
    if (score === null) return '--';
    return score.toFixed(1);
  }

  function openOptimization(id: string): void {
    editorStore.openResult(id);
  }

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

    {#if showFamilyDetail}
      <!-- Pattern family detail -->
      <div class="family-detail">
        {#if patternsStore.familyDetailLoading}
          <div class="phase-state">
            <div class="spinner" aria-label="Loading family" role="status"></div>
            <span class="phase-label">Loading family...</span>
          </div>

        {:else if patternsStore.familyDetailError}
          <div class="error-state">
            <span class="error-icon" aria-hidden="true">!</span>
            <span class="error-text">{patternsStore.familyDetailError}</span>
          </div>

        {:else if patternsStore.familyDetail}
          {@const family = patternsStore.familyDetail}

          <!-- Family header -->
          <div class="family-header">
            <span class="family-intent">{family.intent_label}</span>
            <span
              class="domain-badge"
              style="background: {domainColor(family.domain)};"
            >{family.domain}</span>
          </div>

          <!-- Stats row -->
          <div class="meta-section">
            <div class="meta-row">
              <span class="meta-label">Usage</span>
              <span class="meta-value meta-value--cyan">{family.usage_count}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">Members</span>
              <span class="meta-value">{family.member_count}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">Avg Score</span>
              <span class="meta-value meta-value--cyan">{formatScore(family.avg_score)}</span>
            </div>
          </div>

          <!-- Meta-patterns -->
          {#if family.meta_patterns.length > 0}
            <div class="family-section">
              <div class="section-heading" style="margin-bottom: 4px;">Meta-patterns</div>
              <div class="pattern-list">
                {#each family.meta_patterns as mp (mp.id)}
                  <div class="pattern-item">
                    <span class="pattern-text">{mp.pattern_text}</span>
                    <span class="source-badge">{mp.source_count}</span>
                  </div>
                {/each}
              </div>
            </div>
          {/if}

          <!-- Linked optimizations -->
          {#if family.optimizations.length > 0}
            <div class="family-section">
              <div class="section-heading" style="margin-bottom: 4px;">Linked Optimizations</div>
              <div class="opt-list">
                {#each family.optimizations.slice(0, 10) as opt (opt.id)}
                  <button
                    class="opt-item"
                    onclick={() => openOptimization(opt.id)}
                    title={opt.raw_prompt}
                  >
                    <span class="opt-prompt">{truncatePrompt(opt.raw_prompt)}</span>
                    <span class="opt-score" class:opt-score--null={opt.overall_score === null}>
                      {formatScore(opt.overall_score)}
                    </span>
                  </button>
                {/each}
              </div>
            </div>
          {/if}
        {/if}
      </div>

    {:else if forgeStore.status === 'idle'}
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

  /* Pattern family detail */
  .family-detail {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .family-header {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  .family-intent {
    font-size: 12px;
    font-family: var(--font-display);
    color: var(--color-text-primary);
    letter-spacing: 0.02em;
    line-height: 1.3;
  }

  .domain-badge {
    display: inline-block;
    font-size: 9px;
    font-family: var(--font-mono);
    color: #06060c;
    padding: 1px 5px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    flex-shrink: 0;
  }

  /* Family sub-sections */
  .family-section {
    display: flex;
    flex-direction: column;
  }

  /* Meta-patterns list */
  .pattern-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .pattern-item {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 6px;
    padding: 3px 6px;
    background: var(--color-bg-card);
    border: 1px solid var(--color-border-subtle);
  }

  .pattern-text {
    font-size: 10px;
    font-family: var(--font-sans);
    color: var(--color-text-secondary);
    line-height: 1.4;
    flex: 1;
    min-width: 0;
  }

  .source-badge {
    font-size: 9px;
    font-family: var(--font-mono);
    color: var(--color-neon-cyan);
    background: var(--color-bg-secondary);
    border: 1px solid var(--color-border-subtle);
    padding: 0 4px;
    flex-shrink: 0;
    line-height: 1.6;
  }

  /* Linked optimizations list */
  .opt-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .opt-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
    padding: 3px 6px;
    background: var(--color-bg-card);
    border: 1px solid var(--color-border-subtle);
    cursor: pointer;
    text-align: left;
    width: 100%;
    font: inherit;
    color: inherit;
    transition: border-color 100ms;
  }

  .opt-item:hover {
    border-color: var(--color-neon-cyan);
  }

  .opt-prompt {
    font-size: 10px;
    font-family: var(--font-sans);
    color: var(--color-text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
    min-width: 0;
  }

  .opt-score {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--color-neon-cyan);
    flex-shrink: 0;
  }

  .opt-score--null {
    color: var(--color-text-dim);
  }
</style>
