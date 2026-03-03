/**
 * Shared forge action handlers for IDE-context components (ForgeIDEEditor, ForgeReview).
 *
 * Uses a stores interface to avoid circular imports — callers pass in the actual store
 * references, and these pure functions orchestrate the action.
 */

import type { OptimizeMetadata } from '$lib/api/client';

/** Minimal result shape needed by forge actions. */
export interface ForgeActionResult {
	id: string;
	original: string;
	optimized: string;
	project: string;
	prompt_id: string;
	title: string;
	version: string;
	tags: string[] | string;
}

/** Store dependencies injected by callers. */
export interface ForgeActionStores {
	optimizationState: {
		forgeResult: ForgeActionResult | null;
		startOptimization(prompt: string, metadata?: OptimizeMetadata, displayTitle?: string): void;
		chainForge(result: ForgeActionResult, metadata?: OptimizeMetadata): void;
	};
	forgeSession: {
		draft: { project: string };
		updateDraft(patch: Record<string, unknown>): void;
		buildMetadata(): OptimizeMetadata | undefined;
		loadRequest(req: Record<string, unknown> & { text: string }): void;
	};
	forgeMachine: {
		enterForging(): void;
		back(): void;
	};
}

/**
 * Re-forge: re-run the original prompt through the pipeline with current metadata.
 * Syncs project from result to draft if needed.
 */
export function reforge(stores: ForgeActionStores): void {
	const result = stores.optimizationState.forgeResult;
	if (!result) return;
	if (result.project && stores.forgeSession.draft.project !== result.project) {
		stores.forgeSession.updateDraft({ project: result.project });
	}
	const metadata: OptimizeMetadata = stores.forgeSession.buildMetadata() ?? {};
	// Always link re-forge to the source result for score-delta computation.
	// This overrides any retryOf already in draft to ensure the immediate parent is used.
	metadata.retry_of = result.id;
	// Use result's title as the process-queue display label when the draft has no title.
	const displayTitle = result.title || undefined;
	stores.optimizationState.startOptimization(result.original, metadata, displayTitle);
	stores.forgeMachine.enterForging();
}

/**
 * Chain forge: feed the optimized output as the new input.
 * Syncs project from result to draft (same as reforge) so metadata always has correct project.
 * Also updates draft.text so the compose area reflects the chain's actual input prompt.
 */
export function chainForge(stores: ForgeActionStores): void {
	const result = stores.optimizationState.forgeResult;
	if (!result) return;
	if (result.project && stores.forgeSession.draft.project !== result.project) {
		stores.forgeSession.updateDraft({ project: result.project });
	}
	// Keep compose area in sync with what the chain is actually processing.
	// Without this, draft.text stays as the user's original typed text while
	// the chain processes result.optimized — a confusing inconsistency.
	stores.forgeSession.updateDraft({ text: result.optimized });
	const metadata = stores.forgeSession.buildMetadata();
	stores.optimizationState.chainForge(result, metadata);
	stores.forgeMachine.enterForging();
}

/**
 * Iterate: load the optimized text into the editor for manual editing.
 */
export function iterate(stores: ForgeActionStores): void {
	const result = stores.optimizationState.forgeResult;
	if (!result) return;
	stores.forgeSession.loadRequest({
		text: result.optimized,
		sourceAction: 'reiterate',
		project: result.project,
		promptId: result.prompt_id,
		title: result.title,
		version: result.version,
		tags: Array.isArray(result.tags) ? result.tags.join(', ') : '',
		strategy: 'auto',
		// Carry lineage so buildMetadata() includes retry_of when user submits
		retryOf: result.id,
	});
	stores.forgeMachine.back();
}
