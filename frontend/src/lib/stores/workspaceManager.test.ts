import { describe, it, expect, vi, beforeEach } from 'vitest';

const {
	mockDeleteGitHubConfig,
	mockSaveGitHubConfig,
	mockFetchGitHubConfig,
	mockFetchGitHubStatus,
	mockFetchWorkspaceStatuses,
} = vi.hoisted(() => ({
	mockDeleteGitHubConfig: vi.fn(),
	mockSaveGitHubConfig: vi.fn(),
	mockFetchGitHubConfig: vi.fn(),
	mockFetchGitHubStatus: vi.fn(),
	mockFetchWorkspaceStatuses: vi.fn(),
}));

vi.mock('$lib/api/client', () => ({
	deleteGitHubConfig: mockDeleteGitHubConfig,
	disconnectGitHub: vi.fn(),
	fetchGitHubAuthorize: vi.fn(),
	fetchGitHubConfig: mockFetchGitHubConfig,
	fetchGitHubRepos: vi.fn().mockResolvedValue([]),
	fetchGitHubStatus: mockFetchGitHubStatus,
	fetchWorkspaceStatuses: mockFetchWorkspaceStatuses,
	linkRepo: vi.fn(),
	saveGitHubConfig: mockSaveGitHubConfig,
	syncWorkspace: vi.fn(),
	unlinkWorkspace: vi.fn(),
}));

vi.mock('$lib/services/systemBus.svelte', () => ({
	systemBus: { emit: vi.fn(), on: vi.fn(() => () => {}), reset: vi.fn() },
}));

// Stub browser storage APIs for Node test environment
const storageStub = (() => {
	let store: Record<string, string> = {};
	return {
		getItem: (key: string) => store[key] ?? null,
		setItem: (key: string, value: string) => { store[key] = value; },
		removeItem: (key: string) => { delete store[key]; },
		clear: () => { store = {}; },
		get length() { return Object.keys(store).length; },
		key: (i: number) => Object.keys(store)[i] ?? null,
	} as Storage;
})();

if (typeof globalThis.sessionStorage === 'undefined') {
	Object.defineProperty(globalThis, 'sessionStorage', { value: storageStub, writable: true });
}
if (typeof globalThis.localStorage === 'undefined') {
	Object.defineProperty(globalThis, 'localStorage', { value: storageStub, writable: true });
}

import { workspaceManager } from './workspaceManager.svelte';

