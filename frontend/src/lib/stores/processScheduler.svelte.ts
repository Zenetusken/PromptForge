/**
 * Process Scheduler — kernel-level process management for forge pipelines.
 *
 * Layer 1 (Kernel) in the PromptForge OS stack.
 * Extracted from forgeMachine.svelte.ts — adds queuing, PIDs, priorities, and bus events.
 */

import { systemBus } from '$lib/services/systemBus.svelte';
import { settingsState } from '$lib/stores/settings.svelte';
import type { OptimizationResultState } from '$lib/stores/optimization.svelte';
import type { OptimizeMetadata } from '$lib/api/client';

export type ProcessStatus = 'queued' | 'running' | 'paused' | 'completed' | 'error' | 'cancelled';
export type ProcessPriority = 'interactive' | 'background' | 'batch';

export interface ForgeProcess {
	id: string;
	pid: number;
	parentPid: number | null;
	status: ProcessStatus;
	priority: ProcessPriority;
	title: string;
	promptHash: string;
	currentStage: string | null;
	progress: number;
	result: OptimizationResultState | null;
	error: string | null;
	score: number | null;
	strategy: string | null;
	optimizationId: string | null;
	startedAt: number;
	completedAt: number | null;
	metadata: OptimizeMetadata | null;
}

export interface SpawnConfig {
	title: string;
	priority?: ProcessPriority;
	parentPid?: number | null;
	promptHash?: string;
	metadata?: OptimizeMetadata;
	/** Called when process transitions to 'running' (immediately or after promotion from queue). */
	onExecute?: () => void;
}

const MAX_PROCESSES = 10;
const STORAGE_KEY = 'pf_scheduler_processes';
const ACTIVE_KEY = 'pf_scheduler_active';
let pidCounter = 0;

function loadPersistedProcesses(): ForgeProcess[] {
	if (typeof window === 'undefined') return [];
	try {
		const raw = sessionStorage.getItem(STORAGE_KEY);
		if (raw) {
			const parsed: ForgeProcess[] = JSON.parse(raw);
			// Restore PID counter from highest PID
			for (const p of parsed) {
				if (p.pid > pidCounter) pidCounter = p.pid;
			}
			// On hydrate: running/queued processes can't resume — mark them as error
			return parsed.map(p =>
				p.status === 'running' || p.status === 'queued'
					? { ...p, status: 'error' as const, error: 'Session interrupted' }
					: p
			);
		}
	} catch {
		// ignore
	}
	return [];
}

function loadPersistedActiveId(): string | null {
	if (typeof window === 'undefined') return null;
	try {
		return sessionStorage.getItem(ACTIVE_KEY);
	} catch {
		return null;
	}
}

class ProcessScheduler {
	processes: ForgeProcess[] = $state(loadPersistedProcesses());
	activeProcessId: string | null = $state(loadPersistedActiveId());
	maxConcurrent: number = $state(settingsState.maxConcurrentForges);

	/** Non-serialized execution callbacks keyed by process id. */
	private _onExecute: Map<string, () => void> = new Map();

	/** Timestamp (ms) when rate limit cooldown expires. */
	rateLimitedUntil: number = $state(0);
	private _rateLimitTimer: ReturnType<typeof setTimeout> | null = null;

	// --- Derived state ---

	get queue(): ForgeProcess[] {
		return this.processes.filter(p => p.status === 'queued');
	}

	get running(): ForgeProcess[] {
		return this.processes.filter(p => p.status === 'running');
	}

	get completed(): ForgeProcess[] {
		return this.processes.filter(p => p.status === 'completed');
	}

	get runningCount(): number {
		return this.processes.filter(p => p.status === 'running').length;
	}

	get canSpawn(): boolean {
		if (Date.now() < this.rateLimitedUntil) return false;
		return this.runningCount < this.maxConcurrent;
	}

	get activeProcess(): ForgeProcess | null {
		if (!this.activeProcessId) return null;
		return this.processes.find(p => p.id === this.activeProcessId) ?? null;
	}

