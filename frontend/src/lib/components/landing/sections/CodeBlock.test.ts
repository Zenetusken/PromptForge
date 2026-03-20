import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import CodeBlock from './CodeBlock.svelte';

describe('CodeBlock', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders without crashing', () => {
    const { container } = render(CodeBlock, { props: { language: 'bash', code: 'npm install' } });
    expect(container.querySelector('.code-block')).toBeInTheDocument();
  });

  it('renders code content', () => {
    render(CodeBlock, { props: { language: 'typescript', code: 'const x = 42;' } });
    expect(screen.getByText('const x = 42;')).toBeInTheDocument();
  });

  it('renders filename in header when provided', () => {
    render(CodeBlock, {
      props: { language: 'bash', code: 'npm run dev', filename: 'start.sh' },
    });
    expect(screen.getByText('start.sh')).toBeInTheDocument();
  });

  it('renders copy button', () => {
    render(CodeBlock, { props: { language: 'bash', code: 'echo hello' } });
    expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument();
  });
});
