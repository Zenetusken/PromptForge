/**
 * Frontend tier resolver.
 *
 * Derives the effective execution tier from user preferences and system
 * capabilities. Mirrors the backend's `services/routing.py` `resolve_route()`
 * 5-tier priority chain so the UI can adapt before the user hits SYNTHESIZE.
 *
 * Copyright 2025-2026 Project Synthesis contributors.
 */

import { preferencesStore } from './preferences.svelte';
import { forgeStore } from './forge.svelte';

export type EffectiveTier = 'internal' | 'sampling' | 'passthrough';

/**
 * Reactive tier derivation — re-evaluates whenever any dependency changes.
 *
 * Priority chain (matches backend):
 *  1. force_passthrough → passthrough
 *  2. force_sampling (if capable + connected) → sampling
 *  3. local provider available → internal
 *  4. auto-sampling available → sampling
 *  5. fallback → passthrough
 */
let _tier = $derived.by((): EffectiveTier => {
  if (preferencesStore.pipeline.force_passthrough) return 'passthrough';

  if (
    preferencesStore.pipeline.force_sampling &&
    forgeStore.samplingCapable === true &&
    !forgeStore.mcpDisconnected
  ) {
    return 'sampling';
  }

  if (forgeStore.provider) return 'internal';

  if (forgeStore.samplingCapable === true && !forgeStore.mcpDisconnected) {
    return 'sampling';
  }

  return 'passthrough';
});

/** Unified read-only routing state for UI consumption. */
export const routing = {
  get tier(): EffectiveTier {
    return _tier;
  },
  get isPassthrough(): boolean {
    return _tier === 'passthrough';
  },
  get isSampling(): boolean {
    return _tier === 'sampling';
  },
  get isInternal(): boolean {
    return _tier === 'internal';
  },
};
