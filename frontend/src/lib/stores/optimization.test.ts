import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock all external dependencies before importing the store
vi.mock('$lib/api/client', () => ({
    fetchOptimize: vi.fn(),
    fetchRetry: vi.fn(),
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

import { optimizationState } from './optimization.svelte';
import { fetchOptimize, fetchRetry, orchestrateAnalyze } from '$lib/api/client';
import { historyState } from '$lib/stores/history.svelte';
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
        it('populates result from history item without pipeline', () => {
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

            optimizationState.loadFromHistory(item as any);

            expect(optimizationState.result).not.toBeNull();
            expect(optimizationState.result!.id).toBe('hist-1');
            expect(optimizationState.result!.original).toBe('original');
            expect(optimizationState.result!.optimized).toBe('better');
            expect(optimizationState.currentRun).toBeNull();
            expect(optimizationState.isRunning).toBe(false);
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
