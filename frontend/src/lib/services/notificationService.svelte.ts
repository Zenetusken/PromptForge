/**
 * Notification Service — structured notification system.
 *
 * Layer 2 (System Services) in the PromptForge OS stack.
 * Replaces ad-hoc toast calls with categorized, actionable notifications.
 * Subscribes to system bus events for automated notifications.
 */

import { systemBus } from './systemBus.svelte';
import { MCP_WRITE_TOOLS } from './mcpActivityFeed.svelte';

export interface SystemNotification {
	id: string;
	type: 'info' | 'success' | 'warning' | 'error';
	source: string;
	title: string;
	body?: string;
	timestamp: number;
	read: boolean;
	persistent: boolean;
	actionLabel?: string;
	actionCallback?: () => void;
}

export interface NotifyConfig {
	type: SystemNotification['type'];
	source: string;
	title: string;
	body?: string;
	persistent?: boolean;
	actionLabel?: string;
	actionCallback?: () => void;
}

/** Human-readable names for non-pipeline MCP write tools. */
const MCP_TOOL_FRIENDLY_NAMES: Record<string, string> = {
	add_prompt: 'Prompt added',
	update_prompt: 'Prompt updated',
	set_project_context: 'Context profile updated',
	tag: 'Tags updated',
	create_project: 'Project created',
	delete: 'Item deleted',
	bulk_delete: 'Bulk delete complete',
};

const MAX_NOTIFICATIONS = 50;
const STORAGE_KEY = 'pf_notifications';

function loadPersistedNotifications(): SystemNotification[] {
	if (typeof window === 'undefined') return [];
	try {
		const raw = sessionStorage.getItem(STORAGE_KEY);
		if (raw) {
			const parsed: SystemNotification[] = JSON.parse(raw);
			// Strip action callbacks (can't serialize functions) and deduplicate IDs
			const seen = new Set<string>();
			const deduped: SystemNotification[] = [];
			for (const n of parsed) {
				const clean = { ...n, actionCallback: undefined, actionLabel: undefined };
				if (!seen.has(clean.id)) {
					seen.add(clean.id);
					deduped.push(clean);
				}
			}
			return deduped;
		}
	} catch {
		// ignore
	}
	return [];
}

/**
 * Seed the counter from persisted notifications so new IDs never collide.
 * Old scheme used `notif_<n>` — extract the max N to continue from there.
 * New IDs use a timestamp + random suffix for collision-proof uniqueness.
 */
let notifCounter = (() => {
	const persisted = loadPersistedNotifications();
	let max = 0;
	for (const n of persisted) {
		const m = n.id.match(/^notif_(\d+)$/);
		if (m) max = Math.max(max, Number(m[1]));
	}
	return max;
})();

class NotificationService {
	notifications: SystemNotification[] = $state(loadPersistedNotifications());

	get unreadCount(): number {
		return this.notifications.filter(n => !n.read).length;
	}

	private _unsubscribers: (() => void)[] = [];

	/**
	 * Create a new notification. Returns its ID.
	 */
	notify(config: NotifyConfig): string {
		const id = `notif_${Date.now()}_${++notifCounter}`;
		const notification: SystemNotification = {
			id,
			type: config.type,
			source: config.source,
			title: config.title,
			body: config.body,
			timestamp: Date.now(),
			read: false,
			persistent: config.persistent ?? false,
			actionLabel: config.actionLabel,
			actionCallback: config.actionCallback,
		};

		this.notifications = [notification, ...this.notifications].slice(0, MAX_NOTIFICATIONS);
		this._persist();
		return id;
	}

	dismiss(id: string): void {
		this.notifications = this.notifications.filter(n => n.id !== id);
		this._persist();
	}

	markRead(id: string): void {
		const n = this.notifications.find(n => n.id === id);
		if (n && !n.read) {
			n.read = true;
			this.notifications = [...this.notifications]; // trigger reactivity
			this._persist();
		}
	}

	markAllRead(): void {
		let changed = false;
		for (const n of this.notifications) {
			if (!n.read) { n.read = true; changed = true; }
		}
		if (changed) {
			this.notifications = [...this.notifications];
			this._persist();
		}
	}

	clear(): void {
		this.notifications = [];
		this._persist();
	}

