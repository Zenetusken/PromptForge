/**
 * Workspace Manager Store — manages GitHub connections and workspace links.
 *
 * Provides reactive state for the Workspace Hub window (GitHub tab, Workspaces tab,
 * Context Inspector). Consumes health endpoint workspace data from the provider store.
 */

import {
	type GitHubRepo,
	type GitHubStatus,
	type WorkspaceLink,
	type WorkspaceStatus,
	deleteGitHubConfig,
	disconnectGitHub,
	fetchGitHubAuthorize,
	fetchGitHubConfig,
	fetchGitHubRepos,
	fetchGitHubStatus,
	fetchWorkspaceStatuses,
	linkRepo,
	saveGitHubConfig,
	syncWorkspace,
	unlinkWorkspace,
} from '$lib/api/client';
import { systemBus } from '$lib/services/systemBus.svelte';

class WorkspaceManagerState {
	// GitHub OAuth config
	githubConfigured = $state(false);
	configuring = $state(false);
	deletingConfig = $state(false);

	// GitHub connection
	githubConnected = $state(false);
	githubUser: GitHubStatus | null = $state(null);
	repos: GitHubRepo[] = $state([]);
	reposLoading = $state(false);
	reposSearch = $state('');

	// Workspace links
	workspaces: WorkspaceStatus[] = $state([]);
	loading = $state(false);
	selectedId: string | null = $state(null);

	// Error states
	githubError: string | null = $state(null);
	workspacesError: string | null = $state(null);

	// Derived
	connectedCount = $derived(
		this.workspaces.filter((w) => w.sync_status === 'synced' && !w.stale).length,
	);
	staleCount = $derived(this.workspaces.filter((w) => w.stale).length);
	errorCount = $derived(this.workspaces.filter((w) => w.sync_status === 'error').length);
	selectedWorkspace = $derived(
		this.workspaces.find((w) => w.project_id === this.selectedId) ?? null,
	);

	filteredRepos = $derived.by(() => {
		if (!this.reposSearch) return this.repos;
		const q = this.reposSearch.toLowerCase();
		return this.repos.filter(
			(r) =>
				r.full_name.toLowerCase().includes(q) ||
				r.description?.toLowerCase().includes(q),
		);
	});

	// --- Actions ---

	async checkGitHubStatus() {
		try {
			this.githubError = null;
			const status = await fetchGitHubStatus();
			this.githubConnected = status.connected;
			this.githubUser = status.connected ? status : null;
		} catch (e) {
			this.githubError = e instanceof Error ? e.message : 'Failed to check GitHub status';
		}
	}

	async connectGitHub() {
		try {
			this.githubError = null;
			const auth = await fetchGitHubAuthorize();
			if (auth.url) {
				window.open(auth.url, '_self');
			} else {
				this.githubError = 'GitHub OAuth returned no authorization URL';
			}
		} catch (e) {
			this.githubError = e instanceof Error ? e.message : 'Failed to start GitHub OAuth';
		}
	}

	async disconnectGitHub() {
		try {
			this.githubError = null;
			await disconnectGitHub();
			this.githubConnected = false;
			this.githubUser = null;
			this.repos = [];
			systemBus.emit('workspace:disconnected', 'workspaceManager');
		} catch (e) {
			this.githubError = e instanceof Error ? e.message : 'Failed to disconnect';
		}
	}

	async loadRepos(search?: string) {
		this.reposLoading = true;
		this.githubError = null;
		try {
			this.repos = await fetchGitHubRepos();
			if (search !== undefined) this.reposSearch = search;
		} catch (e) {
			this.githubError = e instanceof Error ? e.message : 'Failed to load repos';
		} finally {
			this.reposLoading = false;
		}
	}

	async loadWorkspaces() {
		this.loading = true;
		this.workspacesError = null;
		try {
			this.workspaces = await fetchWorkspaceStatuses();
		} catch (e) {
			this.workspacesError = e instanceof Error ? e.message : 'Failed to load workspaces';
		} finally {
			this.loading = false;
		}
	}

	async linkRepo(projectId: string, repoFullName: string): Promise<WorkspaceLink | null> {
		try {
			const link = await linkRepo(projectId, repoFullName);
			if (link) {
				await this.loadWorkspaces();
				systemBus.emit('workspace:synced', 'workspaceManager', {
					project_id: projectId,
					repo: repoFullName,
				});
			}
			return link;
		} catch (e) {
			const error = e instanceof Error ? e.message : 'Link failed';
			systemBus.emit('workspace:error', 'workspaceManager', {
				project_id: projectId,
				error,
			});
			throw e;
		}
	}

	async unlinkWorkspace(linkId: string) {
		try {
			this.workspacesError = null;
			await unlinkWorkspace(linkId);
			await this.loadWorkspaces();
		} catch (e) {
			this.workspacesError = e instanceof Error ? e.message : 'Unlink failed';
		}
	}

	async syncWorkspace(linkId: string) {
		try {
			const result = await syncWorkspace(linkId);
			if (result) {
				await this.loadWorkspaces();
				systemBus.emit('workspace:synced', 'workspaceManager', {
					link_id: linkId,
				});
			}
			return result;
		} catch (e) {
			const error = e instanceof Error ? e.message : 'Sync failed';
			this.workspacesError = error;
			systemBus.emit('workspace:error', 'workspaceManager', {
				link_id: linkId,
				error,
			});
			throw e;
		}
	}

	async saveConfig(clientId: string, clientSecret: string) {
		this.configuring = true;
		this.githubError = null;
		try {
			await saveGitHubConfig(clientId, clientSecret);
			this.githubConfigured = true;
		} catch (e) {
			this.githubError = e instanceof Error ? e.message : 'Failed to save config';
			throw e;
		} finally {
			this.configuring = false;
		}
	}

	async deleteConfig() {
		this.deletingConfig = true;
		this.githubError = null;
		try {
			await deleteGitHubConfig();
			this.githubConfigured = false;
		} catch (e) {
			this.githubError = e instanceof Error ? e.message : 'Failed to remove credentials';
			throw e;
		} finally {
			this.deletingConfig = false;
		}
	}

	/** Called on page load and when OAuth callback completes. */
	async initialize() {
		await Promise.allSettled([
			this.checkGitHubStatus(),
			this.loadWorkspaces(),
			this.checkGitHubConfig(),
		]);
	}

	/** Fetch GitHub OAuth config status (configured vs not). */
	private async checkGitHubConfig() {
		try {
			const cfg = await fetchGitHubConfig();
			this.githubConfigured = cfg.configured;
		} catch {
			// Non-critical — health polling will sync this later
		}
	}

	/** Update config status from health polling data. */
	updateFromHealth(workspace: { github_configured?: boolean; github_connected?: boolean }) {
		if (workspace.github_configured !== undefined) {
			this.githubConfigured = workspace.github_configured;
		}
		if (workspace.github_connected !== undefined) {
			this.githubConnected = workspace.github_connected;
		}
	}
}

export const workspaceManager = new WorkspaceManagerState();
