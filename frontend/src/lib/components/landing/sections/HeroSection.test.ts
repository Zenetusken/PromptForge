import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import HeroSection from './HeroSection.svelte';

describe('HeroSection', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders without crashing', () => {
    const { container } = render(HeroSection, {
      props: { heading: 'Test Heading', subheading: 'Test subheading' },
    });
    expect(container.querySelector('.hero')).toBeInTheDocument();
  });

  it('renders the heading text', () => {
    render(HeroSection, { props: { heading: 'AI Prompt Engine', subheading: 'Subtitle here' } });
    expect(screen.getByText('AI Prompt Engine')).toBeInTheDocument();
  });

  it('renders the subheading text', () => {
    render(HeroSection, { props: { heading: 'Title', subheading: 'Meaningful subtitle' } });
    expect(screen.getByText('Meaningful subtitle')).toBeInTheDocument();
  });

  it('renders CTA link when cta prop is provided', () => {
    render(HeroSection, {
      props: {
        heading: 'Title',
        subheading: 'Sub',
        cta: { label: 'Get Started', href: '#start' },
      },
    });
    expect(screen.getByText('Get Started')).toBeInTheDocument();
  });
});
