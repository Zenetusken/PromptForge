<script lang="ts">
  interface Props {
    number: number;
    title: string;
    description: string;
    isLast?: boolean;
  }

  let { number, title, description, isLast = false }: Props = $props();
</script>

<div class="step">
  <div class="step__indicator">
    <div class="step__number">{number}</div>
    {#if !isLast}
      <div class="step__line" aria-hidden="true"></div>
    {/if}
  </div>
  <div class="step__content">
    <h3 class="step__title">{title}</h3>
    <p class="step__desc">{description}</p>
  </div>
</div>

<style>
  .step {
    display: flex;
    gap: 12px;
    align-items: stretch;
  }

  .step__indicator {
    display: flex;
    flex-direction: column;
    align-items: center;
    flex-shrink: 0;
  }

  .step__number {
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 600;
    color: var(--color-neon-cyan);
    border: 1px solid var(--color-neon-cyan);
    flex-shrink: 0;
  }

  .step__line {
    width: 1px;
    flex: 1;
    min-height: 12px;
    background: var(--color-border-subtle);
  }

  .step__content {
    padding-bottom: 20px;
  }

  .step__title {
    font-family: var(--font-display);
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--color-text-primary);
    margin: 2px 0 4px 0;
  }

  .step__desc {
    font-size: 12px;
    font-weight: 400;
    color: var(--color-text-secondary);
    margin: 0;
    line-height: 1.5;
  }
</style>
