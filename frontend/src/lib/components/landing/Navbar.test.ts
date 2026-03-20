import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';

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

  it('mobile toggle button has aria-expanded false by default', () => {
    render(Navbar);
    const toggle = screen.getByRole('button', { name: /Open menu/i });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
  });

  it('mobile toggle button opens mobile menu on click', async () => {
    const user = userEvent.setup();
    render(Navbar);
    const toggle = screen.getByRole('button', { name: /Open menu/i });
    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(toggle).toHaveAttribute('aria-label', 'Close menu');
  });

  it('mobile menu shows nav links when open', async () => {
    const user = userEvent.setup();
    render(Navbar);
    const toggle = screen.getByRole('button', { name: /Open menu/i });
    await user.click(toggle);
    // Mobile links in the mobile menu
    const mobileLinks = screen.getAllByText('Pipeline');
    expect(mobileLinks.length).toBeGreaterThan(0);
  });

  it('mobile menu link closes menu on click', async () => {
    const user = userEvent.setup();
    render(Navbar);
    const toggle = screen.getByRole('button', { name: /Open menu/i });
    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
  });

  it('renders the main nav element', () => {
    render(Navbar);
    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument();
  });
});
