<script lang="ts">
  import { patternsStore } from '$lib/stores/patterns.svelte';

  interface Props {
    onApply: (patterns: string[]) => void;
  }

  let { onApply }: Props = $props();

  function handleApply() {
    const patterns = patternsStore.applySuggestion();
    if (patterns) onApply(patterns);
  }

  function handleSkip() {
    patternsStore.dismissSuggestion();
  }
</script>

{#if patternsStore.suggestionVisible && patternsStore.suggestion}
  {@const match = patternsStore.suggestion}
  <div class="suggestion-banner" role="alert">
    <div class="suggestion-content">
      <div class="suggestion-header">
        <span class="suggestion-icon">&#x27E1;</span>
        <span class="suggestion-label">
          Matches "<strong>{match.family.intent_label}</strong>" pattern ({Math.round(match.similarity * 100)}%)
        </span>
      </div>
      <div class="suggestion-meta">
        {match.meta_patterns.length} meta-pattern{match.meta_patterns.length !== 1 ? 's' : ''} available
        {#if match.family.avg_score != null}
          &middot; avg score {match.family.avg_score.toFixed(1)}
        {/if}
      </div>
    </div>
    <div class="suggestion-actions">
      <button class="btn-apply" onclick={handleApply}>Apply</button>
      <button class="btn-skip" onclick={handleSkip}>Skip</button>
    </div>
  </div>
{/if}

<style>
  .suggestion-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 10px;
    background: var(--color-bg-secondary, #0d0d1a);
    border: 1px solid var(--color-border-accent, #00e5ff33);
    margin: 4px 0;
    animation: slideIn 200ms ease-out;
    font-size: 11px;
  }

  @keyframes slideIn {
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
    color: var(--color-text-primary, #c8c8d0);
  }

  .suggestion-icon {
    color: var(--color-neon-cyan, #00e5ff);
    font-size: 14px;
  }

  .suggestion-label strong {
    color: var(--color-neon-cyan, #00e5ff);
  }

  .suggestion-meta {
    color: var(--color-text-dim, #666);
    font-size: 10px;
    margin-top: 2px;
    padding-left: 20px;
  }

  .suggestion-actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }

  .btn-apply {
    background: transparent;
    border: 1px solid var(--color-neon-cyan, #00e5ff);
    color: var(--color-neon-cyan, #00e5ff);
    padding: 2px 10px;
    font-size: 10px;
    font-family: inherit;
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .btn-apply:hover {
    background: rgba(0, 229, 255, 0.06);
  }

  .btn-skip {
    background: transparent;
    border: 1px solid var(--color-border-subtle, #333);
    color: var(--color-text-dim, #666);
    padding: 2px 10px;
    font-size: 10px;
    font-family: inherit;
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .btn-skip:hover {
    border-color: #555;
    color: #888;
  }
</style>
