/**
 * MCP Activity Feed — SSE client for real-time MCP tool call tracking.
 *
 * Layer 2 (System Services) in the PromptForge OS stack.
 * Connects to /api/mcp/events SSE stream, maintains reactive state,
 * and emits events on the SystemBus for cross-component integration.
 */

import { systemBus, type BusEventType } from './systemBus.svelte';

const API_BASE = import.meta.env.VITE_API_URL || '';

// --- Types ---

export interface MCPActivityEvent {
	id: string;
	event_type: string;
	tool_name?: string;
	call_id?: string;
	client_id?: string;
	timestamp: string;
	progress?: number;
	message?: string;
	duration_ms?: number;
	error?: string;
	result_summary?: Record<string, unknown>;
}

export interface ActiveToolCall {
	call_id: string;
	tool_name: string;
	client_id?: string;
	startedAt: number;
	progress?: number;
	message?: string;
}

/** Raw shape from the backend /api/mcp/status snapshot. */
interface MCPStatusRaw {
	subscriber_count: number;
	active_calls: Array<{
		call_id: string;
		tool_name: string;
		client_id?: string;
		timestamp: string;
		progress?: number;
		message?: string;
	}>;
	session_count: number;
	total_events: number;
}

export interface MCPStatus {
	subscriber_count: number;
	active_calls: ActiveToolCall[];
	session_count: number;
	total_events: number;
}

// --- SSE Event Type → Bus Event Type mapping ---

const EVENT_TYPE_MAP: Record<string, BusEventType> = {
	tool_start: 'mcp:tool_start',
	tool_progress: 'mcp:tool_progress',
	tool_complete: 'mcp:tool_complete',
	tool_error: 'mcp:tool_error',
	session_connect: 'mcp:session_connect',
	session_disconnect: 'mcp:session_disconnect',
};

/** MCP tool names that modify data — used for notifications and history reload. */
export const MCP_WRITE_TOOLS = [
	'optimize', 'retry', 'batch', 'cancel',
	'create_project', 'add_prompt', 'update_prompt', 'set_project_context',
	'delete', 'bulk_delete', 'tag', 'sync_workspace',
] as const;

/**
 * Canonical mapping of MCP tool names → Tailwind text color classes.
 * Categories: Pipeline=cyan, Query=blue, Organize=purple, Projects=green, Destructive=red.
 * Single source of truth — import in components that display tool-specific colors.
 */
export const MCP_TOOL_COLORS: Record<string, string> = {
	// Pipeline
	optimize: 'text-neon-cyan',
	retry: 'text-neon-cyan',
	batch: 'text-neon-cyan',
	cancel: 'text-neon-red',
	// Query
	get: 'text-neon-blue',
	list: 'text-neon-blue',
	get_by_project: 'text-neon-blue',
	search: 'text-neon-blue',
	// Organize
	tag: 'text-neon-purple',
	stats: 'text-neon-blue',
	strategies: 'text-neon-blue',
	// Projects
	create_project: 'text-neon-green',
	get_project: 'text-neon-green',
	list_projects: 'text-neon-green',
	add_prompt: 'text-neon-green',
	update_prompt: 'text-neon-green',
	set_project_context: 'text-neon-green',
	// Workspace
	sync_workspace: 'text-neon-green',
	// Destructive
	delete: 'text-neon-red',
	bulk_delete: 'text-neon-red',
};

const MAX_EVENTS = 100;
const MAX_BACKOFF = 30_000;
const INITIAL_BACKOFF = 3_000;

class MCPActivityFeed {
	connected = $state(false);
	events: MCPActivityEvent[] = $state([]);
	activeCalls: ActiveToolCall[] = $state([]);
	sessionCount = $state(0);
	totalEventsReceived = $state(0);

	private _abortController: AbortController | null = null;
	private _reconnectTimer: ReturnType<typeof setTimeout> | null = null;
	private _backoff = INITIAL_BACKOFF;
	private _snapshotPhase = true;
	private _snapshotTimer: ReturnType<typeof setTimeout> | null = null;
	private _lastEventId: string | null = null;
	private _connecting = false;

	/**
	 * Start the SSE connection. Safe to call multiple times — guards
	 * against concurrent connect attempts from rapid $effect re-runs.
	 */
	connect(): void {
		if (this._connecting || this.connected) return;
		this._connecting = true;
		this._startStream().finally(() => { this._connecting = false; });
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
	}

