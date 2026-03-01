/**
 * System Bus — decoupled IPC for inter-store communication.
 *
 * Layer 3 (System Libraries) in the PromptForge OS stack.
 * All cross-store events flow through the bus instead of direct imports.
 */

// --- Core event types ---

export type BusEventType =
	| 'forge:started'
	| 'forge:completed'
	| 'forge:failed'
	| 'forge:cancelled'
	| 'forge:progress'
	| 'provider:available'
	| 'provider:rate_limited'
	| 'provider:unavailable'
	| 'clipboard:copied'
	| 'window:opened'
	| 'window:closed'
	| 'window:focused'
	| 'history:reload'
	| 'stats:reload'
	| 'notification:show'
	| 'tournament:completed'
	| 'mcp:tool_start'
	| 'mcp:tool_progress'
	| 'mcp:tool_complete'
	| 'mcp:tool_error'
	| 'mcp:session_connect'
	| 'mcp:session_disconnect'
	| 'workspace:synced'
	| 'workspace:error'
	| 'workspace:connected'
	| 'workspace:disconnected'
	| 'snap:created'
	| 'snap:dissolved'
	| 'snap:window_added'
	| 'snap:window_removed'
	| 'fs:moved'
	| 'fs:created'
	| 'fs:deleted'
	| 'fs:renamed'
	| 'transform:completed'
	| 'transform:failed'
	| 'kernel:app_enabled'
	| 'kernel:app_disabled'
	| 'kernel:audit_logged'
	| 'kernel:job_submitted'
	| 'kernel:job_started'
	| 'kernel:job_progress'
	| 'kernel:job_completed'
	| 'kernel:job_failed'
	| 'kernel:event'
	| 'textforge:prefill';

export interface BusEvent {
	type: BusEventType;
	source: string;
	payload: Record<string, unknown>;
	timestamp: number;
	id: string;
}

type BusHandler = (event: BusEvent) => void;

const MAX_RECENT = 50;
let eventCounter = 0;

class SystemBus {
	recentEvents: BusEvent[] = $state([]);

	private _handlers = new Map<string, Set<BusHandler>>();
	private _wildcardHandlers = new Set<BusHandler>();

	/**
	 * Emit an event on the bus. All matching handlers are called synchronously.
	 */
	emit(type: BusEventType, source: string, payload: Record<string, unknown> = {}): void {
		const event: BusEvent = {
			type,
			source,
			payload,
			timestamp: Date.now(),
			id: `evt_${++eventCounter}`,
		};

		// Record for debugging/terminal
		this.recentEvents = [event, ...this.recentEvents].slice(0, MAX_RECENT);

		// Type-specific handlers
		const handlers = this._handlers.get(type);
		if (handlers) {
			for (const handler of handlers) {
				try {
					handler(event);
				} catch {
					// Don't let one handler break others
				}
			}
		}

		// Wildcard handlers (listen to all events)
		for (const handler of this._wildcardHandlers) {
			try {
				handler(event);
			} catch {
				// Don't let one handler break others
			}
		}
	}

	/**
	 * Subscribe to events of a given type. Returns an unsubscribe function.
	 * Pass '*' to subscribe to all events.
	 */
	on(type: BusEventType | '*', handler: BusHandler): () => void {
		if (type === '*') {
			this._wildcardHandlers.add(handler);
			return () => { this._wildcardHandlers.delete(handler); };
		}
		if (!this._handlers.has(type)) {
			this._handlers.set(type, new Set());
		}
		this._handlers.get(type)!.add(handler);
		return () => {
			this._handlers.get(type)?.delete(handler);
			if (this._handlers.get(type)?.size === 0) {
				this._handlers.delete(type);
			}
		};
	}

	/**
	 * Subscribe to a single occurrence of an event type. Auto-unsubscribes after first fire.
	 */
	once(type: BusEventType | '*', handler: BusHandler): () => void {
		const unsub = this.on(type, (event) => {
			unsub();
			handler(event);
		});
		return unsub;
	}

	/**
	 * Remove all handlers. Used for testing cleanup.
	 */
	reset(): void {
		this._handlers.clear();
		this._wildcardHandlers.clear();
		this.recentEvents = [];
		eventCounter = 0;
	}

	/**
	 * Number of registered handlers (for debugging).
	 */
	get handlerCount(): number {
		let count = this._wildcardHandlers.size;
		for (const set of this._handlers.values()) {
			count += set.size;
		}
		return count;
	}
}

export const systemBus = new SystemBus();
