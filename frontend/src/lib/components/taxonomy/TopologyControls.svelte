<script lang="ts">
  import { clustersStore } from '$lib/stores/clusters.svelte';
  import { TAXONOMY_TOOLTIPS } from '$lib/utils/metric-tooltips';
  import { tooltip } from '$lib/actions/tooltip';
  import { TOPOLOGY_TOOLTIPS } from '$lib/utils/ui-tooltips';
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

<!-- HUD — right-edge instrument cluster -->
<div class="hud">
  <!-- Primary instrument cluster: metrics + controls -->
  <div class="hud-cluster">
    <!-- Metrics readout -->
    <div class="hud-block hud-metrics">
      <TopologyInfoPanel />
    </div>

    <!-- Layers + commands -->
    <div class="hud-block hud-controls">
      <div class="hud-row">
        <button
          class="hud-toggle"
          class:hud-toggle--on={clustersStore.showSimilarityEdges}
          style="--hud-accent: var(--color-neon-cyan)"
          onclick={() => { clustersStore.showSimilarityEdges = !clustersStore.showSimilarityEdges; }}
          use:tooltip={TOPOLOGY_TOOLTIPS.toggle_similarity}
        >
          <span class="hud-indicator"></span>
          Sim
        </button>
        <button
          class="hud-toggle"
          class:hud-toggle--on={clustersStore.showInjectionEdges}
          style="--hud-accent: var(--color-neon-orange)"
          onclick={() => { clustersStore.showInjectionEdges = !clustersStore.showInjectionEdges; }}
          use:tooltip={TOPOLOGY_TOOLTIPS.toggle_injection}
        >
          <span class="hud-indicator"></span>
          Inj
        </button>
      </div>
      <div class="hud-row">
        <button class="hud-cmd" onclick={onSeed} use:tooltip={'Seed taxonomy with generated prompts'}>
          Seed
        </button>
        <button
          class="hud-cmd"
          onclick={handleRecluster}
          disabled={reclustering}
          use:tooltip={TOPOLOGY_TOOLTIPS.recluster}
        >
          {reclustering ? '...' : 'Recluster'}
        </button>
        <span class="hud-lod" use:tooltip={'Level of detail'}>{lodTier.toUpperCase()}</span>
      </div>
      <button
        class="hud-toggle hud-toggle--wide"
        class:hud-toggle--on={showActivity}
        style="--hud-accent: var(--color-neon-purple)"
        onclick={onToggleActivity}
        use:tooltip={'Toggle taxonomy decision feed'}
      >
        <span class="hud-indicator"></span>
        Activity
      </button>
    </div>

    <!-- Status telemetry -->
    <div class="hud-block hud-status">
      <span class="hud-count" use:tooltip={TAXONOMY_TOOLTIPS.active}>{filteredCounts.active} active</span>
      {#if filteredCounts.candidate > 0}
        <span class="hud-sep"></span>
        <span class="hud-count hud-count--candidate" use:tooltip={TAXONOMY_TOOLTIPS.candidate}>{filteredCounts.candidate} forming</span>
      {/if}
      {#if filteredCounts.template > 0}
        <span class="hud-sep"></span>
        <span class="hud-count" use:tooltip={TAXONOMY_TOOLTIPS.template}>{filteredCounts.template} tmpl</span>
      {/if}
      <span class="hud-fill"></span>
      <span class="hud-legend">wire=coh sat=score</span>
    </div>
  </div>

  <!-- Search overlay (Ctrl+F) -->
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
  /* ══ HUD — right-edge instrument cluster ══
   *
   * Single vertical column anchored top-right. Blocks stack with
   * 2px gaps — tight enough to read as one unit, loose enough to
   * show graph between blocks. Each block is semi-transparent with
   * backdrop-blur. No outer container border.
   */

  .hud {
    position: absolute;
    inset: 0;
    pointer-events: none;
    z-index: 10;
  }

  /* ── Instrument cluster — right-aligned vertical stack ── */

  .hud-cluster {
    position: absolute;
    top: 6px;
    right: 6px;
    width: 178px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    pointer-events: auto;
  }

  /* ── Individual HUD blocks ── */

  .hud-block {
    background: color-mix(in srgb, var(--color-bg-primary) 75%, transparent);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
    border-left: 1px solid color-mix(in srgb, var(--color-neon-cyan) 12%, transparent);
  }

  /* ── Metrics readout ── */

  .hud-metrics {
    /* InfoPanel manages its own padding */
  }

  /* ── Controls block ── */

  .hud-controls {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 4px 6px;
  }

  .hud-row {
    display: flex;
    gap: 2px;
  }

  /* ── Toggle buttons ── */

  .hud-toggle {
    display: flex;
    align-items: center;
    gap: 3px;
    flex: 1;
    padding: 2px 5px;
    background: transparent;
    border: 1px solid color-mix(in srgb, var(--color-border-subtle) 30%, transparent);
    color: var(--color-text-dim);
    font-family: var(--font-mono);
    font-size: 9px;
    cursor: pointer;
    transition: border-color 150ms cubic-bezier(0.16, 1, 0.3, 1),
                color 150ms cubic-bezier(0.16, 1, 0.3, 1),
                background 150ms cubic-bezier(0.16, 1, 0.3, 1);
  }

  .hud-toggle:hover {
    border-color: color-mix(in srgb, var(--hud-accent, var(--color-neon-cyan)) 40%, transparent);
    color: var(--color-text-secondary);
  }

  .hud-toggle--on {
    border-color: color-mix(in srgb, var(--hud-accent, var(--color-neon-cyan)) 50%, transparent);
    color: var(--color-text-primary);
    background: color-mix(in srgb, var(--hud-accent, var(--color-neon-cyan)) 6%, transparent);
  }

  .hud-toggle--wide {
    width: 100%;
  }

  .hud-indicator {
    width: 4px;
    height: 4px;
    flex-shrink: 0;
    background: var(--hud-accent, var(--color-neon-cyan));
    opacity: 0.25;
    transition: opacity 150ms cubic-bezier(0.16, 1, 0.3, 1);
  }

  .hud-toggle--on .hud-indicator {
    opacity: 1;
  }

  /* ── Command buttons ── */

  .hud-cmd {
    flex: 1;
    padding: 2px 4px;
    background: transparent;
    border: 1px solid color-mix(in srgb, var(--color-border-subtle) 30%, transparent);
    color: var(--color-text-dim);
    font-family: var(--font-mono);
    font-size: 9px;
    cursor: pointer;
    text-align: center;
    transition: border-color 150ms cubic-bezier(0.16, 1, 0.3, 1),
                color 150ms cubic-bezier(0.16, 1, 0.3, 1),
                background 150ms cubic-bezier(0.16, 1, 0.3, 1);
  }

  .hud-cmd:hover:not(:disabled) {
    border-color: color-mix(in srgb, var(--color-neon-cyan) 40%, transparent);
    color: var(--color-neon-cyan);
    background: color-mix(in srgb, var(--color-neon-cyan) 5%, transparent);
  }

  .hud-cmd:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }

  .hud-lod {
    font-family: var(--font-mono);
    font-size: 8px;
    font-weight: 700;
    color: var(--color-text-dim);
    padding: 2px 4px;
    letter-spacing: 0.08em;
    flex-shrink: 0;
  }

  /* ── Status telemetry ── */

  .hud-status {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 3px 6px;
    font-family: var(--font-mono);
    font-size: 9px;
    color: var(--color-text-dim);
  }

  .hud-count {
    cursor: default;
  }

  .hud-count--candidate {
    color: #7a7a9e;
  }

  .hud-sep {
    width: 1px;
    height: 8px;
    background: color-mix(in srgb, var(--color-text-dim) 25%, transparent);
    flex-shrink: 0;
  }

  .hud-fill {
    flex: 1;
  }

  .hud-legend {
    font-size: 7px;
    letter-spacing: 0.03em;
    color: color-mix(in srgb, var(--color-text-dim) 50%, transparent);
  }

  /* ── Search overlay ── */

  .hud-search {
    position: absolute;
    top: 6px;
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
