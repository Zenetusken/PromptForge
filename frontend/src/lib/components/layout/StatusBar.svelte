<script lang="ts">
  import { onMount } from 'svelte';
  import { getHealth } from '$lib/api/client';
  import ProviderBadge from '$lib/components/shared/ProviderBadge.svelte';

  let provider = $state<string | null>(null);
  let version = $state<string | null>(null);

  onMount(async () => {
    try {
      const health = await getHealth();
      provider = health.provider;
      version = health.version;
    } catch {
      // Backend not reachable — leave provider/version null
    }
  });
</script>

<div
  class="status-bar"
  role="status"
  aria-label="Status bar"
  style="background: var(--color-bg-secondary); border-top: 1px solid var(--color-border-subtle);"
>
  <!-- Left side: provider badge + version -->
  <div class="status-left">
    <ProviderBadge {provider} />
    <span class="status-item">Project Synthesis{version ? ` v${version}` : ''}</span>
  </div>

  <!-- Right side: keyboard shortcut hint -->
  <div class="status-right">
    <span class="status-kbd" aria-label="Open command palette with Ctrl+K">Ctrl+K</span>
  </div>
</div>

<style>
  .status-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 20px;
    padding: 0 4px;
    overflow: hidden;
  }

  .status-left,
  .status-right {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .status-item {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--color-text-dim);
    white-space: nowrap;
  }

  .status-kbd {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--color-text-dim);
    border: 1px solid var(--color-border-subtle);
    padding: 1px 6px;
    white-space: nowrap;
  }
</style>
