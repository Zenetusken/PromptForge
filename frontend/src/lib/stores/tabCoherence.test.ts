import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock sessionStorage
const storageMap = new Map<string, string>();
const mockSessionStorage = {
	getItem: (key: string) => storageMap.get(key) ?? null,
	setItem: (key: string, value: string) => storageMap.set(key, value),
	removeItem: (key: string) => storageMap.delete(key),
	clear: () => storageMap.clear(),
	get length() { return storageMap.size; },
	key: (i: number) => [...storageMap.keys()][i] ?? null,
};
Object.defineProperty(globalThis, 'sessionStorage', { value: mockSessionStorage, writable: true });

// Mock stores
vi.mock('$lib/stores/provider.svelte', () => ({
	providerState: { selectedProvider: null },
}));

vi.mock('$lib/stores/windowManager.svelte', () => ({
	windowManager: {
		openIDE: vi.fn(),
		closeIDE: vi.fn(),
		ideSpawned: false,
		ideVisible: false,
	},
}));

vi.mock('$lib/stores/history.svelte', () => ({
	historyState: { loadHistory: vi.fn() },
}));

vi.mock('$lib/stores/projects.svelte', () => ({
	projectsState: { loadProjects: vi.fn() },
}));

vi.mock('$lib/stores/promptAnalysis.svelte', () => ({
	promptAnalysis: { updateFromPipeline: vi.fn() },
}));

vi.mock('$lib/stores/toast.svelte', () => ({
	toastState: { show: vi.fn() },
}));

vi.mock('$lib/api/client', () => ({
	fetchOptimize: vi.fn(),
	fetchRetry: vi.fn(),
	fetchOptimization: vi.fn(),
	orchestrateAnalyze: vi.fn(),
}));

import { saveActiveTabState, restoreTabState } from './tabCoherence';
import { forgeSession, createEmptyDraft } from './forgeSession.svelte';
import { optimizationState } from './optimization.svelte';
import { forgeMachine } from './forgeMachine.svelte';
import type { WorkspaceTab } from './forgeSession.svelte';
import type { OptimizationResultState } from './optimization.svelte';

function makeResult(id: string): OptimizationResultState {
	return {
		id,
		original: 'test',
		optimized: 'better',
		task_type: 'coding',
		complexity: 'medium',
		weaknesses: [],
		strengths: [],
		changes_made: [],
		framework_applied: '',
		optimization_notes: '',
		scores: { clarity: 0, specificity: 0, structure: 0, faithfulness: 0, overall: 0.8 },
		is_improvement: true,
		verdict: '',
		duration_ms: 0,
		model_used: '',
		input_tokens: 0,
		output_tokens: 0,
		cache_creation_input_tokens: 0,
		cache_read_input_tokens: 0,
		title: '',
		version: '',
		project: '',
		prompt_id: '',
		project_id: '',
		project_status: '',
		tags: [],
		strategy: '',
		strategy_reasoning: '',
		strategy_confidence: 0,
		secondary_frameworks: [],
		created_at: '',
		codebase_context_snapshot: null,
	};
}

function makeTab(overrides?: Partial<WorkspaceTab>): WorkspaceTab {
	return {
		id: crypto.randomUUID(),
		name: 'Test',
		draft: createEmptyDraft(),
		resultId: null,
		mode: 'compose',
		...overrides,
	};
}

