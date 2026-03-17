<script lang="ts">
  interface Props {
    quote: string;
    name: string;
    role: string;
    company: string;
    initials: string;
  }

  let { quote, name, role, company, initials }: Props = $props();
</script>

<blockquote class="testimonial">
  <p class="testimonial__quote">&ldquo;{quote}&rdquo;</p>
  <footer class="testimonial__attribution">
    <div class="testimonial__avatar" aria-hidden="true">{initials}</div>
    <div>
      <cite class="testimonial__name">{name}</cite>
      <span class="testimonial__role">{role} &middot; {company}</span>
    </div>
  </footer>
</blockquote>

<style>
  .testimonial {
    padding: 12px;
    background: var(--color-bg-secondary);
    border: 1px solid var(--color-border-subtle);
    margin: 0;
  }

  .testimonial__quote {
    font-size: 12px;
    font-weight: 400;
    color: var(--color-text-primary);
    line-height: 1.6;
    margin: 0 0 10px 0;
  }

  .testimonial__attribution {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .testimonial__avatar {
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--font-mono);
    font-size: 9px;
    font-weight: 600;
    color: var(--color-neon-cyan);
    border: 1px solid rgba(0, 229, 255, 0.2);
    background: rgba(0, 229, 255, 0.04);
    flex-shrink: 0;
  }

  .testimonial__name {
    display: block;
    font-family: var(--font-sans);
    font-size: 11px;
    font-weight: 600;
    font-style: normal;
    color: var(--color-text-primary);
  }

  .testimonial__role {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-text-dim);
  }
</style>
