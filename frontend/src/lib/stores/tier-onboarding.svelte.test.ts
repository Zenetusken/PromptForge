import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { triggerTierGuide, _resetOnboarding } from './tier-onboarding.svelte';
import { internalGuide } from './internal-guide.svelte';
import { samplingGuide } from './sampling-guide.svelte';
import { passthroughGuide } from './passthrough-guide.svelte';

describe('tier onboarding coordinator', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    _resetOnboarding();
    internalGuide.close();
    internalGuide.resetDismissal();
    samplingGuide.close();
    samplingGuide.resetDismissal();
    passthroughGuide.close();
    passthroughGuide.resetDismissal();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('first trigger defers by settle delay', () => {
    const spy = vi.spyOn(internalGuide, 'show');
    triggerTierGuide('internal');
    // Not called yet — waiting for settle
    expect(spy).not.toHaveBeenCalled();
    // After settle delay
    vi.advanceTimersByTime(2000);
    expect(spy).toHaveBeenCalledWith(true);
    spy.mockRestore();
  });

  it('SSE tier change before settle fires immediately and cancels timer', () => {
    const internalSpy = vi.spyOn(internalGuide, 'show');
    const samplingSpy = vi.spyOn(samplingGuide, 'show');

    // First call: starts settle timer for internal
    triggerTierGuide('internal');
    expect(internalSpy).not.toHaveBeenCalled();

    // SSE arrives before settle — sampling supersedes
    triggerTierGuide('sampling');
    expect(samplingSpy).toHaveBeenCalledWith(true);

    // Advance past settle — internal should NOT fire (timer was cancelled)
    vi.advanceTimersByTime(2000);
    expect(internalSpy).not.toHaveBeenCalled();

    internalSpy.mockRestore();
    samplingSpy.mockRestore();
  });

  it('post-settle triggers fire immediately', () => {
    // Settle first
    triggerTierGuide('internal');
    vi.advanceTimersByTime(2000);

    // Now post-settle: passthrough fires immediately
    const spy = vi.spyOn(passthroughGuide, 'show');
    triggerTierGuide('passthrough');
    expect(spy).toHaveBeenCalledWith(true);
    spy.mockRestore();
  });

  it('deduplicates: same tier called twice only triggers once', () => {
    const spy = vi.spyOn(internalGuide, 'show');
    triggerTierGuide('internal');
    vi.advanceTimersByTime(2000);
    // Second call with same tier — deduped
    triggerTierGuide('internal');
    expect(spy).toHaveBeenCalledTimes(1);
    spy.mockRestore();
  });

  it('triggers correct guide for each tier after settle', () => {
    const internalSpy = vi.spyOn(internalGuide, 'show');
    const samplingSpy = vi.spyOn(samplingGuide, 'show');
    const passthroughSpy = vi.spyOn(passthroughGuide, 'show');

    triggerTierGuide('sampling');
    vi.advanceTimersByTime(2000);
    expect(samplingSpy).toHaveBeenCalledWith(true);

    triggerTierGuide('passthrough');
    expect(passthroughSpy).toHaveBeenCalledWith(true);

    triggerTierGuide('internal');
    expect(internalSpy).toHaveBeenCalledWith(true);

    internalSpy.mockRestore();
    samplingSpy.mockRestore();
    passthroughSpy.mockRestore();
  });

  it('_resetOnboarding allows re-triggering the same tier', () => {
    const spy = vi.spyOn(internalGuide, 'show');
    triggerTierGuide('internal');
    vi.advanceTimersByTime(2000);
    expect(spy).toHaveBeenCalledTimes(1);

    _resetOnboarding();
    triggerTierGuide('internal');
    vi.advanceTimersByTime(2000);
    expect(spy).toHaveBeenCalledTimes(2);
    spy.mockRestore();
  });
});