describe('tabCoherence', () => {
	beforeEach(() => {
		forgeSession.reset();
		optimizationState.reset();
		forgeMachine.reset();
		storageMap.clear();
	});

	describe('saveActiveTabState', () => {
		it('captures forgeResult.id and mode on the active tab', () => {
			const result = makeResult('res-1');
			optimizationState.forgeResult = result;
			forgeMachine.enterReview();

			saveActiveTabState();

			expect(forgeSession.activeTab.resultId).toBe('res-1');
			expect(forgeSession.activeTab.mode).toBe('review');
		});

		it('saves null resultId when no forgeResult', () => {
			forgeMachine.reset(); // compose

			saveActiveTabState();

			expect(forgeSession.activeTab.resultId).toBeNull();
			expect(forgeSession.activeTab.mode).toBe('compose');
		});

		it('resets forging mode to compose', () => {
			// Manually set mode to forging
			forgeMachine.mode = 'forging';

			saveActiveTabState();

			expect(forgeSession.activeTab.mode).toBe('compose');
		});
	});

	describe('restoreTabState', () => {
		it('restores review tab with cached result', () => {
			const result = makeResult('cached-1');
			optimizationState.resultHistory = [result];

			const tab = makeTab({ resultId: 'cached-1', mode: 'review' });
			restoreTabState(tab);

			expect(optimizationState.forgeResult).not.toBeNull();
			expect(optimizationState.forgeResult!.id).toBe('cached-1');
			expect(forgeMachine.mode).toBe('review');
		});

		it('clears forgeResult and resets to compose for compose tab', () => {
			optimizationState.forgeResult = makeResult('old');
			forgeMachine.enterReview();

			const tab = makeTab({ resultId: null, mode: 'compose' });
			restoreTabState(tab);

			expect(optimizationState.forgeResult).toBeNull();
			expect(forgeMachine.mode).toBe('compose');
		});

		it('falls back to compose and shows toast when result not in cache (async path)', async () => {
			// No cached result, mock fetchOptimization to return null
			const { fetchOptimization } = await import('$lib/api/client');
			vi.mocked(fetchOptimization).mockResolvedValue(null as any);
			const { toastState } = await import('$lib/stores/toast.svelte');

			const tab = makeTab({ id: 'tab-async', resultId: 'missing-1', mode: 'review' });
			forgeSession.tabs = [tab];
			forgeSession.activeTabId = tab.id;

			restoreTabState(tab);

			// Initially resets to compose
			expect(forgeMachine.mode).toBe('compose');

			// Wait for async fallback
			await vi.waitFor(() => {
				expect(tab.resultId).toBeNull();
				expect(tab.mode).toBe('compose');
			});

			expect(toastState.show).toHaveBeenCalledWith('Previous result could not be restored', 'info');
		});

		it('discards stale async restore when called rapidly', async () => {
			const { fetchOptimization } = await import('$lib/api/client');
			const { toastState } = await import('$lib/stores/toast.svelte');

			// First call resolves with a result, but slowly
			let resolveFirst: (v: any) => void;
			const firstPromise = new Promise(r => { resolveFirst = r; });
			// Second call resolves immediately with null (triggers compose fallback)
			vi.mocked(fetchOptimization)
				.mockReturnValueOnce(firstPromise as any)
				.mockResolvedValueOnce(null as any);

			// restoreResult delegates to fetchOptimization internally
			const restoreSpy = vi.spyOn(optimizationState, 'restoreResult');
			restoreSpy.mockReturnValueOnce(firstPromise.then(() => true) as any);
			restoreSpy.mockResolvedValueOnce(false);

			const tab1 = makeTab({ id: 'tab-1', resultId: 'res-1', mode: 'review' });
			const tab2 = makeTab({ id: 'tab-2', resultId: 'res-2', mode: 'review' });
			forgeSession.tabs = [tab1, tab2];
			forgeSession.activeTabId = tab1.id;

			// First restore (tab1)
			restoreTabState(tab1);

			// Immediately switch to tab2 — second restore supersedes the first
			forgeSession.activeTabId = tab2.id;
			restoreTabState(tab2);

			// Wait for second (fast) resolve
			await vi.waitFor(() => {
				expect(tab2.resultId).toBeNull();
				expect(tab2.mode).toBe('compose');
			});

			// Now resolve the first (stale) call
			resolveFirst!(null);
			await firstPromise.catch(() => {});

			// tab1 should NOT have been modified by the stale callback
			// (it still has its original resultId since the generation guard prevented the write)
			expect(tab1.resultId).toBe('res-1');

			restoreSpy.mockRestore();
		});
	});
});
