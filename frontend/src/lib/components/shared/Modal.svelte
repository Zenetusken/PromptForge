<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    /** Control visibility (default: true — assumes parent controls mounting) */
    open?: boolean;
    /** Called when backdrop is clicked; omit to disable backdrop dismiss */
    onclose?: () => void;
    /** Backdrop opacity variant */
    backdropOpacity?: 80 | 90;
    /** Content slot */
    children: Snippet;
  }

  const {
    open = true,
    onclose,
    backdropOpacity = 80,
    children,
  }: Props = $props();
</script>

{#if open}
  <!-- Backdrop -->
  <div
    class="fixed inset-0 z-50 {backdropOpacity === 90 ? 'bg-bg-primary/90' : 'bg-bg-primary/80'}"
    onclick={(e) => { if (e.target === e.currentTarget) onclose?.(); }}
    role="presentation"
  ></div>
  <!-- Content layer — pointer-events-none so backdrop receives clicks -->
  <div class="fixed inset-0 z-50 pointer-events-none">
    {@render children()}
  </div>
{/if}
