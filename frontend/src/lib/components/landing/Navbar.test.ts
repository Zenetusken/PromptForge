import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';

vi.mock('$app/paths', () => ({ base: '' }));
vi.mock('$app/stores', () => ({
  page: {
    subscribe: vi.fn((fn: (v: unknown) => void) => {
      fn({ url: { pathname: '/' } });
      return () => {};
    }),
  },
}));

import Navbar from './Navbar.svelte';

describe('Navbar', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders without crashing', () => {
    const { container } = render(Navbar);
    expect(container.querySelector('header')).toBeInTheDocument();
  });

  it('renders navigation links', () => {
    render(Navbar);
    expect(screen.getByText('Pipeline')).toBeInTheDocument();
    expect(screen.getByText('Example')).toBeInTheDocument();
    expect(screen.getByText('Integrations')).toBeInTheDocument();
  });

  it('renders the GitHub CTA link', () => {
    render(Navbar);
    expect(screen.getAllByText('GitHub').length).toBeGreaterThan(0);
  });

  it('renders the skip to content link', () => {
    render(Navbar);
    expect(screen.getByText('Skip to content')).toBeInTheDocument();
  });
});
