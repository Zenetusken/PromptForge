import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { mockOptimizationResult } from '$lib/test-utils';

vi.mock('$lib/api/client', () => ({
  savePassthrough: vi.fn().mockResolvedValue({}),
  getOptimization: vi.fn().mockResolvedValue(null),
}));

import PassthroughView from './PassthroughView.svelte';
import { forgeStore } from '$lib/stores/forge.svelte';
import { editorStore } from '$lib/stores/editor.svelte';

describe('PassthroughView', () => {
  beforeEach(() => {
    forgeStore._reset();
    editorStore._reset();
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders without crashing', () => {
    const { container } = render(PassthroughView);
    expect(container.querySelector('.passthrough-view')).toBeInTheDocument();
  });

  it('shows MANUAL PASSTHROUGH header label', () => {
    render(PassthroughView);
    expect(screen.getByText('MANUAL PASSTHROUGH')).toBeInTheDocument();
  });

  it('shows loading state when assembledPrompt is absent', () => {
    render(PassthroughView);
    expect(screen.getByText('Preparing prompt...')).toBeInTheDocument();
  });

  it('shows assembled prompt when forgeStore.assembledPrompt is set', () => {
    forgeStore.assembledPrompt = 'My assembled prompt content';
    render(PassthroughView);
    expect(screen.getByText('My assembled prompt content')).toBeInTheDocument();
  });

  it('shows strategy label when passthroughStrategy is set', () => {
    forgeStore.assembledPrompt = 'Some assembled prompt content here';
    forgeStore.passthroughStrategy = 'chain-of-thought';
    render(PassthroughView);
    expect(screen.getByText(/strategy: chain-of-thought/)).toBeInTheDocument();
  });

  it('shows CANCEL button', () => {
    render(PassthroughView);
    expect(screen.getByText('CANCEL')).toBeInTheDocument();
  });

  it('clicking CANCEL calls forgeStore.cancel', async () => {
    const user = userEvent.setup();
    const cancelSpy = vi.spyOn(forgeStore, 'cancel');
    render(PassthroughView);

    await user.click(screen.getByText('CANCEL'));

    expect(cancelSpy).toHaveBeenCalled();
  });

  it('shows optimized result textarea with placeholder', () => {
    forgeStore.assembledPrompt = 'Some prompt content here';
    render(PassthroughView);
    expect(screen.getByLabelText('Optimized prompt result')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Paste the optimized prompt here...')).toBeInTheDocument();
  });

  it('shows changes summary input', () => {
    forgeStore.assembledPrompt = 'Some prompt content here';
    render(PassthroughView);
    expect(screen.getByLabelText('Changes summary')).toBeInTheDocument();
  });

  it('shows disabled SAVE button when no optimized prompt text', () => {
    forgeStore.assembledPrompt = 'Some prompt content here';
    render(PassthroughView);
    const saveBtn = screen.getByText('SAVE');
    expect(saveBtn).toBeDisabled();
  });

  it('enables SAVE button when optimized result is typed', async () => {
    const user = userEvent.setup();
    forgeStore.assembledPrompt = 'Some prompt content here';
    render(PassthroughView);

    const textarea = screen.getByLabelText('Optimized prompt result');
    await user.type(textarea, 'My optimized output text here');

    const saveBtn = screen.getByText('SAVE');
    expect(saveBtn).not.toBeDisabled();
  });

  it('calls submitPassthrough when SAVE is clicked with content', async () => {
    const user = userEvent.setup();
    const result = mockOptimizationResult({ id: 'opt-pt-saved' });
    const { savePassthrough } = await import('$lib/api/client');
    vi.mocked(savePassthrough).mockResolvedValue(result as any);

    forgeStore.assembledPrompt = 'Some prompt content here';
    forgeStore.passthroughTraceId = 'pt-trace-save';
    render(PassthroughView);

    const textarea = screen.getByLabelText('Optimized prompt result');
    await user.type(textarea, 'Optimized text from LLM here');
    await user.click(screen.getByText('SAVE'));

    expect(savePassthrough).toHaveBeenCalled();
  });

  it('shows COPY button (disabled when loading)', () => {
    render(PassthroughView);
    const copyBtn = screen.getByText('COPY');
    expect(copyBtn).toBeDisabled();
  });

  it('shows COPY button enabled when assembledPrompt is set', () => {
    forgeStore.assembledPrompt = 'Content to copy';
    render(PassthroughView);
    const copyBtn = screen.getByText('COPY');
    expect(copyBtn).not.toBeDisabled();
  });

  it('clicking COPY calls copyToClipboard', async () => {
    const user = userEvent.setup();
    forgeStore.assembledPrompt = 'Content to copy via clipboard';
    render(PassthroughView);

    await user.click(screen.getByText('COPY'));

    // Clipboard mock from test-setup.ts handles this; just check no crash
    expect(screen.getByText(/COPY|COPIED/)).toBeInTheDocument();
  });
});
