<script lang="ts">
  import { forge } from '$lib/stores/forge.svelte';

  // Typed shapes for the two store fields this component reads
  interface RetryDiagnostics {
    attempt: number;
    overall_score: number;
    threshold: number;
    action: 'accept' | 'accept_best' | 'retry';
    reason: string;
    focus_areas: string[];
    gate: string;
    momentum?: number;
    best_attempt_index?: number;
  }

  interface RetryBestSelected {
    best_attempt_index: number;
    best_score: number;
    reason: string;
  }

  let diag = $derived(forge.retryDiagnostics as RetryDiagnostics | null);
  let best = $derived(forge.retryBestSelected as RetryBestSelected | null);

  // Bar geometry: score and threshold clamped to [0, 10] then mapped to [0%, 100%]
  let scorePercent = $derived(
    diag != null ? Math.min(100, Math.max(0, (diag.overall_score / 10) * 100)) : 0
  );
  let thresholdPercent = $derived(
    diag != null ? Math.min(100, Math.max(0, (diag.threshold / 10) * 100)) : 0
  );

  // Decision color class: yellow for retry, green for accept/accept_best
  let decisionColorClass = $derived(
    diag?.action === 'retry' ? 'text-neon-yellow' : 'text-neon-green'
  );

  let decisionLabel = $derived(
    diag?.action === 'retry'
      ? 'RETRY'
      : diag?.action === 'accept_best'
        ? 'ACCEPT_BEST'
        : 'ACCEPT'
  );
</script>

{#if diag != null}
  <div class="space-y-2 text-xs" data-testid="retry-diagnostics">

    <!-- Row 1: Attempt counter + Gate label -->
    <div class="flex items-center justify-between">
      <span class="font-mono text-[10px] text-neon-cyan">
        Attempt {diag.attempt}
      </span>
      <span class="font-mono text-[10px] text-text-dim">
        gate:{diag.gate}
      </span>
    </div>

    <!-- Row 2: Score vs Threshold bar -->
    <div>
      <div class="flex justify-between mb-1">
        <span class="font-mono text-[10px] text-text-dim">score vs threshold</span>
        <span class="font-mono text-[10px] text-text-secondary">
          {diag.overall_score.toFixed(1)} / {diag.threshold.toFixed(1)}
        </span>
      </div>
      <div
        class="relative w-full h-2 bg-border-subtle/40"
        role="meter"
        aria-valuenow={diag.overall_score}
        aria-valuemin={0}
        aria-valuemax={10}
        aria-label="Score {diag.overall_score.toFixed(1)} vs threshold {diag.threshold.toFixed(1)}"
      >
        <!-- Score fill bar -->
        <div
          class="absolute top-0 left-0 h-full bg-neon-cyan"
          style="width: {scorePercent}%;"
        ></div>

        <!-- Threshold marker: 1px vertical line in neon-yellow -->
        <div
          class="absolute top-0 h-full w-px bg-neon-yellow"
          style="left: {thresholdPercent}%;"
          aria-hidden="true"
        ></div>

        <!-- Score position dot -->
        <div
          class="absolute top-1/2 w-1.5 h-1.5 bg-neon-cyan"
          style="left: {scorePercent}%; transform: translate(-50%, -50%);"
          aria-hidden="true"
        ></div>
      </div>
    </div>

    <!-- Row 3: Decision line -->
    <div class="flex items-center gap-2">
      <span class="font-mono text-[10px] text-text-dim">decision</span>
      <span
        class="font-mono text-[11px] font-bold {decisionColorClass}"
      >
        {decisionLabel}
      </span>
      {#if diag.momentum != null}
        <span class="font-mono text-[10px] text-text-dim">
          momentum:{diag.momentum > 0 ? '+' : ''}{diag.momentum.toFixed(2)}
        </span>
      {/if}
    </div>

    <!-- Row 4: Reason -->
    {#if diag.reason}
      <p class="font-mono text-[10px] leading-relaxed text-text-secondary">
        {diag.reason}
      </p>
    {/if}

    <!-- Row 5: Focus area chips -->
    {#if diag.focus_areas.length > 0}
      <div class="flex flex-wrap gap-1">
        {#each diag.focus_areas as area}
          <span
            class="px-1.5 py-0.5 font-mono text-[10px] border border-neon-yellow/60 text-neon-yellow bg-neon-yellow/5"
          >
            {area}
          </span>
        {/each}
      </div>
    {/if}

    <!-- Row 6: Best-of-N selected indicator -->
    {#if best != null}
      <div
        class="flex items-center gap-2 px-2 py-1 border border-neon-green/30 bg-neon-green/4"
        data-testid="retry-best-selected"
      >
        <span class="font-mono text-[10px] font-bold text-neon-green">
          Best of {best.best_attempt_index + 1} selected
        </span>
        <span class="font-mono text-[10px] text-text-dim">
          score {best.best_score.toFixed(1)}
        </span>
      </div>
    {/if}

  </div>
{/if}
