<script lang="ts">
	import { workspaceManager } from '$lib/stores/workspaceManager.svelte';
	import { providerState } from '$lib/stores/provider.svelte';
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import { desktopStore } from '$lib/stores/desktopStore.svelte';
	import { systemBus } from '$lib/services/systemBus.svelte';
	import type { ProjectSummary } from '$lib/api/client';
	import { fetchProjects } from '$lib/api/client';
	import Icon from './Icon.svelte';
	import { WindowTabStrip, StatusDot, InlineProgress } from './ui';
	import { onMount } from 'svelte';

	let activeTab: 'github' | 'workspaces' | 'inspector' = $state('github');

	const tabs = [
		{ id: 'github' as const, label: 'GitHub', icon: 'github' as const },
		{ id: 'workspaces' as const, label: 'Workspaces', icon: 'git-branch' as const },
		{ id: 'inspector' as const, label: 'Context Inspector', icon: 'search' as const },
	];

	// Project list for linking
	let projects: ProjectSummary[] = $state([]);
	let projectsLoading = $state(false);
	let linkProjectId = $state('');
	let linkingRepo = $state('');
	let linkError = $state('');
	let syncingId = $state<string | null>(null);
	let connecting = $state(false);
	let disconnecting = $state(false);

	// OAuth setup form state
	let configClientId = $state('');
	let configClientSecret = $state('');
	let configError = $state('');
	let configSaving = $state(false);
	let showSetupGuide = $state(false);

	const contextFields = [
		{ key: 'language', label: 'Language' },
		{ key: 'framework', label: 'Framework' },
		{ key: 'description', label: 'Description' },
		{ key: 'conventions', label: 'Conventions' },
		{ key: 'patterns', label: 'Patterns' },
		{ key: 'test_framework', label: 'Test Framework' },
		{ key: 'test_patterns', label: 'Test Patterns' },
	];

	let githubConnected = $derived(workspaceManager.githubConnected);
	let githubUser = $derived(workspaceManager.githubUser);
	let repos = $derived(workspaceManager.filteredRepos);
	let reposLoading = $derived(workspaceManager.reposLoading);
	let workspaces = $derived(workspaceManager.workspaces);
	let loading = $derived(workspaceManager.loading);
	let selectedWorkspace = $derived(workspaceManager.selectedWorkspace);
	let githubError = $derived(workspaceManager.githubError);
	let workspacesError = $derived(workspaceManager.workspacesError);

	// Workspace health from provider polling
	let wsHealth = $derived(providerState.health?.workspace);

	// Three-state: not configured → configured but not connected → connected
	let githubConfigured = $derived(
		wsHealth?.github_configured ?? workspaceManager.githubConfigured,
	);

	function formatRelative(iso: string | null): string {
		if (!iso) return 'Never';
		const ms = Date.now() - new Date(iso).getTime();
		if (ms < 60_000) return 'Just now';
		if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ago`;
		if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h ago`;
		return `${Math.floor(ms / 86_400_000)}d ago`;
	}

	function statusDotColor(ws: { sync_status: string; stale: boolean }): 'green' | 'yellow' | 'red' | 'cyan' | 'orange' {
		if (ws.sync_status === 'error') return 'red';
		if (ws.sync_status === 'syncing' || ws.sync_status === 'pending') return 'cyan';
		if (ws.stale) return 'yellow';
		return 'green';
	}

	function statusLabel(ws: { sync_status: string; stale: boolean }): string {
		if (ws.sync_status === 'error') return 'Error';
		if (ws.sync_status === 'syncing') return 'Syncing...';
		if (ws.sync_status === 'pending') return 'Pending';
		if (ws.stale) return 'Stale';
		return 'Synced';
	}

	async function handleSaveConfig() {
		configError = '';
		const id = configClientId.trim();
		const secret = configClientSecret.trim();
		if (!id) { configError = 'Client ID is required'; return; }
		if (!secret) { configError = 'Client secret is required'; return; }
		if (!/^[A-Za-z0-9._-]+$/.test(id)) { configError = 'Client ID contains invalid characters'; return; }

		configSaving = true;
		try {
			await workspaceManager.saveConfig(id, secret);
			configClientId = '';
			configClientSecret = '';
		} catch (e) {
			configError = e instanceof Error ? e.message : 'Save failed';
		} finally {
			configSaving = false;
		}
	}

	async function handleConnect() {
		connecting = true;
		try {
			await workspaceManager.connectGitHub();
		} finally {
			connecting = false;
		}
	}

	async function handleDisconnect() {
		disconnecting = true;
		try {
			await workspaceManager.disconnectGitHub();
		} finally {
			disconnecting = false;
		}
	}

	function handleDeleteConfig() {
		desktopStore.confirmDialog = {
			open: true,
			title: 'Remove GitHub Credentials',
			message: 'This will delete the stored OAuth app credentials. You can reconfigure them at any time.',
			confirmLabel: 'Remove',
			onConfirm: async () => {
				desktopStore.confirmDialog.open = false;
				try {
					await workspaceManager.deleteConfig();
				} catch {
					// Error already set on workspaceManager.githubError
				}
			},
		};
	}

	function handleReconfigure() {
		desktopStore.confirmDialog = {
			open: true,
			title: 'Reconfigure GitHub Credentials',
			message: 'This will disconnect your GitHub account and remove the stored OAuth credentials. You can set up new credentials afterward.',
			confirmLabel: 'Reconfigure',
			onConfirm: async () => {
				desktopStore.confirmDialog.open = false;
				disconnecting = true;
				try {
					await workspaceManager.disconnectGitHub();
					await workspaceManager.deleteConfig();
				} catch {
					// Errors set on workspaceManager.githubError
				} finally {
					disconnecting = false;
				}
			},
		};
	}

	async function handleLoadRepos() {
		await workspaceManager.loadRepos();
	}

	async function handleLink(repoFullName: string) {
		if (!linkProjectId) {
			linkError = 'Select a project first';
			return;
		}
		linkError = '';
		linkingRepo = repoFullName;
		try {
			await workspaceManager.linkRepo(linkProjectId, repoFullName);
			linkingRepo = '';
			linkProjectId = '';
		} catch (e) {
			linkError = e instanceof Error ? e.message : 'Link failed';
			linkingRepo = '';
		}
	}

	async function handleSync(linkId: string) {
		syncingId = linkId;
		try {
			await workspaceManager.syncWorkspace(linkId);
		} catch {
			// Error already captured in workspaceManager.workspacesError
		} finally {
			syncingId = null;
		}
	}

	let unlinkingId = $state<string | null>(null);

	async function handleUnlink(linkId: string) {
		unlinkingId = linkId;
		try {
			await workspaceManager.unlinkWorkspace(linkId);
		} finally {
			unlinkingId = null;
		}
	}

	// Load data on mount
	onMount(() => {
		windowManager.setBreadcrumbs('workspace-manager', [
			{
				label: 'Desktop',
				icon: 'monitor',
				action: () => windowManager.closeWindow('workspace-manager'),
			},
			{ label: 'Workspace Hub' },
		]);

		// Fire-and-forget async init
		(async () => {
			projectsLoading = true;
			await workspaceManager.initialize();
			try {
				const res = await fetchProjects({ status: 'active', per_page: 100 });
				if (res) projects = res.items;
			} finally {
				projectsLoading = false;
			}
			if (workspaceManager.githubConnected) {
				await workspaceManager.loadRepos();
			}
		})();

		// Refresh on workspace events
		return systemBus.on('workspace:synced', () => {
			workspaceManager.loadWorkspaces();
		});
	});