	/** Initialize bus subscriptions. Call once from +layout.svelte onMount. */
	init(): () => void {
		// Sync maxConcurrent from settings
		const unsubSettings = $effect.root(() => {
			$effect(() => {
				this.maxConcurrent = settingsState.maxConcurrentForges;
			});
		});

		// Pause promotion during rate limits
		const unsubRateLimit = systemBus.on('provider:rate_limited', (event) => {
			const retryAfter = (event.payload as { retryAfter?: number } | undefined)?.retryAfter ?? 30;
			this.rateLimitedUntil = Date.now() + retryAfter * 1000;
			// Schedule promotion retry after cooldown
			if (this._rateLimitTimer) clearTimeout(this._rateLimitTimer);
			this._rateLimitTimer = setTimeout(() => {
				this.rateLimitedUntil = 0;
				this._rateLimitTimer = null;
				this._promoteNext();
			}, retryAfter * 1000);
		});

		return () => {
			unsubSettings();
			unsubRateLimit();
			if (this._rateLimitTimer) {
				clearTimeout(this._rateLimitTimer);
				this._rateLimitTimer = null;
			}
		};
	}

	// --- Process lifecycle ---

	/**
	 * Spawn a new forge process. If at max concurrent, it's queued.
	 * Returns the process (status will be 'running' or 'queued').
	 */
	spawn(config: SpawnConfig): ForgeProcess {
		const id = typeof crypto !== 'undefined' ? crypto.randomUUID() : Math.random().toString();
		const pid = ++pidCounter;
		const status: ProcessStatus = this.canSpawn ? 'running' : 'queued';

		const process: ForgeProcess = {
			id,
			pid,
			parentPid: config.parentPid ?? null,
			status,
			priority: config.priority ?? 'interactive',
			title: config.title || 'Untitled Forge',
			promptHash: config.promptHash ?? '',
			currentStage: null,
			progress: 0,
			result: null,
			error: null,
			score: null,
			strategy: null,
			optimizationId: null,
			startedAt: Date.now(),
			completedAt: null,
			metadata: config.metadata ?? null,
		};

		// LRU eviction: remove oldest completed/error if at limit
		if (this.processes.length >= MAX_PROCESSES) {
			const evictIdx = this.processes.findLastIndex(
				p => p.status === 'completed' || p.status === 'error' || p.status === 'cancelled'
			);
			if (evictIdx >= 0) {
				this.processes.splice(evictIdx, 1);
			}
		}

		// Store execution callback (non-serialized)
		if (config.onExecute) {
			this._onExecute.set(id, config.onExecute);
		}

		this.processes = [process, ...this.processes];
		this.activeProcessId = id;
		this._persist();

		systemBus.emit('forge:started', 'processScheduler', {
			pid,
			id,
			title: config.title,
			status,
		});

		// If immediately running, invoke the execution callback
		if (status === 'running') {
			this._onExecute.get(id)?.();
		}

		return process;
	}

	/**
	 * Mark a process as completed with result data.
	 */
	complete(id: string, data: {
		score?: number | null;
		strategy?: string | null;
		optimizationId?: string | null;
		result?: OptimizationResultState | null;
	}): void {
		const proc = this.processes.find(p => p.id === id);
		if (!proc) return;
		this._onExecute.delete(id);
		proc.status = 'completed';
		proc.score = data.score ?? null;
		proc.strategy = data.strategy ?? null;
		proc.optimizationId = data.optimizationId ?? null;
		proc.result = data.result ?? null;
		proc.completedAt = Date.now();
		this.processes = [...this.processes];
		this._persist();

		systemBus.emit('forge:completed', 'processScheduler', {
			pid: proc.pid,
			id: proc.id,
			title: proc.title,
			score: proc.score,
			strategy: proc.strategy,
			optimizationId: proc.optimizationId,
		});

		// Promote next queued process
		this._promoteNext();
	}

	/**
	 * Mark a process as failed.
	 */
	fail(id: string, error?: string): void {
		const proc = this.processes.find(p => p.id === id);
		if (!proc) return;
		this._onExecute.delete(id);
		proc.status = 'error';
		proc.error = error ?? 'Unknown error';
		proc.completedAt = Date.now();
		this.processes = [...this.processes];
		this._persist();

		systemBus.emit('forge:failed', 'processScheduler', {
			pid: proc.pid,
			id: proc.id,
			title: proc.title,
			error: proc.error,
		});

		this._promoteNext();
	}

