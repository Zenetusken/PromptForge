import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';

// --- Mocks ---

const mockLogs = [
	{
		id: 1,
		app_id: 'promptforge',
		action: 'create',
		resource_type: 'project',
		resource_id: 'abc-123-def-456-ghi-789',
		details: { name: 'Test Project' },
		timestamp: new Date().toISOString(),
	},
	{
		id: 2,
		app_id: 'textforge',
		action: 'delete',
		resource_type: 'optimization',
		resource_id: 'opt-999',
		details: null,
		timestamp: new Date(Date.now() - 120_000).toISOString(),
	},
];

const mockFetchAuditLogs = vi.fn().mockResolvedValue({ logs: mockLogs, total: 2 });
const mockFetchApps = vi.fn().mockResolvedValue({
	apps: [
		{ id: 'promptforge', name: 'PromptForge', version: '1.0', status: 'enabled' },
		{ id: 'textforge', name: 'TextForge', version: '1.0', status: 'enabled' },
	],
});

vi.mock('$lib/kernel/services/auditClient', () => ({
	fetchAuditLogs: (...args: unknown[]) => mockFetchAuditLogs(...args),
}));

vi.mock('$lib/kernel/services/appManagerClient', () => ({
	fetchApps: () => mockFetchApps(),
}));

vi.mock('$lib/kernel/services/kernelBusBridge.svelte', () => ({
	kernelBusBridge: { connected: false },
}));

// Track bus subscriptions so we can trigger them in tests
const busHandlers: Record<string, Array<(...args: unknown[]) => void>> = {};
vi.mock('$lib/services/systemBus.svelte', () => ({
	systemBus: {
		on: (event: string, handler: (...args: unknown[]) => void) => {
			if (!busHandlers[event]) busHandlers[event] = [];
			busHandlers[event].push(handler);
			return () => {
				const idx = busHandlers[event]?.indexOf(handler);
				if (idx !== undefined && idx >= 0) busHandlers[event].splice(idx, 1);
			};
		},
		emit: (event: string, ...args: unknown[]) => {
			busHandlers[event]?.forEach((h) => h(...args));
		},
	},
}));

import AuditLogWindow from './AuditLogWindow.svelte';

describe('AuditLogWindow', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		document.body.innerHTML = '';
		mockFetchAuditLogs.mockClear();
		mockFetchApps.mockClear();
		mockFetchAuditLogs.mockResolvedValue({ logs: mockLogs, total: 2 });
		mockFetchApps.mockResolvedValue({
			apps: [
				{ id: 'promptforge', name: 'PromptForge', version: '1.0', status: 'enabled' },
				{ id: 'textforge', name: 'TextForge', version: '1.0', status: 'enabled' },
			],
		});
		// Clear bus handlers
		for (const key of Object.keys(busHandlers)) {
			busHandlers[key] = [];
		}
	});

	afterEach(() => {
		vi.runAllTimers();
		cleanup();
		vi.useRealTimers();
	});

	it('renders table with audit log entries', async () => {
		render(AuditLogWindow);
		await vi.advanceTimersByTimeAsync(10);

		expect(mockFetchAuditLogs).toHaveBeenCalled();
		// 'promptforge' appears in both dropdown option and table cell
		expect(screen.getAllByText('promptforge').length).toBeGreaterThanOrEqual(1);
		// Table-specific content
		expect(screen.getByText('create')).toBeTruthy();
		expect(screen.getByText('project')).toBeTruthy();
	});

	it('shows entry count', async () => {
		render(AuditLogWindow);
		await vi.advanceTimersByTimeAsync(10);

		expect(screen.getByText('2 entries')).toBeTruthy();
	});

	it('fetches apps for dynamic filter on mount', async () => {
		render(AuditLogWindow);
		await vi.advanceTimersByTimeAsync(10);

		expect(mockFetchApps).toHaveBeenCalled();
	});

	it('app filter change triggers reload with correct params', async () => {
		render(AuditLogWindow);
		await vi.advanceTimersByTimeAsync(10);

		const select = document.querySelector('select');
		expect(select).toBeTruthy();

		// Change to promptforge filter
		if (select) {
			select.value = 'promptforge';
			await fireEvent.change(select);
			await vi.advanceTimersByTimeAsync(10);
		}

		// Should have been called with 'promptforge' app filter
		const lastCall = mockFetchAuditLogs.mock.calls[mockFetchAuditLogs.mock.calls.length - 1];
		expect(lastCall[0]).toBe('promptforge');
	});

	it('bus event kernel:audit_logged triggers reload', async () => {
		render(AuditLogWindow);
		await vi.advanceTimersByTimeAsync(10);

		const callCount = mockFetchAuditLogs.mock.calls.length;

		// Simulate bus event
		busHandlers['kernel:audit_logged']?.forEach((h) => h({}));
		await vi.advanceTimersByTimeAsync(10);

		expect(mockFetchAuditLogs.mock.calls.length).toBeGreaterThan(callCount);
	});

	it('displays error state on fetch failure', async () => {
		mockFetchAuditLogs.mockRejectedValueOnce(new Error('Network error'));

		render(AuditLogWindow);
		await vi.advanceTimersByTimeAsync(10);

		expect(screen.getByText('Network error')).toBeTruthy();
	});

	it('resource ID cell has title attribute for tooltip', async () => {
		render(AuditLogWindow);
		await vi.advanceTimersByTimeAsync(10);

		// Find the cell with the truncated resource ID
		const cells = document.querySelectorAll('td[title]');
		const idCell = Array.from(cells).find((c) => c.getAttribute('title') === 'abc-123-def-456-ghi-789');
		expect(idCell).toBeTruthy();
	});

	it('clicking a row with details expands detail view', async () => {
		render(AuditLogWindow);
		await vi.advanceTimersByTimeAsync(10);

		// Click the first row (which has details)
		const rows = document.querySelectorAll('tbody tr');
		expect(rows.length).toBeGreaterThan(0);
		await fireEvent.click(rows[0]);
		await vi.advanceTimersByTimeAsync(10);

		// Details row should now be visible with key-value content
		expect(screen.getByText('name:')).toBeTruthy();
		expect(screen.getByText('Test Project')).toBeTruthy();
	});

	it('pagination next/prev work', async () => {
		// Return enough entries to trigger pagination
		mockFetchAuditLogs.mockResolvedValue({ logs: mockLogs, total: 100 });

		render(AuditLogWindow);
		await vi.advanceTimersByTimeAsync(10);

		// Should show pagination
		const nextBtn = screen.getByText('Next');
		expect(nextBtn).toBeTruthy();

		await fireEvent.click(nextBtn);
		await vi.advanceTimersByTimeAsync(10);

		// Second call should have offset=50 (page 1)
		const nextCall = mockFetchAuditLogs.mock.calls[mockFetchAuditLogs.mock.calls.length - 1];
		expect(nextCall[2]).toBe(50); // offset

		// Previous should now be enabled
		const prevBtn = screen.getByText('Previous');
		await fireEvent.click(prevBtn);
		await vi.advanceTimersByTimeAsync(10);

		const prevCall = mockFetchAuditLogs.mock.calls[mockFetchAuditLogs.mock.calls.length - 1];
		expect(prevCall[2]).toBe(0); // back to offset 0
	});
});