	/**
	 * Reset all state. Used for testing.
	 */
	reset(): void {
		this.disconnect();
		this.events = [];
		this.activeCalls = [];
		this.sessionCount = 0;
		this.totalEventsReceived = 0;
		this._lastEventId = null;
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
			const response = await fetch(`${API_BASE}/api/mcp/events`, {
				signal,
				headers,
			});

			if (!response.ok || !response.body) {
				throw new Error(`SSE connect failed: ${response.status}`);
			}

			this.connected = true;
			this._backoff = INITIAL_BACKOFF;
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
				let currentData = '';

				for (const line of lines) {
					if (line.startsWith('event: ')) {
						currentEventType = line.slice(7).trim();
					} else if (line.startsWith('data: ')) {
						currentData = line.slice(6);
					} else if (line.startsWith('id: ')) {
						// SSE protocol id field — tracked via parsed JSON in _handleActivity
					} else if (line === '' && currentEventType && currentData) {
						this._handleSSEEvent(currentEventType, currentData);
						currentEventType = '';
						currentData = '';
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
		this._reconnectTimer = setTimeout(() => {
			this._reconnectTimer = null;
			this._backoff = Math.min(this._backoff * 1.5, MAX_BACKOFF);
			this._startStream();
		}, this._backoff);
	}

	private _handleSSEEvent(eventType: string, data: string): void {
		try {
			const parsed = JSON.parse(data);

			if (eventType === 'mcp_status') {
				this._handleStatus(parsed as MCPStatusRaw);
				return;
			}

			if (eventType === 'mcp_activity') {
				const event = parsed as MCPActivityEvent;
				this._handleActivity(event);
				return;
			}
		} catch {
			// Malformed JSON — skip
		}
	}

	private _handleStatus(status: MCPStatusRaw): void {
		this.sessionCount = status.session_count;
		// Backend sends `timestamp` (ISO string); convert to epoch ms for `startedAt`
		this.activeCalls = (status.active_calls || []).map((c) => ({
			call_id: c.call_id,
			tool_name: c.tool_name,
			client_id: c.client_id,
			startedAt: c.timestamp ? new Date(c.timestamp).getTime() : Date.now(),
			progress: c.progress,
			message: c.message,
		}));
	}

	private _handleActivity(event: MCPActivityEvent): void {
		// Track for Last-Event-ID reconnection
		if (event.id) {
			this._lastEventId = event.id;
		}

		// Add to events list (newest first) — mutate in place to avoid GC churn
		this.events.unshift(event);
		if (this.events.length > MAX_EVENTS) this.events.length = MAX_EVENTS;
		this.totalEventsReceived++;

		// Update active calls
		switch (event.event_type) {
			case 'tool_start':
				if (event.call_id) {
					this.activeCalls = [
						{
							call_id: event.call_id,
							tool_name: event.tool_name ?? 'unknown',
							client_id: event.client_id,
							startedAt: Date.now(),
							progress: 0,
							message: event.message,
						},
						...this.activeCalls,
					];
				}
				break;
			case 'tool_progress':
				if (event.call_id) {
					this.activeCalls = this.activeCalls.map((c) =>
						c.call_id === event.call_id
							? { ...c, progress: event.progress, message: event.message }
							: c,
					);
				}
				break;
			case 'tool_complete':
			case 'tool_error':
				if (event.call_id) {
					this.activeCalls = this.activeCalls.filter(
						(c) => c.call_id !== event.call_id,
					);
				}
				break;
			case 'session_connect':
				this.sessionCount++;
				break;
			case 'session_disconnect':
				this.sessionCount = Math.max(0, this.sessionCount - 1);
				break;
		}

		// Don't emit bus events for snapshot replay events — prevents notification
		// flooding on SSE connect/reconnect. Events still populate the event log.
		if (!this._snapshotPhase) {
			const busType = EVENT_TYPE_MAP[event.event_type];
			if (busType) {
				systemBus.emit(busType, 'mcpActivityFeed', {
					tool_name: event.tool_name,
					call_id: event.call_id,
					duration_ms: event.duration_ms,
					error: event.error,
					result_summary: event.result_summary,
				});
			}
		}
	}
}

export const mcpActivityFeed = new MCPActivityFeed();
