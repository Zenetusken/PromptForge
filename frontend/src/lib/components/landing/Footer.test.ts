import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';

vi.mock('$app/paths', () => ({ base: '' }));

import Footer from './Footer.svelte';

describe('Footer', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders without crashing', () => {
    const { container } = render(Footer);
    expect(container.querySelector('footer')).toBeInTheDocument();
  });

  it('renders the Product column heading', () => {
    render(Footer);
    expect(screen.getByText('Product')).toBeInTheDocument();
  });

  it('renders the Legal column heading', () => {
    render(Footer);
    expect(screen.getByText('Legal')).toBeInTheDocument();
  });

  it('renders footer links', () => {
    render(Footer);
    expect(screen.getByText('Pipeline')).toBeInTheDocument();
    expect(screen.getByText('Privacy')).toBeInTheDocument();
  });

  it('renders copyright text', () => {
    render(Footer);
    expect(screen.getByText(/Project Synthesis/)).toBeInTheDocument();
  });
});
