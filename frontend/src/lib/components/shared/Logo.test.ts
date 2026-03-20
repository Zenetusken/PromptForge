import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/svelte';
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
});
