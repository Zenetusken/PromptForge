<script lang="ts">
  interface Props {
    scores: number[];
    width?: number;
    height?: number;
    baseline?: number | null;
    labels?: string[] | null;
  }

  let { scores, width = 120, height = 24, baseline = null, labels = null }: Props = $props();

  const PADDING = 2;

  // Shared scale: computed once, used by polyline, baseline, and tooltips
  const scaleMin = $derived(scores.length >= 2 ? Math.min(...scores) : 0);
  const scaleMax = $derived(scores.length >= 2 ? Math.max(...scores) : 1);
  const scaleRange = $derived(scaleMax - scaleMin || 1);

  function toY(value: number): number {
    return height - PADDING - ((value - scaleMin) / scaleRange) * (height - PADDING * 2);
  }

  const computedPoints = $derived.by(() => {
    if (scores.length < 2) return [];
    const step = (width - PADDING * 2) / (scores.length - 1);
    return scores.map((s, i) => ({
      x: PADDING + i * step,
      y: toY(s),
      score: s,
    }));
  });

  const points = $derived(computedPoints.map(p => `${p.x},${p.y}`).join(' '));

  const baselineY = $derived(
    baseline != null && scores.length >= 2 ? toY(baseline) : null
  );

  // Hit-area radius: larger when fewer points, capped for dense sparklines
  const hitRadius = $derived(
    scores.length >= 2
      ? Math.max(3, Math.min(6, (width - PADDING * 2) / scores.length / 2))
      : 0
  );
</script>

{#if scores.length >= 2}
  <svg
    width={width}
    height={height}
    viewBox="0 0 {width} {height}"
    class="sparkline"
    aria-label="Score progression sparkline"
    role="img"
  >
    {#if baselineY != null}
      <line
        x1={PADDING}
        y1={baselineY}
        x2={width - PADDING}
        y2={baselineY}
        stroke="var(--color-text-dim)"
        stroke-width="0.5"
        stroke-dasharray="2,2"
        opacity="0.6"
      >
        <title>Baseline: {baseline?.toFixed(2)}</title>
      </line>
    {/if}
    <polyline
      points={points}
      fill="none"
      stroke="var(--tier-accent, var(--color-neon-cyan))"
      stroke-width="1.5"
      stroke-linejoin="round"
      stroke-linecap="round"
    />
    {#each computedPoints as pt, i}
      <circle
        cx={pt.x}
        cy={pt.y}
        r={hitRadius}
        fill="transparent"
        stroke="none"
        class="sparkline-hitarea"
      >
        <title>{labels?.[i] ?? pt.score.toFixed(2)}</title>
      </circle>
    {/each}
  </svg>
{/if}

<style>
  .sparkline {
    display: block;
    flex-shrink: 0;
  }

  .sparkline-hitarea {
    pointer-events: all;
    cursor: default;
  }
</style>
