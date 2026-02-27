import { forgeSession } from '$lib/stores/forgeSession.svelte';
import { optimizationState } from '$lib/stores/optimization.svelte';
import { forgeMachine } from '$lib/stores/forgeMachine.svelte';
import { toastState } from '$lib/stores/toast.svelte';
import type { WorkspaceTab } from '$lib/stores/forgeSession.svelte';

/** Monotonic counter — incremented on each restoreTabState call to discard stale async results. */
let _restoreGeneration = 0;

/**
 * Save the current forge/machine state onto the active tab and persist to sessionStorage.
 * Call before switching away from or closing the active tab.
 */
export function saveActiveTabState(): void {
	const tab = forgeSession.activeTab;
	if (!tab) return;
	tab.resultId = optimizationState.forgeResult?.id ?? null;
	tab.mode = forgeMachine.mode === 'forging' ? 'compose' : forgeMachine.mode;
	forgeSession.persistTabs();
}

/**
 * Restore forge/machine state from a tab's saved state.
 * Document-aware: uses tab.document.kind for kind-specific restore behavior.
 * Call after switching to a new active tab.
 */
export function restoreTabState(tab: WorkspaceTab): void {
	const generation = ++_restoreGeneration;

	if (tab.resultId && tab.mode === 'review') {
		// Synchronous cache path (no flash)
		const cached = optimizationState.resultHistory.find(r => r.id === tab.resultId);
		if (cached) {
			optimizationState.forgeResult = cached;
			forgeMachine.enterReview();
		} else {
			// Async server fallback — show compose briefly, then transition to review
			optimizationState.resetForge();
			forgeMachine.back();
			optimizationState.restoreResult(tab.resultId).then(ok => {
				if (generation !== _restoreGeneration) return;
				if (forgeSession.activeTabId === tab.id && ok) {
					forgeMachine.enterReview();
				} else if (forgeSession.activeTabId === tab.id) {
					tab.resultId = null;
					tab.mode = 'compose';
					// Clear artifact/sub-artifact document when its result can't be restored
					if (tab.document?.kind === 'artifact' || tab.document?.kind === 'sub-artifact') {
						tab.document = null;
					}
					forgeSession.persistTabs();
					toastState.show('Previous result could not be restored', 'info');
				}
			});
		}
	} else {
		optimizationState.resetForge();
		if (forgeMachine.mode !== 'compose') {
			forgeMachine.back();
		}
	}
}
