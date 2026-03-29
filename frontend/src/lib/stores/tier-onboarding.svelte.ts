/**
 * Tier onboarding coordinator.
 *
 * Single entry point for all automatic guide triggers — startup detection
 * and runtime tier transitions.  Maps the resolved tier to the correct
 * guide store and calls ``show(true)`` (respectDismiss) so first-time
 * users see onboarding while returning users are not interrupted.
 *
 * Uses a settle delay on the first trigger to allow the MCP bridge time
 * to connect and establish sampling capability (~1-2s).  Subsequent
 * triggers (SSE-driven tier changes) fire immediately.
 *
 * Copyright 2025-2026 Project Synthesis contributors.
 */

import type { EffectiveTier } from './routing.svelte';
import { internalGuide } from './internal-guide.svelte';
import { samplingGuide } from './sampling-guide.svelte';
import { passthroughGuide } from './passthrough-guide.svelte';

/** Settle delay for the first trigger — allows MCP bridge capability negotiation. */
const STARTUP_SETTLE_MS = 2000;

/** Last tier for which a guide was triggered — prevents redundant opens. */
let lastTriggeredTier: EffectiveTier | null = null;

/** Whether the first trigger has settled (or been superseded by a tier change). */
let settled = false;

/** Pending startup timer — cancelled when an SSE tier change arrives first. */
let settleTimer: ReturnType<typeof setTimeout> | null = null;

/** Tier → guide store lookup.  O(1) dispatch, no switch statement. */
const GUIDE_MAP: Record<EffectiveTier, { show(respectDismiss?: boolean): void }> = {
  internal: internalGuide,
  sampling: samplingGuide,
  passthrough: passthroughGuide,
};

function showGuide(tier: EffectiveTier): void {
  if (tier === lastTriggeredTier) return;
  lastTriggeredTier = tier;
  GUIDE_MAP[tier].show(true);
}

/**
 * Show the onboarding guide for the given tier (respectDismiss = true).
 *
 * First call: deferred by STARTUP_SETTLE_MS to let MCP bridge connect.
 * If a second call arrives before the timer fires (SSE tier change),
 * the timer is cancelled and the new tier fires immediately — the SSE
 * event carries the authoritative tier.
 *
 * Subsequent calls (after settle): fire immediately with dedup guard.
 */
export function triggerTierGuide(tier: EffectiveTier): void {
  if (settled) {
    // Post-startup: immediate (SSE-driven tier transitions)
    showGuide(tier);
    return;
  }

  // Pre-startup: debounce to let MCP bridge establish capabilities
  if (settleTimer) {
    // A new tier arrived before the timer fired — cancel and fire immediately
    clearTimeout(settleTimer);
    settleTimer = null;
    settled = true;
    showGuide(tier);
    return;
  }

  // First call: start settle timer
  settleTimer = setTimeout(() => {
    settleTimer = null;
    settled = true;
    showGuide(tier);
  }, STARTUP_SETTLE_MS);
}

/** @internal Test-only: reset the last triggered tier for isolation. */
export function _resetOnboarding(): void {
  lastTriggeredTier = null;
  settled = false;
  if (settleTimer) { clearTimeout(settleTimer); settleTimer = null; }
}