describe('WorkspaceManagerState', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		// Reset state
		workspaceManager.githubConfigured = false;
		workspaceManager.githubConnected = false;
		workspaceManager.githubError = null;
		workspaceManager.configuring = false;
		workspaceManager.deletingConfig = false;
	});

	describe('deleteConfig', () => {
		it('sets githubConfigured to false on success', async () => {
			workspaceManager.githubConfigured = true;
			mockDeleteGitHubConfig.mockResolvedValue({ status: 'deleted' });

			await workspaceManager.deleteConfig();

			expect(workspaceManager.githubConfigured).toBe(false);
			expect(mockDeleteGitHubConfig).toHaveBeenCalledOnce();
		});

		it('sets deletingConfig true during call and false after', async () => {
			const states: boolean[] = [];
			mockDeleteGitHubConfig.mockImplementation(async () => {
				states.push(workspaceManager.deletingConfig);
				return { status: 'deleted' };
			});

			await workspaceManager.deleteConfig();

			expect(states[0]).toBe(true);
			expect(workspaceManager.deletingConfig).toBe(false);
		});

		it('clears githubError before calling API', async () => {
			workspaceManager.githubError = 'previous error';
			mockDeleteGitHubConfig.mockResolvedValue({ status: 'deleted' });

			await workspaceManager.deleteConfig();

			expect(workspaceManager.githubError).toBeNull();
		});

		it('sets githubError on API failure', async () => {
			workspaceManager.githubConfigured = true;
			mockDeleteGitHubConfig.mockRejectedValue(new Error('Network error'));

			await expect(workspaceManager.deleteConfig()).rejects.toThrow('Network error');

			expect(workspaceManager.githubError).toBe('Network error');
		});

		it('re-throws on failure so callers can catch', async () => {
			mockDeleteGitHubConfig.mockRejectedValue(new Error('fail'));

			await expect(workspaceManager.deleteConfig()).rejects.toThrow('fail');
		});

		it('does not change githubConfigured on failure', async () => {
			workspaceManager.githubConfigured = true;
			mockDeleteGitHubConfig.mockRejectedValue(new Error('fail'));

			try { await workspaceManager.deleteConfig(); } catch {}

			expect(workspaceManager.githubConfigured).toBe(true);
		});
	});

	describe('saveConfig', () => {
		it('sets githubConfigured to true on success', async () => {
			mockSaveGitHubConfig.mockResolvedValue({ configured: true });

			await workspaceManager.saveConfig('id', 'secret');

			expect(workspaceManager.githubConfigured).toBe(true);
			expect(mockSaveGitHubConfig).toHaveBeenCalledWith('id', 'secret');
		});

		it('sets configuring flag during call', async () => {
			const states: boolean[] = [];
			mockSaveGitHubConfig.mockImplementation(async () => {
				states.push(workspaceManager.configuring);
				return { configured: true };
			});

			await workspaceManager.saveConfig('id', 'secret');

			expect(states[0]).toBe(true);
			expect(workspaceManager.configuring).toBe(false);
		});

		it('sets githubError on failure', async () => {
			mockSaveGitHubConfig.mockRejectedValue(new Error('Save failed'));

			await expect(workspaceManager.saveConfig('id', 'secret')).rejects.toThrow();

			expect(workspaceManager.githubError).toBe('Save failed');
		});
	});

	describe('initialize', () => {
		it('calls checkGitHubStatus, loadWorkspaces, and checkGitHubConfig', async () => {
			mockFetchGitHubStatus.mockResolvedValue({ connected: false });
			mockFetchWorkspaceStatuses.mockResolvedValue([]);
			mockFetchGitHubConfig.mockResolvedValue({ configured: false, client_id_hint: '', source: null });

			await workspaceManager.initialize();

			expect(mockFetchGitHubStatus).toHaveBeenCalledOnce();
			expect(mockFetchWorkspaceStatuses).toHaveBeenCalledOnce();
			expect(mockFetchGitHubConfig).toHaveBeenCalledOnce();
		});

		it('sets githubConfigured from fetchGitHubConfig response', async () => {
			mockFetchGitHubStatus.mockResolvedValue({ connected: false });
			mockFetchWorkspaceStatuses.mockResolvedValue([]);
			mockFetchGitHubConfig.mockResolvedValue({ configured: true, client_id_hint: 'Iv1.****1234', source: 'database' });

			await workspaceManager.initialize();

			expect(workspaceManager.githubConfigured).toBe(true);
		});

		it('handles fetchGitHubConfig failure gracefully', async () => {
			mockFetchGitHubStatus.mockResolvedValue({ connected: false });
			mockFetchWorkspaceStatuses.mockResolvedValue([]);
			mockFetchGitHubConfig.mockRejectedValue(new Error('Network error'));

			// Should not throw
			await workspaceManager.initialize();

			// githubConfigured stays at its default (false)
			expect(workspaceManager.githubConfigured).toBe(false);
		});
	});

	describe('updateFromHealth', () => {
		it('syncs githubConfigured from health data', () => {
			workspaceManager.updateFromHealth({ github_configured: true });
			expect(workspaceManager.githubConfigured).toBe(true);

			workspaceManager.updateFromHealth({ github_configured: false });
			expect(workspaceManager.githubConfigured).toBe(false);
		});

		it('syncs githubConnected from health data', () => {
			workspaceManager.updateFromHealth({ github_connected: true });
			expect(workspaceManager.githubConnected).toBe(true);

			workspaceManager.updateFromHealth({ github_connected: false });
			expect(workspaceManager.githubConnected).toBe(false);
		});

		it('ignores undefined fields', () => {
			workspaceManager.githubConfigured = true;
			workspaceManager.githubConnected = true;

			workspaceManager.updateFromHealth({});

			expect(workspaceManager.githubConfigured).toBe(true);
			expect(workspaceManager.githubConnected).toBe(true);
		});
	});
});
