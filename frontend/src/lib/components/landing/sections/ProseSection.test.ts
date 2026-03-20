import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import ProseSection from './ProseSection.svelte';

describe('ProseSection', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders without crashing', () => {
    const { container } = render(ProseSection, {
      props: { blocks: [] },
    });
    expect(container.querySelector('.prose-section')).toBeInTheDocument();
  });

  it('renders block heading when provided', () => {
    render(ProseSection, {
      props: {
        blocks: [{ heading: 'Introduction', content: '<p>Some text</p>' }],
      },
    });
    expect(screen.getByText('Introduction')).toBeInTheDocument();
  });

  it('renders block html content', () => {
    render(ProseSection, {
      props: {
        blocks: [{ content: '<p>Paragraph content here</p>' }],
      },
    });
    expect(screen.getByText('Paragraph content here')).toBeInTheDocument();
  });

  it('renders multiple blocks', () => {
    render(ProseSection, {
      props: {
        blocks: [
          { heading: 'Section A', content: '<p>Content A</p>' },
          { heading: 'Section B', content: '<p>Content B</p>' },
        ],
      },
    });
    expect(screen.getByText('Section A')).toBeInTheDocument();
    expect(screen.getByText('Section B')).toBeInTheDocument();
  });
});
