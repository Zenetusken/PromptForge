<script lang="ts">
  import { clustersStore } from '$lib/stores/clusters.svelte';
  import { TAXONOMY_TOOLTIPS } from '$lib/utils/metric-tooltips';
  import { tooltip } from '$lib/actions/tooltip';
  import { TOPOLOGY_TOOLTIPS } from '$lib/utils/ui-tooltips';
  import { generatePanelInsight } from '$lib/utils/taxonomy-health';
  import type { PanelMode } from '$lib/utils/taxonomy-health';
  import TopologyInfoPanel from './TopologyInfoPanel.svelte';
  import type { LODTier } from './TopologyRenderer';

  interface Props {
    lodTier: LODTier;
    showActivity: boolean;
    onSearch: (query: string) => void;
    onRecluster: () => Promise<void>;
    onToggleActivity: () => void;
    onSeed: () => void;
  }

  let { lodTier, showActivity, onSearch, onRecluster, onToggleActivity, onSeed }: Props = $props();

  let searchQuery = $state('');
  let searchOpen = $state(false);
  let reclustering = $state(false);

  // Canonical state breakdown from the store (respects orphan filter + state filter)
  const filteredCounts = $derived(clustersStore.clusterCounts);

  // Insight text — generated here so it can be positioned independently (top-left)
  const detail = $derived(clustersStore.clusterDetail);
  const selectedId = $derived(clustersStore.selectedClusterId);
  const mode: PanelMode = $derived.by(() => {
    if (!selectedId || !detail) return 'system';
    if (detail.state === 'domain') return 'domain';
    return 'cluster';
  });
  const insight = $derived(generatePanelInsight({
    mode,
    stats: clustersStore.taxonomyStats,
    detail: detail ? {
      coherence: detail.coherence,
      separation: detail.separation,
      output_coherence: detail.output_coherence ?? null,
      blend_w_optimized: detail.blend_w_optimized ?? null,
      member_count: detail.member_count,
      split_failures: detail.split_failures ?? 0,
      label: detail.label,
      state: detail.state,
    } : null,
    domainChildCount: (detail?.children ?? []).length,
    domainBelowFloor: (detail?.children ?? []).filter(c => c.coherence != null && c.coherence < 0.5).length,
  }));

  function handleSearch(): void {
    if (searchQuery.trim()) {
      onSearch(searchQuery.trim());
    }
  }

  function handleKeyDown(e: KeyboardEvent): void {
    if (e.key === 'Enter') handleSearch();
    if (e.key === 'Escape') {
      searchOpen = false;
      searchQuery = '';
    }
  }

  async function handleRecluster(): Promise<void> {
    reclustering = true;
    try {
      await onRecluster();
    } finally {
      reclustering = false;
    }
  }

  function handleGlobalKey(e: KeyboardEvent): void {
    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
      e.preventDefault();
      searchOpen = true;
    }
  }
</script>

<svelte:window onkeydown={handleGlobalKey} />

