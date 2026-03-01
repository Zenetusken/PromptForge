/**
 * Kernel Bus Bridge — SSE client bridging backend EventBus to frontend SystemBus.
 *
 * Reuses the mcpActivityFeed SSE pattern: $state connected flag, AbortController,
 * exponential backoff reconnect, Last-Event-ID, snapshot phase suppression.
 */

import { systemBus, type BusEventType } from '$lib/services/systemBus.svelte';

const API_BASE = import.meta.env.VITE_API_URL || '';

// --- Backend event_type → frontend BusEventType mapping ---

const EVENT_TYPE_MAP: Record<string, BusEventType> = {
	'kernel:app.enabled': 'kernel:app_enabled',
	'kernel:app.disabled': 'kernel:app_disabled',
	'kernel:audit.logged': 'kernel:audit_logged',
	'kernel:job.submitted': 'kernel:job_submitted',
	'kernel:job.started': 'kernel:job_started',
	'kernel:job.progress': 'kernel:job_progress',
	'kernel:job.completed': 'kernel:job_completed',
	'kernel:job.failed': 'kernel:job_failed',
};

const MAX_BACKOFF = 30_000;
const INITIAL_BACKOFF = 3_000;

class KernelBusBridge {
	connected = $state(false);

	private _abortController: AbortController | null = null;
	private _reconnectTimer: ReturnType<typeof setTimeout> | null = null;
	private _backoff = INITIAL_BACKOFF;
	private _snapshotPhase = true;
	private _snapshotTimer: ReturnType<typeof setTimeout> | null = null;
	private _lastEventId: string | null = null;
	private _connecting = false;

	/**
	 * Start the SSE connection to the kernel bus.
	 * Safe to call multiple times — guards against concurrent connect attempts.
	 */
	connect(): void {
		if (this._connecting || this.connected) return;
		this._connecting = true;
		this._startStream().finally(() => {
			this._connecting = false;
		});
	}

	/**
	 * Stop the SSE connection and cleanup.
	 */
	disconnect(): void {
		if (this._snapshotTimer) {
			clearTimeout(this._snapshotTimer);
			this._snapshotTimer = null;
		}
		if (this._reconnectTimer) {
			clearTimeout(this._reconnectTimer);
			this._reconnectTimer = null;
		}
		if (this._abortController) {
			this._abortController.abort();
			this._abortController = null;
		}
		this.connected = false;
		this._connecting = false;
	}

	/**
	 * Publish an event to the backend bus via POST.
	 */
	async publish(eventType: string, data: Record<string, unknown> = {}, sourceApp = 'frontend'): Promise<void> {
		const res = await fetch(`${API_BASE}/api/kernel/bus/publish`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ event_type: eventType, data, source_app: sourceApp }),
		});
		if (!res.ok) {
			const body = await res.json().catch(() => ({}));
			throw new Error(body.detail || `Publish failed: ${res.status}`);
		}
	}

	/**
	 * Reset all state. Used for testing.
	 */
	reset(): void {
		this.disconnect();
		this._lastEventId = null;
		this._backoff = INITIAL_BACKOFF;
	}

	private async _startStream(): Promise<void> {
		if (this._abortController) {
			this._abortController.abort();
		}
		this._abortController = new AbortController();
		const { signal } = this._abortController;

		try {
			const headers: Record<string, string> = { Accept: 'text/event-stream' };
			if (this._lastEventId) {
				headers['Last-Event-ID'] = this._lastEventId;
			}
			const response = await fetch(`${API_BASE}/api/kernel/bus/events`, {
				signal,
				headers,
			});

			if (!response.ok || !response.body) {
				throw new Error(`SSE connect failed: ${response.status}`);
			}

			this.connected = true;
			this._backoff = INITIAL_BACKOFF;

			// Snapshot phase: suppress bus emissions for 2s to avoid notification flooding
			this._snapshotPhase = true;
			if (this._snapshotTimer) clearTimeout(this._snapshotTimer);
			this._snapshotTimer = setTimeout(() => {
				this._snapshotPhase = false;
				this._snapshotTimer = null;
			}, 2000);

			const reader = response.body.getReader();
			const decoder = new TextDecoder();
			let buffer = '';

			while (true) {
				const { done, value } = await reader.read();
				if (done) break;

				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split('\n');
				buffer = lines.pop() ?? '';

				let currentEventType = '';
				let currentDataLines: string[] = [];
				let currentId = '';

				for (const line of lines) {
					if (line.startsWith('event: ')) {
						currentEventType = line.slice(7).trim();
					} else if (line.startsWith('data: ')) {
						currentDataLines.push(line.slice(6));
					} else if (line.startsWith('id: ')) {
						currentId = line.slice(4).trim();
					} else if (line === '' && currentDataLines.length > 0) {
						if (currentId) {
							this._lastEventId = currentId;
						}
						this._handleEvent(currentEventType, currentDataLines.join('\n'));
						currentEventType = '';
						currentDataLines = [];
						currentId = '';
					} else if (line.startsWith(':')) {
						// Comment (keepalive) — ignore
					}
				}
			}
		} catch (err: unknown) {
			if (err instanceof Error && err.name === 'AbortError') return;
			// Connection lost — schedule reconnect
		}

		this.connected = false;
		this._scheduleReconnect();
	}

	private _scheduleReconnect(): void {
		if (this._reconnectTimer) return;
		// Add jitter (±25%) to prevent thundering herd on reconnect
		const jitter = this._backoff * (0.75 + Math.random() * 0.5);
		this._reconnectTimer = setTimeout(() => {
			this._reconnectTimer = null;
			this._backoff = Math.min(this._backoff * 1.5, MAX_BACKOFF);
			this._startStream();
		}, jitter);
	}

	private _handleEvent(_sseEventType: string, data: string): void {
		try {
			const parsed = JSON.parse(data);
			const backendEventType: string = parsed.event_type || 'unknown';
			const sourceApp: string = parsed.source_app || 'unknown';

			// Map to known frontend bus event type, or use generic passthrough
			const busType: BusEventType = EVENT_TYPE_MAP[backendEventType] || 'kernel:event';

			// During snapshot phase, still emit state-sync events (app status, job updates)
			// but suppress notification-triggering events to avoid flooding
			if (this._snapshotPhase) {
				// Always forward state-sync events that UI components need
				const stateEvents: BusEventType[] = [
					'kernel:app_enabled', 'kernel:app_disabled',
					'kernel:job_submitted', 'kernel:job_completed', 'kernel:job_failed',
				];
				if (!stateEvents.includes(busType)) return;
			}

			systemBus.emit(busType, `kernel:${sourceApp}`, {
				backend_event_type: backendEventType,
				...parsed,
			});
		} catch {
			// Malformed JSON — skip
		}
	}
}

export const kernelBusBridge = new KernelBusBridge();
