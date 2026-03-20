import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, cleanup, fireEvent } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import Logo from './Logo.svelte';

describe('Logo', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders without crashing', () => {
    const { container } = render(Logo);
    expect(container.querySelector('svg')).toBeInTheDocument();
  });

  it('renders the logo container with button role', () => {
    const { container } = render(Logo);
    expect(container.querySelector('[role="button"]')).toBeInTheDocument();
  });

  it('renders full variant with brand text', () => {
    const { container } = render(Logo, { props: { variant: 'full' } });
    expect(container.querySelector('.brand-text')).toBeInTheDocument();
  });

  it('applies correct size attribute to svg', () => {
    const { container } = render(Logo, { props: { size: 32 } });
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('width')).toBe('32');
    expect(svg?.getAttribute('height')).toBe('32');
  });

  it('triggers animation on click', async () => {
    const user = userEvent.setup();
    const { container } = render(Logo);
    const logoBtn = container.querySelector('[role="button"]') as HTMLElement;

    await user.click(logoBtn);

    // After click, is-active class should be set briefly
    expect(logoBtn).toHaveClass('is-active');
  });

  it('triggers animation on Enter keydown', async () => {
    const user = userEvent.setup();
    const { container } = render(Logo);
    const logoBtn = container.querySelector('[role="button"]') as HTMLElement;

    logoBtn.focus();
    await user.keyboard('{Enter}');

    expect(logoBtn).toHaveClass('is-active');
  });

  it('triggers animation on Space keydown', async () => {
    const user = userEvent.setup();
    const { container } = render(Logo);
    const logoBtn = container.querySelector('[role="button"]') as HTMLElement;

    logoBtn.focus();
    await user.keyboard(' ');

    expect(logoBtn).toHaveClass('is-active');
  });

  it('does not double-trigger animation while already animating', async () => {
    const user = userEvent.setup();
    const { container } = render(Logo);
    const logoBtn = container.querySelector('[role="button"]') as HTMLElement;

    // First click — triggers animation (is-active set)
    await user.click(logoBtn);
    expect(logoBtn).toHaveClass('is-active');

    // Click again while animating — isAnimating is true so no re-trigger
    // The class stays 'is-active' because isAnimating flag prevents re-entry
    await user.click(logoBtn);
    // Still active since timer hasn't expired
    expect(logoBtn).toHaveClass('is-active');
  });

  it('renders mark variant without brand text', () => {
    const { container } = render(Logo, { props: { variant: 'mark' } });
    expect(container.querySelector('.brand-text')).not.toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(Logo, { props: { class: 'custom-class' } });
    expect(container.querySelector('.custom-class')).toBeInTheDocument();
  });
});