</script>

<div class="flex h-full flex-col bg-bg-primary text-text-primary font-mono">
	<WindowTabStrip {tabs} {activeTab} onTabChange={(id) => (activeTab = id as typeof activeTab)} />

	<!-- Content -->
	<div class="flex-1 overflow-y-auto p-3 space-y-3">
		{#if activeTab === 'github'}
			<!-- GitHub Connection Tab -->
			<div class="space-y-3">
				<h3 class="section-heading">
					GitHub Connection
				</h3>

				{#if githubError}
					<div class="text-[10px] text-neon-red px-2 py-1.5 bg-neon-red/5 border border-neon-red/10 flex items-center gap-2">
						<Icon name="alert-triangle" size={10} class="shrink-0" />
						<span class="flex-1">{githubError}</span>
						<button
							class="text-neon-red/60 hover:text-neon-red text-[10px] shrink-0"
							onclick={() => (workspaceManager.githubError = null)}
						>dismiss</button>
					</div>
				{/if}

				{#if githubConnected && githubUser}
					<!-- Connected state -->
					<div
						class="flex items-center gap-3 p-3 border border-neon-green/20 bg-neon-green/5"
					>
						{#if githubUser.avatar_url}
							<img
								src={githubUser.avatar_url}
								alt={githubUser.username}
								class="w-8 h-8 rounded-full border border-neon-green/30"
							/>
						{:else}
							<div
								class="w-8 h-8 rounded-full border border-neon-green/30 flex items-center justify-center bg-bg-card"
							>
								<Icon name="github" size={14} />
							</div>
						{/if}
						<div class="flex-1 min-w-0">
							<div class="text-xs text-neon-green font-medium truncate">
								{githubUser.username}
							</div>
							<div class="text-[10px] text-text-dim">
								Connected · Scopes: {githubUser.scopes || 'repo'}
							</div>
						</div>
						<div class="flex items-center gap-2 shrink-0">
							<button
								class="text-[10px] text-neon-red/60 hover:text-neon-red px-2 py-1 border border-neon-red/10 hover:border-neon-red/30 transition-colors disabled:opacity-40"
								onclick={handleDisconnect}
								disabled={disconnecting}
							>
								{disconnecting ? 'Disconnecting...' : 'Disconnect'}
							</button>
							<button
								class="text-[10px] text-text-dim hover:text-text-secondary transition-colors disabled:opacity-40"
								onclick={handleReconfigure}
								disabled={disconnecting || workspaceManager.deletingConfig}
							>
								Reconfigure
							</button>
						</div>
					</div>

					<!-- Repos list -->
					<div class="space-y-2">
						<div class="flex items-center gap-2">
							<h4 class="text-xs text-text-secondary flex-1">Repositories</h4>
							<button
								class="text-[10px] text-neon-cyan hover:text-neon-cyan/80 transition-colors"
								onclick={handleLoadRepos}
								disabled={reposLoading}
							>
								{reposLoading ? 'Loading...' : 'Refresh'}
							</button>
						</div>

						<input
							id="workspace-repo-search"
							type="text"
							placeholder="Search repos..."
							class="w-full bg-bg-input border border-neon-cyan/10 text-xs text-text-primary px-2 py-1.5 outline-none focus:border-neon-cyan/30"
							bind:value={workspaceManager.reposSearch}
						/>

						{#if linkError}
							<div class="text-[10px] text-neon-red px-2 py-1 bg-neon-red/5 border border-neon-red/10">
								{linkError}
							</div>
						{/if}

						<!-- Project selector for linking -->
						<select
							id="workspace-link-project"
							class="w-full bg-bg-input border border-neon-cyan/10 text-xs text-text-primary px-2 py-1.5 outline-none focus:border-neon-cyan/30"
							bind:value={linkProjectId}
							disabled={projectsLoading}
						>
							<option value="">{projectsLoading ? 'Loading projects...' : 'Select project to link...'}</option>
							{#each projects as p (p.id)}
								<option value={p.id}>{p.name}</option>
							{/each}
						</select>

						<div class="space-y-1 max-h-[300px] overflow-y-auto">
							{#each repos as repo (repo.full_name)}
								{@const linked = workspaces.some((w) => w.repo === repo.full_name)}
								<div
									class="flex items-center gap-2 p-2 border border-neon-cyan/5 hover:border-neon-cyan/20 transition-colors
										{linked ? 'bg-neon-green/5 border-neon-green/10' : 'bg-bg-card'}"
								>
									<div class="flex-1 min-w-0">
										<div class="text-xs truncate">
											<span class="text-text-primary">{repo.name}</span>
											{#if repo.private}
												<span class="text-[9px] text-neon-yellow/60 ml-1">private</span>
											{/if}
										</div>
										<div class="text-[10px] text-text-dim truncate">
											{repo.description || 'No description'}
										</div>
										<div class="flex items-center gap-2 mt-0.5">
											{#if repo.language}
												<span class="text-[9px] text-neon-purple">{repo.language}</span>
											{/if}
											<span class="text-[9px] text-text-dim">{repo.default_branch}</span>
										</div>
									</div>
									{#if linked}
										<span class="text-[9px] text-neon-green px-1.5 py-0.5 border border-neon-green/20">
											Linked
										</span>
									{:else}
										<button
											class="text-[10px] text-neon-cyan hover:text-neon-cyan/80 px-2 py-1 border border-neon-cyan/10 hover:border-neon-cyan/30 transition-colors disabled:opacity-30"
											onclick={() => handleLink(repo.full_name)}
											disabled={linkingRepo === repo.full_name || !linkProjectId}
										>
											{linkingRepo === repo.full_name ? 'Linking...' : 'Link'}
										</button>
									{/if}
								</div>
							{/each}
							{#if repos.length === 0 && !reposLoading}
								<div class="text-xs text-text-dim text-center py-4">
									{workspaceManager.reposSearch ? 'No matching repos' : 'No repos loaded'}
								</div>
							{/if}
						</div>
					</div>
				{:else if githubConfigured}
					<!-- State 2: Configured but not connected -->
					<div
						class="flex flex-col items-center gap-3 py-8 border border-neon-cyan/10 bg-bg-card"
					>
						<Icon name="github" size={24} class="text-text-dim" />
						<p class="text-xs text-text-secondary text-center max-w-[240px]">
							GitHub OAuth is configured. Connect your account to start
							extracting codebase context from repositories.
						</p>
						<button
							class="flex items-center gap-1.5 text-xs text-neon-cyan px-3 py-1.5 border border-neon-cyan/20 hover:border-neon-cyan/40 hover:bg-neon-cyan/5 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
							onclick={handleConnect}
							disabled={connecting}
						>
							<Icon name="github" size={12} />
							{connecting ? 'Connecting...' : 'Connect GitHub'}
						</button>
						<button
							class="text-[10px] text-neon-red/60 hover:text-neon-red px-2 py-1 border border-neon-red/10 hover:border-neon-red/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
							onclick={handleDeleteConfig}
							disabled={workspaceManager.deletingConfig}
						>
							{workspaceManager.deletingConfig ? 'Removing...' : 'Remove credentials'}
						</button>
					</div>
				{:else}
					<!-- State 1: Not configured — Setup form -->
					<div class="space-y-3">
						<div class="flex flex-col items-center gap-2 pt-2">
							<Icon name="github" size={20} class="text-text-dim" />
							<h4 class="text-xs font-medium text-text-primary">GitHub OAuth Setup</h4>
							<p class="text-[10px] text-text-secondary text-center max-w-[280px]">
								Configure your GitHub OAuth App to enable automatic codebase
								context extraction from your repositories.
							</p>
						</div>

						<!-- Collapsible setup walkthrough -->
						<button
							class="w-full text-left text-[10px] text-neon-cyan/80 hover:text-neon-cyan flex items-center gap-1 transition-colors"
							onclick={() => (showSetupGuide = !showSetupGuide)}
						>
							<Icon name={showSetupGuide ? 'chevron-down' : 'chevron-right'} size={10} />
							How to get credentials
						</button>

						{#if showSetupGuide}
							<div class="text-[10px] text-text-secondary space-y-2 px-2 py-2 border border-neon-cyan/5 bg-bg-card">
								<div class="flex items-start gap-2">
									<span class="text-neon-cyan font-medium shrink-0">1.</span>
									<div>
										Open
										<a
											href="https://github.com/settings/developers"
											target="_blank"
											rel="noopener noreferrer"
											class="text-neon-cyan hover:underline"
										>GitHub Developer Settings</a>
										and click <span class="text-text-primary">"OAuth Apps"</span>
									</div>
								</div>
								<div class="flex items-start gap-2">
									<span class="text-neon-cyan font-medium shrink-0">2.</span>
									<div>
										Click <span class="text-text-primary">"New OAuth App"</span>
										and set <span class="text-text-primary">Application name</span> to anything
										(e.g. "PromptForge")
									</div>
								</div>
								<div class="flex items-start gap-2">
									<span class="text-neon-cyan font-medium shrink-0">3.</span>
									<div>
										Set <span class="text-text-primary">Homepage URL</span> to
										<code class="text-[9px] text-neon-cyan">http://localhost:5199</code>
									</div>
								</div>
								<div class="flex items-start gap-2">
									<span class="text-neon-cyan font-medium shrink-0">4.</span>
									<div>
										Set <span class="text-text-primary">Authorization callback URL</span> to:
										<code class="block text-[9px] text-neon-cyan bg-bg-input px-2 py-1 mt-0.5 border border-neon-cyan/10 select-all">http://localhost:8000/api/github/callback</code>
									</div>
								</div>
								<div class="flex items-start gap-2">
									<span class="text-neon-cyan font-medium shrink-0">5.</span>
									<div>
										Click <span class="text-text-primary">"Register application"</span>, then copy
										the <span class="text-text-primary">Client ID</span> and generate a
										<span class="text-text-primary">Client Secret</span>
									</div>
								</div>
								<a
									href="https://github.com/settings/applications/new"
									target="_blank"
									rel="noopener noreferrer"
									class="flex items-center justify-center gap-1.5 text-[10px] text-neon-cyan px-2 py-1 border border-neon-cyan/20 hover:border-neon-cyan/30 hover:bg-neon-cyan/5 transition-colors mt-1"
								>
									<Icon name="github" size={10} />
									Create OAuth App on GitHub
								</a>
							</div>
						{/if}

						{#if configError}
							<div class="text-[10px] text-neon-red px-2 py-1.5 bg-neon-red/5 border border-neon-red/10 flex items-center gap-2">
								<Icon name="alert-triangle" size={10} class="shrink-0" />
								<span class="flex-1">{configError}</span>
								<button
									class="text-neon-red/60 hover:text-neon-red text-[10px] shrink-0"
									onclick={() => (configError = '')}
								>dismiss</button>
							</div>
						{/if}

						<!-- Input fields -->
						<div class="space-y-2">
							<div>
								<label for="config-client-id" class="text-[10px] text-text-secondary block mb-0.5">Client ID</label>
								<input
									id="config-client-id"
									type="text"
									placeholder="Iv1.abc123..."
									class="w-full bg-bg-input border border-neon-cyan/10 text-xs text-text-primary px-2 py-1.5 outline-none focus:border-neon-cyan/30"
									bind:value={configClientId}
								onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); document.getElementById('config-client-secret')?.focus(); } }}
								/>
							</div>
							<div>
								<label for="config-client-secret" class="text-[10px] text-text-secondary block mb-0.5">Client Secret</label>
								<input
									id="config-client-secret"
									type="password"
									placeholder="Enter client secret..."
									class="w-full bg-bg-input border border-neon-cyan/10 text-xs text-text-primary px-2 py-1.5 outline-none focus:border-neon-cyan/30"
									bind:value={configClientSecret}
									onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleSaveConfig(); } }}
								/>
							</div>
						</div>

						<!-- Security note -->
						<div class="flex items-start gap-1.5 text-[9px] text-text-dim px-2 py-1.5 border border-neon-cyan/5 bg-bg-card">
							<Icon name="lock" size={10} class="shrink-0 mt-0.5 text-neon-green/60" />
							<div>
								<p>Credentials are encrypted at rest using Fernet (AES-128-CBC + HMAC).</p>
								<p class="mt-0.5">Secrets are never logged or exposed in API responses.</p>
							</div>
						</div>

						<button
							class="w-full flex items-center justify-center gap-1.5 text-xs text-neon-cyan px-3 py-1.5 border border-neon-cyan/20 hover:border-neon-cyan/40 hover:bg-neon-cyan/5 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
							onclick={handleSaveConfig}
							disabled={configSaving || !configClientId.trim() || !configClientSecret.trim()}
						>
							{configSaving ? 'Saving...' : 'Save Configuration'}
						</button>

						<!-- Env var fallback hint -->
						<div class="pt-2 border-t border-neon-cyan/5">
							<p class="text-[9px] text-text-dim text-center">
								Or set via environment variables:
							</p>
							<code class="block text-[9px] text-text-dim text-center mt-1">
								GITHUB_CLIENT_ID=... GITHUB_CLIENT_SECRET=...
							</code>
						</div>
					</div>
				{/if}
			</div>

		{:else if activeTab === 'workspaces'}
			<!-- Workspaces Tab -->
			<div class="space-y-3">
				<div class="flex items-center gap-2">
					<h3 class="section-heading flex-1">
						Workspace Links
					</h3>
					<div class="flex items-center gap-2 text-[10px] text-text-dim">
						<span class="flex items-center gap-1">
							<StatusDot color="green" />
							{workspaceManager.connectedCount}
						</span>
						{#if workspaceManager.staleCount > 0}
							<span class="flex items-center gap-1">
								<StatusDot color="yellow" />
								{workspaceManager.staleCount}
							</span>
						{/if}
						{#if workspaceManager.errorCount > 0}
							<span class="flex items-center gap-1">
								<StatusDot color="red" />
								{workspaceManager.errorCount}
							</span>
						{/if}
					</div>
				</div>

				{#if workspacesError}
					<div class="text-[10px] text-neon-red px-2 py-1.5 bg-neon-red/5 border border-neon-red/10 flex items-center gap-2">
						<Icon name="alert-triangle" size={10} class="shrink-0" />
						<span class="flex-1">{workspacesError}</span>
						<button
							class="text-neon-cyan/60 hover:text-neon-cyan text-[10px] shrink-0"
							onclick={() => workspaceManager.loadWorkspaces()}
						>retry</button>
					</div>
				{/if}

				{#if loading}
					<div class="text-xs text-text-dim text-center py-6">Loading workspaces...</div>
				{:else if workspaces.length === 0 && !workspacesError}
					<div class="text-xs text-text-dim text-center py-6 border border-neon-cyan/5 bg-bg-card">
						No workspace links yet. Link a repo from the GitHub tab.
					</div>
				{:else}
					<div class="space-y-1">
						{#each workspaces as ws (ws.id)}
							<div
								role="button"
								tabindex="0"
								class="w-full flex items-center gap-2 p-2 text-left border transition-colors cursor-pointer
									{workspaceManager.selectedId === ws.project_id
										? 'border-neon-cyan/30 bg-neon-cyan/5'
										: 'border-neon-cyan/5 bg-bg-card hover:border-neon-cyan/20'}"
								onclick={() => (workspaceManager.selectedId = ws.project_id)}
								onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); workspaceManager.selectedId = ws.project_id; } }}
							>
								<StatusDot color={statusDotColor(ws)} />
								<div class="flex-1 min-w-0">
									<div class="text-xs text-text-primary truncate">{ws.project}</div>
									<div class="text-[10px] text-text-dim truncate">{ws.repo}</div>
								</div>
								<div class="text-right shrink-0">
									<div class="text-[10px] {ws.sync_status === 'error' ? 'text-neon-red' : ws.stale ? 'text-neon-yellow' : 'text-text-dim'}">
										{statusLabel(ws)}
									</div>
									<div class="text-[9px] text-text-dim">{formatRelative(ws.synced_at)}</div>
								</div>
								<div class="flex items-center gap-1 shrink-0">
									<button
										class="text-[10px] text-neon-cyan/60 hover:text-neon-cyan p-0.5 transition-colors disabled:opacity-30"
										title="Sync now"
										onclick={(e) => { e.stopPropagation(); handleSync(ws.id); }}
										disabled={syncingId === ws.id}
									>
										<Icon name="refresh" size={10} class={syncingId === ws.id ? 'animate-spin' : ''} />
									</button>
									<button
										class="text-[10px] text-neon-red/40 hover:text-neon-red p-0.5 transition-colors disabled:opacity-30"
										title="Unlink"
										onclick={(e) => { e.stopPropagation(); handleUnlink(ws.id); }}
										disabled={unlinkingId === ws.id}
									>
										<Icon name={unlinkingId === ws.id ? 'refresh' : 'x'} size={10} class={unlinkingId === ws.id ? 'animate-spin' : ''} />
									</button>
								</div>
							</div>
						{/each}
					</div>
				{/if}
			</div>

		{:else if activeTab === 'inspector'}
			<!-- Context Inspector Tab -->
			<div class="space-y-3">
				<h3 class="section-heading">
					Context Inspector
				</h3>

				{#if !selectedWorkspace}
					<div class="text-xs text-text-dim text-center py-6 border border-neon-cyan/5 bg-bg-card">
						Select a workspace from the Workspaces tab to inspect its context.
					</div>
				{:else}
					<div class="space-y-2">
						<div class="flex items-center justify-between">
							<span class="text-xs text-text-primary">{selectedWorkspace.project}</span>
							<span class="text-[10px] text-text-dim">{selectedWorkspace.repo}</span>
						</div>

						{#if selectedWorkspace.sync_status === 'error'}
							<div class="text-[10px] text-neon-red px-2 py-1.5 bg-neon-red/5 border border-neon-red/10 flex items-center gap-2">
								<Icon name="alert-triangle" size={10} class="shrink-0" />
								<span class="flex-1">Sync failed — context may be stale or missing.</span>
								<button
									class="text-neon-cyan/60 hover:text-neon-cyan text-[10px] shrink-0"
									onclick={() => handleSync(selectedWorkspace?.id ?? '')}
									disabled={syncingId === selectedWorkspace?.id}
								>{syncingId === selectedWorkspace?.id ? 'Syncing...' : 'retry'}</button>
							</div>
						{:else if syncingId === selectedWorkspace.id}
							<div class="text-[10px] text-neon-cyan px-2 py-1.5 bg-neon-cyan/5 border border-neon-cyan/10 flex items-center gap-2">
								<Icon name="refresh" size={10} class="animate-spin shrink-0" />
								<span>Syncing workspace context...</span>
							</div>
						{/if}

						<!-- Context completeness -->
						<div class="flex items-center gap-2">
							<span class="text-[10px] text-text-secondary">Completeness</span>
							<InlineProgress percent={selectedWorkspace.context_completeness * 100} class="flex-1" />
							<span class="text-[10px] text-neon-cyan">
								{Math.round(selectedWorkspace.context_completeness * 100)}%
							</span>
						</div>

						<!-- Field breakdown -->
						<div class="space-y-1.5">
							{#each contextFields as field (field.key)}
								<div class="flex items-center gap-2 text-[11px]">
									<span class="w-24 text-text-secondary shrink-0">{field.label}</span>
									<span class="text-[9px] px-1 py-0.5 border shrink-0
										{selectedWorkspace.sync_status === 'synced'
											? 'text-neon-green border-neon-green/20 bg-neon-green/5'
											: 'text-text-dim border-neon-cyan/5'}">
										{selectedWorkspace.sync_status === 'synced' ? 'auto' : 'n/a'}
									</span>
									<span class="text-text-dim truncate flex-1">
										{selectedWorkspace.sync_status === 'synced' ? 'Detected from repo' : 'Not synced'}
									</span>
								</div>
							{/each}
						</div>

						<div class="pt-2 border-t border-neon-cyan/5">
							<p class="text-[10px] text-text-dim">
								Auto-detected fields serve as the base layer. Manual edits via
								ContextProfileEditor override these fields. Per-request context
								has the highest priority.
							</p>
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Status bar -->
	<div class="flex items-center gap-3 px-3 py-1.5 border-t border-neon-cyan/10 text-[10px] text-text-dim">
		{#if wsHealth}
			<span class="flex items-center gap-1">
				{#if wsHealth.github_connected}
					<StatusDot color="green" />
				{:else}
					<StatusDot color="red" />
				{/if}
				{wsHealth.github_connected ? wsHealth.github_username : 'Not connected'}
			</span>
			<span>Links: {wsHealth.total_links}</span>
			<span class="text-neon-green">{wsHealth.synced} synced</span>
			{#if wsHealth.stale > 0}
				<span class="text-neon-yellow">{wsHealth.stale} stale</span>
			{/if}
			{#if wsHealth.errors > 0}
				<span class="text-neon-red">{wsHealth.errors} error</span>
			{/if}
		{:else}
			<span>Workspace health unavailable</span>
		{/if}
	</div>
</div>