	/**
	 * Cancel a running or queued process.
	 */
	cancel(pid: number): void {
		const proc = this.processes.find(p => p.pid === pid);
		if (!proc || (proc.status !== 'running' && proc.status !== 'queued')) return;
		this._onExecute.delete(proc.id);
		proc.status = 'cancelled';
		proc.completedAt = Date.now();
		this.processes = [...this.processes];
		this._persist();

		systemBus.emit('forge:cancelled', 'processScheduler', {
			pid: proc.pid,
			id: proc.id,
			title: proc.title,
			optimizationId: proc.optimizationId,
		});

		this._promoteNext();
	}

	/**
	 * Dismiss (remove) a process from the list. Only non-running processes.
	 */
	dismiss(pid: number): void {
		const proc = this.processes.find(p => p.pid === pid);
		if (!proc || proc.status === 'running') return;
		this._onExecute.delete(proc.id);
		this.processes = this.processes.filter(p => p.pid !== pid);
		if (this.activeProcessId === proc.id) {
			this.activeProcessId = this.processes[0]?.id ?? null;
		}
		this._persist();
	}

	/**
	 * Promote a queued process to higher priority.
	 */
	promote(pid: number): void {
		const proc = this.processes.find(p => p.pid === pid);
		if (!proc || proc.status !== 'queued') return;
		proc.priority = 'interactive';
		this.processes = [...this.processes];
		this._persist();
	}

	/**
	 * Update progress for a running process.
	 */
	updateProgress(id: string, stage: string, progress: number): void {
		const proc = this.processes.find(p => p.id === id);
		if (!proc || proc.status !== 'running') return;
		proc.currentStage = stage;
		proc.progress = Math.min(Math.max(progress, 0), 1);
		this.processes = [...this.processes];
		// Don't persist on every progress update to avoid excessive writes
	}

	/**
	 * Find a process by its optimizer-assigned UUID (for SSE event correlation).
	 */
	findById(id: string): ForgeProcess | null {
		return this.processes.find(p => p.id === id) ?? null;
	}

	/**
	 * Find a process by PID.
	 */
	findByPid(pid: number): ForgeProcess | null {
		return this.processes.find(p => p.pid === pid) ?? null;
	}

	/**
	 * Full reset for testing.
	 */
	reset(): void {
		this.processes = [];
		this.activeProcessId = null;
		this.maxConcurrent = settingsState.maxConcurrentForges;
		this._onExecute.clear();
		pidCounter = 0;
		if (typeof window !== 'undefined') {
			try {
				sessionStorage.removeItem(STORAGE_KEY);
				sessionStorage.removeItem(ACTIVE_KEY);
			} catch { /* ignore */ }
		}
	}

	// --- Private ---

	private _promoteNext(): void {
		if (!this.canSpawn) return;
		// Find highest-priority queued process
		const queued = this.processes
			.filter(p => p.status === 'queued')
			.sort((a, b) => {
				const priorityOrder = { interactive: 0, background: 1, batch: 2 };
				return (priorityOrder[a.priority] ?? 2) - (priorityOrder[b.priority] ?? 2);
			});
		const next = queued[0];
		if (next) {
			next.status = 'running';
			next.startedAt = Date.now();
			this.processes = [...this.processes];
			this._persist();

			systemBus.emit('forge:started', 'processScheduler', {
				pid: next.pid,
				id: next.id,
				title: next.title,
				status: 'running',
				promoted: true,
			});

			// Execute the deferred work (starts the SSE stream)
			this._onExecute.get(next.id)?.();
		}
	}

	private _persist(): void {
		if (typeof window === 'undefined') return;
		try {
			// Strip non-serializable result objects to keep storage small
			const serializable = this.processes.map(({ result, metadata, ...rest }) => rest);
			sessionStorage.setItem(STORAGE_KEY, JSON.stringify(serializable));
			if (this.activeProcessId) {
				sessionStorage.setItem(ACTIVE_KEY, this.activeProcessId);
			} else {
				sessionStorage.removeItem(ACTIVE_KEY);
			}
		} catch {
			// ignore
		}
	}
}

export const processScheduler = new ProcessScheduler();