<!-- HUD — 4-corner distributed overlay -->
<div class="hud">
  <!-- TOP-RIGHT: Metrics readout -->
  <div class="hud-tr">
    <TopologyInfoPanel hideInsight />
  </div>

  <!-- TOP-LEFT: Insight callout -->
  {#if insight}
    <div class="hud-tl">
      <p class="hud-insight">{insight}</p>
    </div>
  {/if}

  <!-- BOTTOM-RIGHT: Controls -->
  <div class="hud-br">
    <div class="hud-row">
      <button class="hud-btn" class:hud-btn--on={clustersStore.showSimilarityEdges} style="--hud-accent: var(--color-neon-cyan)" onclick={() => { clustersStore.showSimilarityEdges = !clustersStore.showSimilarityEdges; }} use:tooltip={TOPOLOGY_TOOLTIPS.toggle_similarity}>Sim</button>
      <button class="hud-btn" class:hud-btn--on={clustersStore.showInjectionEdges} style="--hud-accent: var(--color-neon-orange)" onclick={() => { clustersStore.showInjectionEdges = !clustersStore.showInjectionEdges; }} use:tooltip={TOPOLOGY_TOOLTIPS.toggle_injection}>Inj</button>
    </div>
    <div class="hud-row">
      <button class="hud-btn" onclick={onSeed} use:tooltip={'Seed taxonomy with generated prompts'}>Seed</button>
      <button class="hud-btn" onclick={handleRecluster} disabled={reclustering} use:tooltip={TOPOLOGY_TOOLTIPS.recluster}>{reclustering ? '...' : 'Recluster'}</button>
    </div>
    <div class="hud-row">
      <button class="hud-btn" class:hud-btn--on={showActivity} style="--hud-accent: var(--color-neon-purple)" onclick={onToggleActivity} use:tooltip={'Toggle taxonomy decision feed'}>Activity</button>
    </div>
  </div>

  <!-- BOTTOM-LEFT: Status telemetry -->
  <div class="hud-bl">
    <span class="hud-count" use:tooltip={TAXONOMY_TOOLTIPS.active}>{filteredCounts.active} active</span>
    {#if filteredCounts.candidate > 0}
      <span class="hud-sep"></span>
      <span class="hud-count hud-count--candidate" use:tooltip={TAXONOMY_TOOLTIPS.candidate}>{filteredCounts.candidate} forming</span>
    {/if}
    {#if filteredCounts.template > 0}
      <span class="hud-sep"></span>
      <span class="hud-count" use:tooltip={TAXONOMY_TOOLTIPS.template}>{filteredCounts.template} tmpl</span>
    {/if}
    <span class="hud-sep"></span>
    <span class="hud-lod" use:tooltip={'Level of detail'}>{lodTier.toUpperCase()}</span>
  </div>

  <!-- CENTER-TOP: Search (Ctrl+F) -->
  {#if searchOpen}
    <div class="hud-search">
      <input
        type="text"
        bind:value={searchQuery}
        onkeydown={handleKeyDown}
        placeholder="Search nodes..."
        class="hud-search-input"
      />
    </div>
  {/if}
</div>

<style>
  /* ══ HUD — 4-corner distributed overlay ══ */

  .hud {
    position: absolute;
    inset: 0;
    pointer-events: none;
    z-index: 10;
  }

  /* ── TOP-RIGHT: Metrics readout ── */

  .hud-tr {
    position: absolute;
    top: 8px;
    right: 8px;
    width: 178px;
    pointer-events: auto;
    background: color-mix(in srgb, var(--color-bg-primary) 75%, transparent);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
  }

  /* ── TOP-LEFT: Insight callout ── */

  .hud-tl {
    position: absolute;
    top: 8px;
    left: 8px;
    max-width: 220px;
    pointer-events: none;
  }

  .hud-insight {
    font-family: var(--font-sans);
    font-size: 10px;
    color: color-mix(in srgb, var(--color-text-dim) 70%, transparent);
    line-height: 1.5;
    margin: 0;
  }

  /* ── BOTTOM-RIGHT: Controls ── */

  .hud-br {
    position: absolute;
    bottom: 8px;
    right: 8px;
    width: 178px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 4px 6px;
    pointer-events: auto;
    background: color-mix(in srgb, var(--color-bg-primary) 75%, transparent);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
  }

  .hud-row {
    display: flex;
    gap: 2px;
  }

  .hud-btn {
    display: flex;
    flex: 1;
    align-items: center;
    justify-content: center;
    height: 22px;
    padding: 0 6px;
    background: transparent;
    border: 1px solid color-mix(in srgb, var(--color-border-subtle) 25%, transparent);
    color: var(--color-text-dim);
    font-family: var(--font-mono);
    font-size: 9px;
    cursor: pointer;
    transition: border-color 150ms cubic-bezier(0.16, 1, 0.3, 1),
                color 150ms cubic-bezier(0.16, 1, 0.3, 1),
                background 150ms cubic-bezier(0.16, 1, 0.3, 1);
  }

  .hud-btn:hover:not(:disabled) {
    border-color: color-mix(in srgb, var(--hud-accent, var(--color-neon-cyan)) 40%, transparent);
    color: var(--color-text-secondary);
  }

  .hud-btn--on {
    border-color: color-mix(in srgb, var(--hud-accent, var(--color-neon-cyan)) 50%, transparent);
    color: var(--color-text-primary);
    background: color-mix(in srgb, var(--hud-accent, var(--color-neon-cyan)) 6%, transparent);
  }

  .hud-btn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }

  /* ── BOTTOM-LEFT: Status telemetry ── */

  .hud-bl {
    position: absolute;
    bottom: 8px;
    left: 8px;
    display: flex;
    align-items: center;
    gap: 5px;
    pointer-events: auto;
    font-family: var(--font-mono);
    font-size: 9px;
    color: color-mix(in srgb, var(--color-text-dim) 70%, transparent);
  }

  .hud-count { cursor: default; }
  .hud-count--candidate { color: #7a7a9e; }

  .hud-sep {
    width: 1px;
    height: 8px;
    background: color-mix(in srgb, var(--color-text-dim) 20%, transparent);
    flex-shrink: 0;
  }

  .hud-lod {
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 0.08em;
  }

  /* ── CENTER-TOP: Search ── */

  .hud-search {
    position: absolute;
    top: 8px;
    left: 50%;
    transform: translateX(-50%);
    width: 240px;
    pointer-events: auto;
  }

  .hud-search-input {
    width: 100%;
    padding: 4px 8px;
    background: color-mix(in srgb, var(--color-bg-primary) 88%, transparent);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    border: 1px solid color-mix(in srgb, var(--color-neon-cyan) 25%, transparent);
    color: var(--color-text-primary);
    font-family: var(--font-mono);
    font-size: 11px;
    outline: none;
    text-align: center;
  }

  .hud-search-input:focus {
    border-color: color-mix(in srgb, var(--color-neon-cyan) 50%, transparent);
  }

  .hud-search-input::placeholder {
    color: var(--color-text-dim);
    opacity: 0.4;
  }
</style>
