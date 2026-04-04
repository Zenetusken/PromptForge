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

<!-- HUD overlay — elements distributed across canvas edges -->
<div class="hud">
  <!-- TOP-RIGHT: Metrics readout -->
  <div class="hud-metrics">
    <TopologyInfoPanel />
  </div>

  <!-- RIGHT EDGE: Command & layer controls -->
  <div class="hud-controls">
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

  <!-- BOTTOM-RIGHT: Status readout -->
  <div class="hud-status">
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
    <span class="hud-legend">wire=coh sat=score</span>
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
  /* ══ HUD — cockpit-style overlay on the 3D canvas ══
   *
   * Elements are positioned absolutely to canvas edges.
   * No container box — each group floats independently.
   * Semi-transparent backgrounds let the graph bleed through.
   * Borders only appear on interactive elements on hover.
   */

  .hud {
    position: absolute;
    inset: 0;
    pointer-events: none;
    z-index: 10;
  }

  /* ── Top-right: Metrics readout ── */

  .hud-metrics {
    position: absolute;
    top: 6px;
    right: 6px;
    width: 172px;
    pointer-events: auto;
    background: color-mix(in srgb, var(--color-bg-primary) 68%, transparent);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
    border: 1px solid color-mix(in srgb, var(--color-border-subtle) 25%, transparent);
  }

  /* ── Right edge: Controls ── */

  .hud-controls {
    position: absolute;
    right: 6px;
    bottom: 28px;
    width: 172px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    pointer-events: auto;
  }

  .hud-row {
    display: flex;
    gap: 2px;
  }

  /* ── Toggle buttons (layers + activity) ── */

  .hud-toggle {
    display: flex;
    align-items: center;
    gap: 3px;
    flex: 1;
    padding: 2px 5px;
    background: color-mix(in srgb, var(--color-bg-primary) 55%, transparent);
    backdrop-filter: blur(3px);
    -webkit-backdrop-filter: blur(3px);
    border: 1px solid transparent;
    color: color-mix(in srgb, var(--color-text-dim) 70%, transparent);
    font-family: var(--font-mono);
    font-size: 9px;
    cursor: pointer;
    transition: border-color 150ms cubic-bezier(0.16, 1, 0.3, 1),
                color 150ms cubic-bezier(0.16, 1, 0.3, 1),
                background 150ms cubic-bezier(0.16, 1, 0.3, 1);
  }

  .hud-toggle:hover {
    border-color: color-mix(in srgb, var(--hud-accent, var(--color-neon-cyan)) 35%, transparent);
    color: var(--color-text-secondary);
  }

  .hud-toggle--on {
    border-color: color-mix(in srgb, var(--hud-accent, var(--color-neon-cyan)) 45%, transparent);
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
    opacity: 0.2;
    transition: opacity 150ms cubic-bezier(0.16, 1, 0.3, 1);
  }

  .hud-toggle--on .hud-indicator {
    opacity: 1;
  }

  /* ── Command buttons ── */

  .hud-cmd {
    flex: 1;
    padding: 2px 4px;
    background: color-mix(in srgb, var(--color-bg-primary) 55%, transparent);
    backdrop-filter: blur(3px);
    -webkit-backdrop-filter: blur(3px);
    border: 1px solid transparent;
    color: color-mix(in srgb, var(--color-text-dim) 70%, transparent);
    font-family: var(--font-mono);
    font-size: 9px;
    cursor: pointer;
    text-align: center;
    transition: border-color 150ms cubic-bezier(0.16, 1, 0.3, 1),
                color 150ms cubic-bezier(0.16, 1, 0.3, 1),
                background 150ms cubic-bezier(0.16, 1, 0.3, 1);
  }

  .hud-cmd:hover:not(:disabled) {
    border-color: color-mix(in srgb, var(--color-neon-cyan) 35%, transparent);
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
    color: color-mix(in srgb, var(--color-text-dim) 60%, transparent);
    padding: 2px 4px;
    letter-spacing: 0.08em;
    background: color-mix(in srgb, var(--color-bg-primary) 45%, transparent);
    border: 1px solid transparent;
    flex-shrink: 0;
  }

  /* ── Bottom-right: Status telemetry ── */

  .hud-status {
    position: absolute;
    right: 6px;
    bottom: 6px;
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 2px 6px;
    font-family: var(--font-mono);
    font-size: 9px;
    color: color-mix(in srgb, var(--color-text-dim) 60%, transparent);
    pointer-events: auto;
    background: color-mix(in srgb, var(--color-bg-primary) 50%, transparent);
    backdrop-filter: blur(3px);
    -webkit-backdrop-filter: blur(3px);
  }

  .hud-count {
    cursor: default;
  }

  .hud-count--candidate {
    color: color-mix(in srgb, #7a7a9e 70%, transparent);
  }

  .hud-sep {
    width: 1px;
    height: 8px;
    background: color-mix(in srgb, var(--color-text-dim) 20%, transparent);
  }

  .hud-legend {
    font-size: 7px;
    letter-spacing: 0.02em;
    color: color-mix(in srgb, var(--color-text-dim) 30%, transparent);
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
    background: color-mix(in srgb, var(--color-bg-primary) 85%, transparent);
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
