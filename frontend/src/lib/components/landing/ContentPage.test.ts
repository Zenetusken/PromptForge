import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import ContentPage from './ContentPage.svelte';
import type { Section } from '$lib/content/types';

describe('ContentPage', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders without crashing with an empty sections array', () => {
    const { container } = render(ContentPage, { props: { sections: [] } });
    expect(container).toBeInTheDocument();
  });

  it('renders a hero section', () => {
    const sections: Section[] = [
      { type: 'hero', heading: 'Test Heading', subheading: 'Test subheading text' },
    ];
    render(ContentPage, { props: { sections } });
    expect(screen.getByText('Test Heading')).toBeInTheDocument();
  });

  it('renders a prose section', () => {
    const sections: Section[] = [
      { type: 'prose', blocks: [{ heading: 'About', content: '<p>Some content</p>' }] },
    ];
    render(ContentPage, { props: { sections } });
    expect(screen.getByText('About')).toBeInTheDocument();
  });

  it('renders a code-block section', () => {
    const sections: Section[] = [
      { type: 'code-block', language: 'bash', code: 'npm install' },
    ];
    render(ContentPage, { props: { sections } });
    expect(screen.getByText('npm install')).toBeInTheDocument();
  });
});
