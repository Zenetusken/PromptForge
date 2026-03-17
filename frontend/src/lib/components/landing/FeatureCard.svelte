<script lang="ts">
  interface Props {
    icon: string;
    color: string;
    title: string;
    description: string;
  }

  let { icon, color, title, description }: Props = $props();
</script>

<article class="feature-card">
  <div class="feature-card__icon" style="color:{color};border-color:{color};">
    {@html icon}
  </div>
  <h3 class="feature-card__title">{title}</h3>
  <p class="feature-card__desc">{description}</p>
</article>

<style>
  .feature-card {
    padding: 12px;
    background: var(--color-bg-card);
    border: 1px solid var(--color-border-subtle);
    transition: all var(--duration-hover) var(--ease-spring);
  }

  .feature-card:hover {
    background: var(--color-bg-hover);
    border-color: var(--color-border-accent);
  }

  .feature-card__icon {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid;
    margin-bottom: 8px;
  }

  .feature-card__icon :global(svg) {
    width: 14px;
    height: 14px;
  }

  .feature-card__title {
    font-family: var(--font-sans);
    font-size: 12px;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0 0 4px 0;
  }

  .feature-card__desc {
    font-size: 12px;
    font-weight: 400;
    color: var(--color-text-secondary);
    margin: 0;
    line-height: 1.5;
  }
</style>
