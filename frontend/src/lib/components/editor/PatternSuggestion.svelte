<script lang="ts">
  import { clustersStore } from '$lib/stores/clusters.svelte';
  import { formatScore } from '$lib/utils/formatting';

  interface Props {
    onApply: (patterns: string[]) => void;
  }

  let { onApply }: Props = $props();

  function handleApply() {
    const patterns = clustersStore.applySuggestion();
    if (patterns) onApply(patterns);
  }

  function handleSkip() {
    clustersStore.dismissSuggestion();
  }
</script>

{#if clustersStore.suggestionVisible && clustersStore.suggestion}
  {@const match = clustersStore.suggestion}
  <div class="suggestion-banner" role="alert">
    <div class="suggestion-content">
      <div class="suggestion-header">
        <span class="suggestion-icon">&#x27E1;</span>
        <span class="suggestion-label">
          Matches "<strong>{match.cluster.label}</strong>" pattern ({Math.round(match.similarity * 100)}%)
        </span>
      </div>
      <div class="suggestion-meta">
        {match.meta_patterns.length} meta-pattern{match.meta_patterns.length !== 1 ? 's' : ''} available
      </div>
    </div>
    <div class="suggestion-actions">
      <button class="action-btn action-btn--primary" onclick={handleApply}>Apply</button>
      <button class="action-btn" onclick={handleSkip}>Skip</button>
    </div>
  </div>
{/if}

<style>
  .suggestion-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 6px;
    background: var(--color-bg-secondary);
    border: 1px solid var(--color-border-accent);
    margin: 4px 0;
    animation: slide-up-in 200ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
    font-size: 11px;
    font-family: var(--font-sans);
  }

  @keyframes slide-up-in {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .suggestion-content {
    flex: 1;
    min-width: 0;
  }

  .suggestion-header {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--color-text-primary);
  }

  .suggestion-icon {
    color: var(--color-neon-cyan);
    font-size: 14px;
  }

  .suggestion-label strong {
    color: var(--color-neon-cyan);
  }

  .suggestion-meta {
    color: var(--color-text-dim);
    font-size: 10px;
    font-family: var(--font-mono);
    margin-top: 2px;
    padding-left: 20px;
  }

  .suggestion-actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }






</style>