	/**
	 * Subscribe to system bus events for automated notifications.
	 * Call this once during app bootstrap.
	 */
	subscribeToBus(): void {
		this._unsubscribers.push(
			systemBus.on('forge:completed', (event) => {
				const title = (event.payload.title as string) || 'Forge';
				const score = event.payload.score as number | undefined;
				const scoreText = score != null ? ` (score: ${score})` : '';
				const optimizationId = event.payload.optimizationId as string | undefined;
				this.notify({
					type: 'success',
					source: 'forge',
					title: `${title} complete${scoreText}`,
					body: event.payload.strategy as string | undefined,
					actionLabel: optimizationId ? 'Open in IDE' : undefined,
					actionCallback: optimizationId
						? () => {
								import('$lib/stores/optimization.svelte').then(({ optimizationState }) => {
									import('$lib/stores/windowManager.svelte').then(({ windowManager }) => {
										optimizationState.openInIDEFromHistory(optimizationId);
										windowManager.openIDE();
									});
								});
							}
						: undefined,
				});
			}),

			systemBus.on('forge:failed', (event) => {
				this.notify({
					type: 'error',
					source: 'forge',
					title: 'Forge failed',
					body: (event.payload.error as string) || 'An unknown error occurred',
					persistent: true,
				});
			}),

			systemBus.on('forge:cancelled', (event) => {
				const title = (event.payload.title as string) || 'Forge';
				this.notify({
					type: 'info',
					source: 'forge',
					title: `${title} cancelled`,
				});
			}),

			systemBus.on('tournament:completed', (event) => {
				const results = event.payload.results as Array<{ strategy: string; score: number; id: string }> | undefined;
				const count = results?.length ?? 0;
				const best = results?.[0];
				const scoreText = best ? ` — best: ${best.score}/10` : '';
				this.notify({
					type: 'success',
					source: 'forge',
					title: `Tournament complete (${count} results${scoreText})`,
					body: best ? `Top strategy: ${best.strategy}` : undefined,
					actionLabel: best?.id ? 'Open in IDE' : undefined,
					actionCallback: best?.id
						? () => {
								import('$lib/stores/optimization.svelte').then(({ optimizationState }) => {
									import('$lib/stores/windowManager.svelte').then(({ windowManager }) => {
										optimizationState.openInIDEFromHistory(best.id);
										windowManager.openIDE();
									});
								});
							}
						: undefined,
				});
			}),

			systemBus.on('provider:rate_limited', (event) => {
				const provider = (event.payload.provider as string) || 'LLM provider';
				this.notify({
					type: 'warning',
					source: 'provider',
					title: `${provider} rate limited`,
					body: 'Requests are being throttled. Retry in a moment.',
				});
			}),

			systemBus.on('provider:unavailable', (event) => {
				const provider = (event.payload.provider as string) || 'LLM provider';
				this.notify({
					type: 'error',
					source: 'provider',
					title: `${provider} unavailable`,
					body: 'Check your API key and connection settings.',
					persistent: true,
				});
			}),

			// MCP activity notifications (write tools only)
			systemBus.on('mcp:tool_complete', (event) => {
				const tool = event.payload.tool_name as string | undefined;
				if (!tool || !(MCP_WRITE_TOOLS as readonly string[]).includes(tool)) return;
				const summary = event.payload.result_summary as Record<string, unknown> | undefined;
				const score = summary?.overall_score as number | undefined;
				const id = summary?.id as string | undefined;
				const scoreText = score != null ? ` (score: ${score}/10)` : '';
				const friendlyName = MCP_TOOL_FRIENDLY_NAMES[tool];
				const title = friendlyName
					? `MCP: ${friendlyName}${scoreText}`
					: `MCP: ${tool} complete${scoreText}`;
				this.notify({
					type: 'info',
					source: 'mcp',
					title,
					body: id ? `ID: ${id.slice(0, 8)}...` : undefined,
					actionLabel: id && tool !== 'cancel' ? 'Open in IDE' : undefined,
					actionCallback: id && tool !== 'cancel'
						? () => {
								import('$lib/stores/optimization.svelte').then(({ optimizationState }) => {
									import('$lib/stores/windowManager.svelte').then(({ windowManager }) => {
										optimizationState.openInIDEFromHistory(id);
										windowManager.openIDE();
									});
								});
							}
						: undefined,
				});
			}),

			systemBus.on('mcp:tool_error', (event) => {
				const tool = event.payload.tool_name as string | undefined;
				this.notify({
					type: 'warning',
					source: 'mcp',
					title: `MCP: ${tool ?? 'tool'} failed`,
					body: (event.payload.error as string) || 'An error occurred',
				});
			}),

			systemBus.on('mcp:session_connect', () => {
				this.notify({
					type: 'success',
					source: 'mcp',
					title: 'MCP connected',
				});
			}),

			systemBus.on('mcp:session_disconnect', () => {
				this.notify({
					type: 'error',
					source: 'mcp',
					title: 'MCP disconnected',
					persistent: true,
				});
			}),

			// Workspace events
			systemBus.on('workspace:synced', (event) => {
				const project = event.payload.project_id as string | undefined;
				this.notify({
					type: 'success',
					source: 'workspace',
					title: 'Workspace synced',
					body: project ? `Project workspace updated` : undefined,
				});
			}),

			systemBus.on('workspace:error', (event) => {
				this.notify({
					type: 'error',
					source: 'workspace',
					title: 'Workspace sync failed',
					body: (event.payload.error as string) || 'An error occurred during sync',
					persistent: true,
				});
			}),

			// Generic notification channel — any component can emit via bus
			systemBus.on('notification:show', (event) => {
				const p = event.payload as Record<string, unknown>;
				this.notify({
					type: (p.type as SystemNotification['type']) || 'info',
					source: (p.source as string) || event.source,
					title: (p.title as string) || 'Notification',
					body: p.body as string | undefined,
					persistent: p.persistent as boolean | undefined,
					actionLabel: p.actionLabel as string | undefined,
					actionCallback: p.actionCallback as (() => void) | undefined,
				});
			}),
		);
	}

	/**
	 * Unsubscribe from all bus events. Used for cleanup/testing.
	 */
	unsubscribeFromBus(): void {
		for (const unsub of this._unsubscribers) unsub();
		this._unsubscribers = [];
	}

	/**
	 * Full reset for testing.
	 */
	reset(): void {
		this.unsubscribeFromBus();
		this.notifications = [];
		notifCounter = 0;
		if (typeof window !== 'undefined') {
			try { sessionStorage.removeItem(STORAGE_KEY); } catch { /* ignore */ }
		}
	}

	private _persist(): void {
		if (typeof window === 'undefined') return;
		try {
			// Strip non-serializable callbacks before persisting
			const serializable = this.notifications.map(({ actionCallback, ...rest }) => rest);
			sessionStorage.setItem(STORAGE_KEY, JSON.stringify(serializable));
		} catch {
			// ignore
		}
	}
}

export const notificationService = new NotificationService();
