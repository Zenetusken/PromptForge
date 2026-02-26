import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock all external dependencies before importing the store
vi.mock('$lib/api/client', () => ({
    fetchOptimize: vi.fn(),
    fetchRetry: vi.fn(),
    fetchOptimization: vi.fn(),
    orchestrateAnalyze: vi.fn(),
    fetchHistory: vi.fn(),
    deleteOptimization: vi.fn(),
    clearAllHistory: vi.fn(),
    fetchHealth: vi.fn(),
    fetchProviders: vi.fn(),
    validateApiKey: vi.fn(),
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

vi.mock('$lib/stores/provider.svelte', () => ({
    providerState: { getLLMHeaders: vi.fn().mockReturnValue(undefined) },
}));

vi.mock('$lib/stores/toast.svelte', () => ({
    toastState: { show: vi.fn() },
}));

vi.mock('$lib/stores/forgeMachine.svelte', () => ({
    forgeMachine: {
        enterReview: vi.fn(),
    },
}));

vi.mock('$lib/stores/windowManager.svelte', () => ({
    windowManager: {
        openIDE: vi.fn(),
        closeIDE: vi.fn(),
        ideSpawned: false,
        ideVisible: false,
    },
}));

vi.mock('$lib/stores/processScheduler.svelte', () => ({
    processScheduler: {
        spawn: vi.fn((opts: { onExecute?: () => void; title?: string }) => {
            const proc = { id: `proc-${Math.random().toString(36).slice(2, 8)}`, pid: 1, status: 'running', title: opts.title || '' };
            // Call onExecute synchronously — matches real scheduler behavior
            opts.onExecute?.();
            return proc;
        }),
        complete: vi.fn(),
        fail: vi.fn(),
        updateProgress: vi.fn(),
    },
}));

vi.mock('$lib/services/systemBus.svelte', () => ({
    systemBus: {
        on: vi.fn(() => vi.fn()),
        emit: vi.fn(),
        recentEvents: [],
    },
}));

vi.mock('$lib/stores/sessionContext.svelte', () => ({
    sessionContext: {
        record: vi.fn(),
        hasContext: false,
        buildContextHint: vi.fn().mockReturnValue(''),
        reset: vi.fn(),
    },
}));

import { optimizationState } from './optimization.svelte';
import { fetchOptimize, fetchRetry, fetchOptimization, orchestrateAnalyze } from '$lib/api/client';
import { historyState } from '$lib/stores/history.svelte';
import { forgeMachine } from '$lib/stores/forgeMachine.svelte';
import { windowManager } from '$lib/stores/windowManager.svelte';
import { promptAnalysis } from '$lib/stores/promptAnalysis.svelte';
import { toastState } from '$lib/stores/toast.svelte';
import type { PipelineEvent } from '$lib/api/client';

describe('OptimizationState', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.useFakeTimers();
        optimizationState.reset();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    describe('initial state', () => {
        it('starts with no run, no result, not running', () => {
            expect(optimizationState.currentRun).toBeNull();
            expect(optimizationState.result).toBeNull();
            expect(optimizationState.isRunning).toBe(false);
            expect(optimizationState.error).toBeNull();
        });
    });

    describe('startOptimization', () => {
        it('sets isRunning and initializes pipeline steps', () => {
            const mockController = new AbortController();
            vi.mocked(fetchOptimize).mockReturnValue(mockController);

            optimizationState.startOptimization('test prompt');

            expect(optimizationState.isRunning).toBe(true);
            expect(optimizationState.currentRun).not.toBeNull();
            expect(optimizationState.currentRun!.steps).toHaveLength(4);
            expect(optimizationState.currentRun!.steps[0].name).toBe('analyze');
            expect(optimizationState.currentRun!.steps[0].status).toBe('pending');
        });

        it('calls fetchOptimize with prompt and LLM headers', () => {
            const mockController = new AbortController();
            vi.mocked(fetchOptimize).mockReturnValue(mockController);

            optimizationState.startOptimization('test prompt', { title: 'Test' });

            expect(fetchOptimize).toHaveBeenCalledOnce();
            expect(fetchOptimize).toHaveBeenCalledWith(
                'test prompt',
                expect.any(Function),
                expect.any(Function),
                { title: 'Test' },
                undefined,
            );
        });

        it('clears previous error and result', () => {
            const mockController = new AbortController();
            vi.mocked(fetchOptimize).mockReturnValue(mockController);

            // Simulate previous error state
            optimizationState.startOptimization('first');
            // Now start a new one
            optimizationState.startOptimization('second');

            expect(optimizationState.error).toBeNull();
            expect(optimizationState.result).toBeNull();
        });
    });

    describe('handleEvent (via startOptimization callback)', () => {
        let onEvent: (event: PipelineEvent) => void;

        beforeEach(() => {
            const mockController = new AbortController();
            vi.mocked(fetchOptimize).mockImplementation((prompt, handler, onError, meta, headers) => {
                onEvent = handler;
                return mockController;
            });
            optimizationState.startOptimization('test prompt');
        });

        it('step_start marks step as running', () => {
            onEvent({ type: 'step_start', step: 'analyze', message: 'Starting analysis' });

            const step = optimizationState.currentRun!.steps.find(s => s.name === 'analyze');
            expect(step!.status).toBe('running');
        });

        it('step_complete marks step as complete with data', () => {
            onEvent({ type: 'step_start', step: 'analyze' });
            onEvent({
                type: 'step_complete',
                step: 'analyze',
                data: { task_type: 'coding', step_duration_ms: 500 },
            });

            const step = optimizationState.currentRun!.steps.find(s => s.name === 'analyze');
            expect(step!.status).toBe('complete');
            expect(step!.data).toEqual({ task_type: 'coding', step_duration_ms: 500 });
        });

        it('step_progress appends streaming content', () => {
            onEvent({ type: 'step_start', step: 'analyze' });
            onEvent({ type: 'step_progress', step: 'analyze', data: { content: 'Line 1' } });
            onEvent({ type: 'step_progress', step: 'analyze', data: { content: 'Line 2' } });

            const step = optimizationState.currentRun!.steps.find(s => s.name === 'analyze');
            expect(step!.streamingContent).toContain('Line 1');
            expect(step!.streamingContent).toContain('Line 2');
        });

        it('strategy_selected sets strategyData and marks step complete immediately', () => {
            onEvent({
                type: 'strategy_selected',
                data: { strategy: 'role-based', reasoning: 'Best fit', confidence: 0.9, task_type: 'coding' },
            });

            expect(optimizationState.currentRun!.strategyData).toBeDefined();
            expect(optimizationState.currentRun!.strategyData!.strategy).toBe('role-based');

            // Strategy step completes immediately (no artificial delay)
            const step = optimizationState.currentRun!.steps.find(s => s.name === 'strategy');
            expect(step!.status).toBe('complete');
        });

        it('result sets result state and marks all steps complete', () => {
            onEvent({
                type: 'result',
                data: {
                    id: 'abc-123',
                    optimized_prompt: 'Better prompt',
                    task_type: 'coding',
                    complexity: 'medium',
                    overall_score: 0.85,
                },
            });

            expect(optimizationState.isRunning).toBe(false);
            expect(optimizationState.result).not.toBeNull();
            expect(optimizationState.result!.id).toBe('abc-123');
            expect(optimizationState.result!.optimized).toBe('Better prompt');

            // All steps should be complete
            for (const step of optimizationState.currentRun!.steps) {
                expect(step.status).toBe('complete');
            }
        });

        it('result triggers toast and history reload', () => {
            onEvent({
                type: 'result',
                data: { id: 'abc-123', optimized_prompt: 'Better' },
            });

            expect(toastState.show).toHaveBeenCalledWith('Optimization complete!', 'success');
            // Reload is debounced by 500ms
            vi.advanceTimersByTime(500);
            expect(historyState.loadHistory).toHaveBeenCalled();
        });

        it('result pushes to resultHistory', () => {
            const prevLen = optimizationState.resultHistory.length;
            onEvent({
                type: 'result',
                data: { id: 'abc-123', optimized_prompt: 'Better' },
            });

            expect(optimizationState.resultHistory.length).toBe(prevLen + 1);
            expect(optimizationState.resultHistory[0].id).toBe('abc-123');
        });

        it('error sets error and stops running', () => {
            onEvent({ type: 'error', error: 'Something went wrong' });

            expect(optimizationState.error).toBe('Something went wrong');
            expect(optimizationState.isRunning).toBe(false);
        });

        it('error marks running steps as error', () => {
            onEvent({ type: 'step_start', step: 'analyze' });
            onEvent({ type: 'error', error: 'Failed' });

            const step = optimizationState.currentRun!.steps.find(s => s.name === 'analyze');
            expect(step!.status).toBe('error');
        });

        it('error shows toast', () => {
            onEvent({ type: 'error', error: 'Oops' });
            expect(toastState.show).toHaveBeenCalledWith('Oops', 'error');
        });
    });

    describe('cancel', () => {
        it('aborts controller and sets isRunning false', () => {
            const mockController = new AbortController();
            vi.mocked(fetchOptimize).mockReturnValue(mockController);

            optimizationState.startOptimization('test');
            optimizationState.cancel();

            expect(mockController.signal.aborted).toBe(true);
            expect(optimizationState.isRunning).toBe(false);
        });
    });

    describe('reset', () => {
        it('clears all state', () => {
            const mockController = new AbortController();
            vi.mocked(fetchOptimize).mockReturnValue(mockController);

            optimizationState.startOptimization('test');
            optimizationState.reset();

            expect(optimizationState.currentRun).toBeNull();
            expect(optimizationState.result).toBeNull();
            expect(optimizationState.error).toBeNull();
            expect(optimizationState.isRunning).toBe(false);
        });
    });

    describe('retryOptimization', () => {
        it('calls fetchRetry with id and sets up pipeline', () => {
            const mockController = new AbortController();
            vi.mocked(fetchRetry).mockReturnValue(mockController);

            optimizationState.retryOptimization('retry-id', 'original prompt');

            expect(optimizationState.isRunning).toBe(true);
            expect(fetchRetry).toHaveBeenCalledWith(
                'retry-id',
                expect.any(Function),
                expect.any(Function),
                undefined,
            );
        });
    });

    describe('loadFromHistory', () => {
        const item = {
            id: 'hist-1',
            created_at: '2024-01-01',
            raw_prompt: 'original',
            optimized_prompt: 'better',
            task_type: 'coding',
            complexity: 'medium',
            weaknesses: ['vague'],
            strengths: ['clear'],
            changes_made: ['added context'],
            framework_applied: 'role-based',
            optimization_notes: 'notes',
            strategy_reasoning: null,
            strategy_confidence: null,
            clarity_score: 0.9,
            specificity_score: 0.8,
            structure_score: 0.7,
            faithfulness_score: 0.85,
            overall_score: 0.81,
            is_improvement: true,
            verdict: 'Improved',
            duration_ms: 1500,
            model_used: 'claude',
            input_tokens: 100,
            output_tokens: 50,
            status: 'completed',
            error_message: null,
            project: 'proj',
            tags: ['tag1'],
            title: 'Test',
        };

        it('populates viewResult from history item without pipeline', () => {
            optimizationState.loadFromHistory(item as any);

            expect(optimizationState.viewResult).not.toBeNull();
            expect(optimizationState.viewResult!.id).toBe('hist-1');
            expect(optimizationState.viewResult!.original).toBe('original');
            expect(optimizationState.viewResult!.optimized).toBe('better');
            expect(optimizationState.currentRun).toBeNull();
            expect(optimizationState.isRunning).toBe(false);
        });

        it('result getter returns viewResult when forgeResult is null', () => {
            optimizationState.loadFromHistory(item as any);
            expect(optimizationState.result).not.toBeNull();
            expect(optimizationState.result!.id).toBe('hist-1');
            expect(optimizationState.forgeResult).toBeNull();
        });

        it('does not clobber forgeResult', () => {
            // Simulate a forgeResult being set
            const mockController = new AbortController();
            vi.mocked(fetchOptimize).mockImplementation((prompt, handler) => {
                handler({
                    type: 'result',
                    data: { id: 'forge-1', optimized_prompt: 'Forged' },
                });
                return mockController;
            });
            optimizationState.startOptimization('test');
            expect(optimizationState.forgeResult).not.toBeNull();

            // Now load from history — should not touch forgeResult
            optimizationState.loadFromHistory(item as any);
            expect(optimizationState.forgeResult!.id).toBe('forge-1');
            expect(optimizationState.viewResult!.id).toBe('hist-1');
            // result getter prefers forgeResult
            expect(optimizationState.result!.id).toBe('forge-1');
        });
    });

    describe('resetForge', () => {
        it('clears forgeResult but preserves viewResult', () => {
            const item = {
                id: 'hist-1', created_at: '2024-01-01', raw_prompt: 'test',
                optimized_prompt: 'better', status: 'completed',
            };
            optimizationState.loadFromHistory(item as any);
            expect(optimizationState.viewResult).not.toBeNull();

            optimizationState.resetForge();

            expect(optimizationState.forgeResult).toBeNull();
            expect(optimizationState.viewResult).not.toBeNull();
        });
    });

    describe('openInIDE', () => {
        const mockResult = {
            id: 'ide-1',
            original: 'original',
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
            title: 'Test',
            version: '',
            project: '',
            prompt_id: '',
            project_id: '',
            project_status: '',
            tags: [],
            strategy: 'co-star',
            strategy_reasoning: '',
            strategy_confidence: 0,
            secondary_frameworks: [],
            created_at: '2024-01-01',
        };

        it('sets forgeResult and calls enterReview + openIDE', () => {
            optimizationState.openInIDE(mockResult as any);

            expect(optimizationState.forgeResult).not.toBeNull();
            expect(optimizationState.forgeResult!.id).toBe('ide-1');
            expect(forgeMachine.enterReview).toHaveBeenCalled();
            expect(windowManager.openIDE).toHaveBeenCalled();
        });

        it('overwrites previous forgeResult', () => {
            optimizationState.openInIDE({ ...mockResult, id: 'first' } as any);
            optimizationState.openInIDE({ ...mockResult, id: 'second' } as any);

            expect(optimizationState.forgeResult!.id).toBe('second');
        });
    });

    describe('openInIDEFromHistory', () => {
        it('fetches optimization and calls openInIDE', async () => {
            const historyItem = {
                id: 'fetch-1',
                raw_prompt: 'original',
                optimized_prompt: 'better',
                status: 'completed',
                created_at: '2024-01-01',
            };
            vi.mocked(fetchOptimization).mockResolvedValue(historyItem as any);

            await optimizationState.openInIDEFromHistory('fetch-1');

            expect(fetchOptimization).toHaveBeenCalledWith('fetch-1');
            expect(optimizationState.forgeResult).not.toBeNull();
            expect(optimizationState.forgeResult!.id).toBe('fetch-1');
            expect(forgeMachine.enterReview).toHaveBeenCalled();
            expect(windowManager.openIDE).toHaveBeenCalled();
        });

        it('does not set forgeResult when fetch returns null', async () => {
            vi.mocked(fetchOptimization).mockResolvedValue(null as any);

            await optimizationState.openInIDEFromHistory('missing');

            expect(optimizationState.forgeResult).toBeNull();
        });
    });

    describe('restoreResult', () => {
        it('returns cached result from resultHistory', async () => {
            // Push a result into resultHistory via event
            const mockController = new AbortController();
            vi.mocked(fetchOptimize).mockImplementation((prompt, handler) => {
                handler({
                    type: 'result',
                    data: { id: 'cached-1', optimized_prompt: 'Cached' },
                });
                return mockController;
            });
            optimizationState.startOptimization('test');
            vi.advanceTimersByTime(500);
            optimizationState.resetForge();

            const ok = await optimizationState.restoreResult('cached-1');

            expect(ok).toBe(true);
            expect(optimizationState.forgeResult).not.toBeNull();
            expect(optimizationState.forgeResult!.id).toBe('cached-1');
        });

        it('fetches from server when not in cache', async () => {
            const historyItem = {
                id: 'server-1',
                raw_prompt: 'original',
                optimized_prompt: 'better',
                status: 'completed',
                created_at: '2024-01-01',
            };
            vi.mocked(fetchOptimization).mockResolvedValue(historyItem as any);

            const ok = await optimizationState.restoreResult('server-1');

            expect(ok).toBe(true);
            expect(fetchOptimization).toHaveBeenCalledWith('server-1');
            expect(optimizationState.forgeResult).not.toBeNull();
            expect(optimizationState.forgeResult!.id).toBe('server-1');
        });

        it('returns false when result not found', async () => {
            vi.mocked(fetchOptimization).mockResolvedValue(null as any);

            const ok = await optimizationState.restoreResult('missing-1');

            expect(ok).toBe(false);
            expect(optimizationState.forgeResult).toBeNull();
        });
    });

    describe('runNodeAnalyze', () => {
        const analysisResponse = {
            task_type: 'coding',
            complexity: 'medium',
            strengths: ['clear intent'],
            weaknesses: ['too vague'],
            step_duration_ms: 1200,
        };

        it('sets isAnalyzing true during the call', async () => {
            let resolve: (v: typeof analysisResponse) => void;
            vi.mocked(orchestrateAnalyze).mockReturnValue(
                new Promise(r => { resolve = r; })
            );

            const promise = optimizationState.runNodeAnalyze({ prompt: 'test' });

            expect(optimizationState.isAnalyzing).toBe(true);

            resolve!(analysisResponse);
            await promise;

            expect(optimizationState.isAnalyzing).toBe(false);
        });

        it('populates analysisResult on completion', async () => {
            vi.mocked(orchestrateAnalyze).mockResolvedValue(analysisResponse);

            await optimizationState.runNodeAnalyze({ prompt: 'test' });

            expect(optimizationState.analysisResult).not.toBeNull();
            expect(optimizationState.analysisResult!.task_type).toBe('coding');
            expect(optimizationState.analysisResult!.complexity).toBe('medium');
            expect(optimizationState.analysisResult!.strengths).toEqual(['clear intent']);
            expect(optimizationState.analysisResult!.weaknesses).toEqual(['too vague']);
        });

        it('calls promptAnalysis.updateFromPipeline with returned task type', async () => {
            vi.mocked(orchestrateAnalyze).mockResolvedValue(analysisResponse);

            await optimizationState.runNodeAnalyze({ prompt: 'test' });

            expect(promptAnalysis.updateFromPipeline).toHaveBeenCalledWith('coding', 'medium');
        });

        it('does not call updateFromPipeline when task_type is missing', async () => {
            vi.mocked(orchestrateAnalyze).mockResolvedValue({ step_duration_ms: 500 } as any);

            await optimizationState.runNodeAnalyze({ prompt: 'test' });

            expect(promptAnalysis.updateFromPipeline).not.toHaveBeenCalled();
        });

        it('clearAnalysis nulls out currentRun and analysisResult', async () => {
            vi.mocked(orchestrateAnalyze).mockResolvedValue(analysisResponse);

            await optimizationState.runNodeAnalyze({ prompt: 'test' });
            expect(optimizationState.analysisResult).not.toBeNull();

            optimizationState.clearAnalysis();

            expect(optimizationState.currentRun).toBeNull();
            expect(optimizationState.analysisResult).toBeNull();
        });

        it('shows error toast on failure', async () => {
            vi.mocked(orchestrateAnalyze).mockRejectedValue(new Error('Network error'));

            await optimizationState.runNodeAnalyze({ prompt: 'test' });

            expect(optimizationState.isAnalyzing).toBe(false);
            expect(toastState.show).toHaveBeenCalledWith(expect.any(String), 'error');
        });
    });
});
