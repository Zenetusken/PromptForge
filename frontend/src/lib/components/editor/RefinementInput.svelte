<script lang="ts">
  import { refinement } from '$lib/stores/refinement.svelte';

  const DIMENSIONS = [
    { key: 'clarity_score',     abbr: 'CLR' },
    { key: 'specificity_score', abbr: 'SPC' },
    { key: 'structure_score',   abbr: 'STR' },
    { key: 'faithfulness_score', abbr: 'FTH' },
    { key: 'conciseness_score', abbr: 'CNC' },
  ] as const;

  let { optimizationId }: { optimizationId: string } = $props();

  let message = $state('');

  function handleSend() {
    const trimmed = message.trim();
    if (!trimmed || refinement.refinementStreaming) return;
    refinement.startRefine(optimizationId, trimmed);
    message = '';
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSend();
    }
  }
</script>

{#if refinement.refinementOpen}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="refinement-well border-t border-border-subtle bg-bg-secondary"
    class:refinement-streaming={refinement.refinementStreaming}
    style="animation: slide-up-in 300ms cubic-bezier(0.16, 1, 0.3, 1) both;"
  >
    <!-- Header row: label + close -->
    <div class="flex items-center justify-between px-3 pt-2.5 pb-1.5">
      <span class="text-[10px] font-mono uppercase tracking-wider text-text-dim">Refine</span>
      <button
        class="w-5 h-5 flex items-center justify-center text-text-dim hover:text-text-secondary transition-colors border border-transparent hover:border-border-subtle"
        onclick={() => refinement.closeRefinement()}
        aria-label="Close refinement panel"
        title="Close"
      >
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
          <line x1="1" y1="1" x2="9" y2="9" stroke="currentColor" stroke-width="1.5" stroke-linecap="square"/>
          <line x1="9" y1="1" x2="1" y2="9" stroke="currentColor" stroke-width="1.5" stroke-linecap="square"/>
        </svg>
      </button>
    </div>

    <!-- Protected dimensions chips -->
    <div class="flex flex-wrap gap-1.5 px-3 pb-2">
      {#each DIMENSIONS as dim}
        {@const isProtected = refinement.protectedDimensions.includes(dim.key)}
        <button
          class="chip px-2 py-0.5 text-[10px] font-mono border transition-colors"
          class:chip-protected={isProtected}
          class:chip-default={!isProtected}
          onclick={() => refinement.toggleProtectDimension(dim.key)}
          title="{isProtected ? 'Unprotect' : 'Protect'} {dim.key.replace(/_/g, ' ')}"
          aria-pressed={isProtected}
        >
          {dim.abbr}
        </button>
      {/each}
      <span class="text-[9px] font-mono text-text-dim self-center ml-0.5">protect dims</span>
    </div>

    <!-- Input well -->
    <div class="input-well mx-3 mb-2 border" class:streaming-border={refinement.refinementStreaming}>
      <textarea
        class="w-full bg-bg-input px-3 py-2 text-[12px] text-text-primary font-sans resize-none
               placeholder:text-text-dim focus:outline-none block"
        placeholder="Describe how to improve..."
        rows="3"
        disabled={refinement.refinementStreaming}
        bind:value={message}
        onkeydown={handleKeydown}
        aria-label="Refinement message"
      ></textarea>

      <!-- Send row -->
      <div class="flex items-center justify-between px-3 py-1.5 border-t border-border-subtle bg-bg-card">
        <span class="text-[9px] font-mono text-text-dim">
          {#if refinement.refinementStreaming}
            <span class="text-neon-cyan/60">streaming...</span>
          {:else}
            <kbd>⌘ Enter</kbd> to send
          {/if}
        </span>
        <button
          class="btn-primary px-3 py-1 text-[11px] font-mono disabled:opacity-40 disabled:cursor-not-allowed"
          disabled={refinement.refinementStreaming || !message.trim()}
          onclick={handleSend}
          aria-label="Send refinement"
        >
          Send
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  /* Protected chip: neon-teal (#00d4aa) */
  .chip-protected {
    background-color: rgba(0, 212, 170, 0.1);
    border-color: #00d4aa;
    color: #00d4aa;
  }

  /* Default (unprotected) chip */
  .chip-default {
    background-color: transparent;
    border-color: rgba(74, 74, 106, 0.3);
    color: var(--color-text-dim);
  }

  .chip-default:hover {
    border-color: rgba(74, 74, 106, 0.6);
    color: var(--color-text-secondary);
  }

  /* Input well border states */
  .input-well {
    border-color: rgba(74, 74, 106, 0.2);
  }

  /* Streaming indicator: border-color oscillation (NOT glow) */
  @keyframes border-oscillate {
    0%, 100% {
      border-color: rgba(0, 229, 255, 0.3);
    }
    50% {
      border-color: rgba(0, 212, 170, 0.3);
    }
  }

  .streaming-border {
    animation: border-oscillate 1.4s ease-in-out infinite;
  }
</style>
