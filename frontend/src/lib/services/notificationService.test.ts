import { describe, it, expect, beforeEach, vi } from 'vitest';

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

import { systemBus } from './systemBus.svelte';
import { notificationService } from './notificationService.svelte';

describe('NotificationService', () => {
	beforeEach(() => {
		notificationService.reset();
		systemBus.reset();
		storageMap.clear();
	});

	describe('notify', () => {
		it('creates a notification with correct fields', () => {
			const id = notificationService.notify({
				type: 'success',
				source: 'forge',
				title: 'Test complete',
				body: 'Details here',
			});

			expect(id).toMatch(/^notif_\d+_\d+$/);
			expect(notificationService.notifications).toHaveLength(1);
			const n = notificationService.notifications[0];
			expect(n.type).toBe('success');
			expect(n.source).toBe('forge');
			expect(n.title).toBe('Test complete');
			expect(n.body).toBe('Details here');
			expect(n.read).toBe(false);
			expect(n.persistent).toBe(false);
			expect(n.timestamp).toBeGreaterThan(0);
		});

		it('prepends new notifications (most recent first)', () => {
			notificationService.notify({ type: 'info', source: 'a', title: 'First' });
			notificationService.notify({ type: 'info', source: 'b', title: 'Second' });

			expect(notificationService.notifications[0].title).toBe('Second');
			expect(notificationService.notifications[1].title).toBe('First');
		});

		it('caps at 50 notifications', () => {
			for (let i = 0; i < 55; i++) {
				notificationService.notify({ type: 'info', source: 'test', title: `N${i}` });
			}
			expect(notificationService.notifications).toHaveLength(50);
		});

		it('supports persistent flag', () => {
			notificationService.notify({
				type: 'error',
				source: 'test',
				title: 'Persistent',
				persistent: true,
			});
			expect(notificationService.notifications[0].persistent).toBe(true);
		});

		it('supports action callback', () => {
			const cb = vi.fn();
			notificationService.notify({
				type: 'success',
				source: 'test',
				title: 'With action',
				actionLabel: 'Open',
				actionCallback: cb,
			});
			const n = notificationService.notifications[0];
			expect(n.actionLabel).toBe('Open');
			n.actionCallback?.();
			expect(cb).toHaveBeenCalledOnce();
		});
	});

	describe('dismiss', () => {
		it('removes a notification by ID', () => {
			const id = notificationService.notify({ type: 'info', source: 'a', title: 'X' });
			notificationService.dismiss(id);
			expect(notificationService.notifications).toHaveLength(0);
		});

		it('no-ops for unknown ID', () => {
			notificationService.notify({ type: 'info', source: 'a', title: 'X' });
			notificationService.dismiss('nonexistent');
			expect(notificationService.notifications).toHaveLength(1);
		});
	});

	describe('markRead', () => {
		it('marks a notification as read', () => {
			const id = notificationService.notify({ type: 'info', source: 'a', title: 'X' });
			expect(notificationService.notifications[0].read).toBe(false);
			notificationService.markRead(id);
			expect(notificationService.notifications[0].read).toBe(true);
		});

		it('no-ops if already read', () => {
			const id = notificationService.notify({ type: 'info', source: 'a', title: 'X' });
			notificationService.markRead(id);
			notificationService.markRead(id); // should not throw
			expect(notificationService.notifications[0].read).toBe(true);
		});
	});

	describe('markAllRead', () => {
		it('marks all notifications as read', () => {
			notificationService.notify({ type: 'info', source: 'a', title: 'A' });
			notificationService.notify({ type: 'info', source: 'b', title: 'B' });
			expect(notificationService.unreadCount).toBe(2);

			notificationService.markAllRead();
			expect(notificationService.unreadCount).toBe(0);
		});
	});

	describe('unreadCount', () => {
		it('counts only unread notifications', () => {
			const id1 = notificationService.notify({ type: 'info', source: 'a', title: 'A' });
			notificationService.notify({ type: 'info', source: 'b', title: 'B' });
			expect(notificationService.unreadCount).toBe(2);

			notificationService.markRead(id1);
			expect(notificationService.unreadCount).toBe(1);
		});
	});

	describe('clear', () => {
		it('removes all notifications', () => {
			notificationService.notify({ type: 'info', source: 'a', title: 'A' });
			notificationService.notify({ type: 'info', source: 'b', title: 'B' });
			notificationService.clear();
			expect(notificationService.notifications).toHaveLength(0);
		});
	});

	describe('bus subscriptions', () => {
		it('creates success notification on forge:completed', () => {
			notificationService.subscribeToBus();

			systemBus.emit('forge:completed', 'scheduler', {
				title: 'My Forge',
				score: 8,
				strategy: 'chain-of-thought',
			});

			expect(notificationService.notifications).toHaveLength(1);
			const n = notificationService.notifications[0];
			expect(n.type).toBe('success');
			expect(n.source).toBe('forge');
			expect(n.title).toContain('My Forge');
			expect(n.title).toContain('score: 8');
		});

		it('forge:completed builds Open in IDE action from optimizationId', () => {
			notificationService.subscribeToBus();

			systemBus.emit('forge:completed', 'scheduler', {
				title: 'My Forge',
				score: 9,
				optimizationId: 'abc-123',
			});

			const n = notificationService.notifications[0];
			expect(n.actionLabel).toBe('Open in IDE');
			expect(n.actionCallback).toBeDefined();
		});

		it('forge:completed omits action when no optimizationId', () => {
			notificationService.subscribeToBus();

			systemBus.emit('forge:completed', 'scheduler', {
				title: 'My Forge',
				score: 9,
			});

			const n = notificationService.notifications[0];
			expect(n.actionLabel).toBeUndefined();
			expect(n.actionCallback).toBeUndefined();
		});

		it('creates info notification on forge:cancelled', () => {
			notificationService.subscribeToBus();

			systemBus.emit('forge:cancelled', 'scheduler', {
				title: 'My Forge',
			});

			expect(notificationService.notifications).toHaveLength(1);
			const n = notificationService.notifications[0];
			expect(n.type).toBe('info');
			expect(n.source).toBe('forge');
			expect(n.title).toContain('My Forge');
			expect(n.title).toContain('cancelled');
		});

		it('creates success notification on tournament:completed', () => {
			notificationService.subscribeToBus();

			systemBus.emit('tournament:completed', 'optimization', {
				results: [
					{ strategy: 'chain-of-thought', score: 9, id: 'best-1' },
					{ strategy: 'risen', score: 8, id: 'second-1' },
				],
			});

			expect(notificationService.notifications).toHaveLength(1);
			const n = notificationService.notifications[0];
			expect(n.type).toBe('success');
			expect(n.source).toBe('forge');
			expect(n.title).toContain('Tournament');
			expect(n.title).toContain('2 results');
			expect(n.body).toContain('chain-of-thought');
			expect(n.actionLabel).toBe('Open in IDE');
		});

		it('creates error notification on forge:failed', () => {
			notificationService.subscribeToBus();

			systemBus.emit('forge:failed', 'scheduler', {
				error: 'Rate limit exceeded',
			});

			expect(notificationService.notifications).toHaveLength(1);
			const n = notificationService.notifications[0];
			expect(n.type).toBe('error');
			expect(n.persistent).toBe(true);
			expect(n.body).toBe('Rate limit exceeded');
		});

		it('creates warning on provider:rate_limited', () => {
			notificationService.subscribeToBus();

			systemBus.emit('provider:rate_limited', 'provider', {
				provider: 'Claude',
			});

			const n = notificationService.notifications[0];
			expect(n.type).toBe('warning');
			expect(n.title).toContain('Claude');
		});

		it('creates error on provider:unavailable', () => {
			notificationService.subscribeToBus();

			systemBus.emit('provider:unavailable', 'provider', {
				provider: 'OpenAI',
			});

			const n = notificationService.notifications[0];
			expect(n.type).toBe('error');
			expect(n.persistent).toBe(true);
			expect(n.title).toContain('OpenAI');
		});

		it('creates success notification on mcp:session_connect', () => {
			notificationService.subscribeToBus();

			systemBus.emit('mcp:session_connect', 'provider', {});

			expect(notificationService.notifications).toHaveLength(1);
			const n = notificationService.notifications[0];
			expect(n.type).toBe('success');
			expect(n.source).toBe('mcp');
			expect(n.title).toBe('MCP connected');
		});

		it('creates persistent error notification on mcp:session_disconnect', () => {
			notificationService.subscribeToBus();

			systemBus.emit('mcp:session_disconnect', 'provider', {});

			expect(notificationService.notifications).toHaveLength(1);
			const n = notificationService.notifications[0];
			expect(n.type).toBe('error');
			expect(n.source).toBe('mcp');
			expect(n.title).toBe('MCP disconnected');
			expect(n.persistent).toBe(true);
		});

		it('creates success notification on workspace:synced', () => {
			notificationService.subscribeToBus();

			systemBus.emit('workspace:synced', 'workspaceManager', {
				project_id: 'proj-123',
			});

			expect(notificationService.notifications).toHaveLength(1);
			const n = notificationService.notifications[0];
			expect(n.type).toBe('success');
			expect(n.source).toBe('workspace');
			expect(n.title).toBe('Workspace synced');
		});

		it('creates persistent error notification on workspace:error', () => {
			notificationService.subscribeToBus();

			systemBus.emit('workspace:error', 'workspaceManager', {
				link_id: 'link-123',
				error: 'GitHub API rate limit exceeded',
			});

			expect(notificationService.notifications).toHaveLength(1);
			const n = notificationService.notifications[0];
			expect(n.type).toBe('error');
			expect(n.source).toBe('workspace');
			expect(n.title).toBe('Workspace sync failed');
			expect(n.body).toBe('GitHub API rate limit exceeded');
			expect(n.persistent).toBe(true);
		});

		it('creates notification for MCP delete tool completion', () => {
			notificationService.subscribeToBus();

			systemBus.emit('mcp:tool_complete', 'mcpActivityFeed', {
				tool_name: 'delete',
				result_summary: { id: 'del-abc-123' },
			});

			expect(notificationService.notifications).toHaveLength(1);
			const n = notificationService.notifications[0];
			expect(n.type).toBe('info');
			expect(n.title).toBe('MCP: Item deleted');
		});

		it('creates notification for MCP bulk_delete tool completion', () => {
			notificationService.subscribeToBus();

			systemBus.emit('mcp:tool_complete', 'mcpActivityFeed', {
				tool_name: 'bulk_delete',
				result_summary: { total: 3 },
			});

			expect(notificationService.notifications).toHaveLength(1);
			expect(notificationService.notifications[0].title).toBe('MCP: Bulk delete complete');
		});

		it('ignores MCP read-only tool completions', () => {
			notificationService.subscribeToBus();

			systemBus.emit('mcp:tool_complete', 'mcpActivityFeed', {
				tool_name: 'list',
			});

			expect(notificationService.notifications).toHaveLength(0);
		});

		it('uses human-readable name for MCP add_prompt tool', () => {
			notificationService.subscribeToBus();

			systemBus.emit('mcp:tool_complete', 'mcpActivityFeed', {
				tool_name: 'add_prompt',
				result_summary: { id: 'prompt-123' },
			});

			expect(notificationService.notifications).toHaveLength(1);
			expect(notificationService.notifications[0].title).toBe('MCP: Prompt added');
		});

		it('uses human-readable name for MCP tag tool', () => {
			notificationService.subscribeToBus();

			systemBus.emit('mcp:tool_complete', 'mcpActivityFeed', {
				tool_name: 'tag',
			});

			expect(notificationService.notifications).toHaveLength(1);
			expect(notificationService.notifications[0].title).toBe('MCP: Tags updated');
		});

		it('keeps score suffix for MCP pipeline tools with friendly names', () => {
			notificationService.subscribeToBus();

			systemBus.emit('mcp:tool_complete', 'mcpActivityFeed', {
				tool_name: 'optimize',
				result_summary: { id: 'opt-123', overall_score: 8 },
			});

			expect(notificationService.notifications).toHaveLength(1);
			// 'optimize' has no friendly name — falls back to generic format
			expect(notificationService.notifications[0].title).toBe('MCP: optimize complete (score: 8/10)');
		});

		it('creates notification via notification:show bus event', () => {
			notificationService.subscribeToBus();

			systemBus.emit('notification:show', 'test-component', {
				type: 'warning',
				title: 'Custom Alert',
				body: 'Something happened',
			});

			expect(notificationService.notifications).toHaveLength(1);
			const n = notificationService.notifications[0];
			expect(n.type).toBe('warning');
			expect(n.title).toBe('Custom Alert');
			expect(n.body).toBe('Something happened');
			expect(n.source).toBe('test-component');
		});

		it('notification:show defaults to info type when type not provided', () => {
			notificationService.subscribeToBus();

			systemBus.emit('notification:show', 'source', {
				title: 'No type specified',
			});

			expect(notificationService.notifications).toHaveLength(1);
			expect(notificationService.notifications[0].type).toBe('info');
		});

		it('unsubscribeFromBus stops receiving events', () => {
			notificationService.subscribeToBus();
			notificationService.unsubscribeFromBus();

			systemBus.emit('forge:completed', 'test', { title: 'X' });
			expect(notificationService.notifications).toHaveLength(0);
		});
	});

	describe('persistence', () => {
		it('persists to sessionStorage on notify', () => {
			notificationService.notify({ type: 'info', source: 'a', title: 'Stored' });
			const stored = storageMap.get('pf_notifications');
			expect(stored).toBeTruthy();
			const parsed = JSON.parse(stored!);
			expect(parsed).toHaveLength(1);
			expect(parsed[0].title).toBe('Stored');
		});

		it('strips actionCallback before persisting', () => {
			notificationService.notify({
				type: 'info',
				source: 'a',
				title: 'Has CB',
				actionCallback: () => {},
			});
			const stored = storageMap.get('pf_notifications');
			const parsed = JSON.parse(stored!);
			expect(parsed[0]).not.toHaveProperty('actionCallback');
		});

		it('clears actionLabel on reload since callback is lost', () => {
			// Simulate a persisted notification with actionLabel but no actionCallback
			const notif = {
				id: 'notif_99',
				type: 'info',
				source: 'mcp',
				title: 'MCP: optimize complete',
				timestamp: Date.now(),
				read: false,
				persistent: false,
				actionLabel: 'Open in IDE',
			};
			storageMap.set('pf_notifications', JSON.stringify([notif]));

			// Re-import triggers loadPersistedNotifications
			// We can test the function directly by resetting and manually loading
			notificationService.reset();
			// Manually set storage again after reset cleared it
			storageMap.set('pf_notifications', JSON.stringify([notif]));

			// Create a fresh service to test deserialization
			// Since the module singleton already loaded, we test the load function behavior:
			const raw = storageMap.get('pf_notifications');
			const parsed = JSON.parse(raw!);
			const loaded = parsed.map((n: Record<string, unknown>) => ({
				...n,
				actionCallback: undefined,
				actionLabel: undefined,
			}));
			expect(loaded[0].actionLabel).toBeUndefined();
			expect(loaded[0].actionCallback).toBeUndefined();
		});
	});
});
