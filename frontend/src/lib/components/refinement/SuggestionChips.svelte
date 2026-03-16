<script lang="ts">
  interface Props {
    suggestions: Array<{ text: string; source: string }>;
    onSelect: (text: string) => void;
  }

  let { suggestions, onSelect }: Props = $props();
</script>

{#if suggestions.length > 0}
  <div class="chips" aria-label="Refinement suggestions">
    {#each suggestions.slice(0, 3) as chip}
      <button
        class="chip"
        title="Source: {chip.source}"
        onclick={() => onSelect(chip.text)}
      >
        {chip.text}
      </button>
    {/each}
  </div>
{/if}

<style>
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    padding: 4px 0;
  }

  .chip {
    font-size: 10px;
    font-family: var(--font-sans);
    color: var(--color-text-secondary);
    background: transparent;
    border: 1px solid var(--color-border-subtle);
    padding: 2px 8px;
    cursor: pointer;
    white-space: nowrap;
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: border-color 200ms cubic-bezier(0.16, 1, 0.3, 1),
                background 200ms cubic-bezier(0.16, 1, 0.3, 1),
                color 200ms cubic-bezier(0.16, 1, 0.3, 1);
  }

  .chip:hover {
    border-color: var(--color-neon-cyan);
    background: rgba(0, 229, 255, 0.04);
    color: var(--color-text-primary);
  }
</style>
