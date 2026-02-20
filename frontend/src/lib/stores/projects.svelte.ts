import {
	fetchProjects,
	fetchProject,
	createProject,
	updateProject,
	deleteProject,
	archiveProject,
	unarchiveProject,
	addProjectPrompt,
	updateProjectPrompt,
	deleteProjectPrompt,
	reorderProjectPrompts,
	type ProjectSummary,
	type ProjectDetail,
	type ProjectListResponse,
	type ArchiveResponse,
} from '$lib/api/client';
import { historyState } from '$lib/stores/history.svelte';

class ProjectsState {
	items: ProjectSummary[] = $state([]);
	total: number = $state(0);
	page: number = $state(1);
	perPage: number = $state(20);
	isLoading: boolean = $state(false);
	hasLoaded: boolean = $state(false);
	searchQuery: string = $state('');
	statusFilter: 'active' | 'archived' = $state('active');
	activeProject: ProjectDetail | null = $state(null);
	activeProjectLoading: boolean = $state(false);

	/** All projects (active + archived) for filter dropdowns. */
	allItems: ProjectSummary[] = $state([]);
	allItemsLoaded: boolean = $state(false);
	private allItemsLoading: boolean = false;

	private controller: AbortController | null = null;

	async loadProjects(params?: { page?: number }) {
		this.controller?.abort();
		this.controller = new AbortController();
		const { signal } = this.controller;

		this.isLoading = true;
		const requestedPage = params?.page ?? 1;

		try {
			const response: ProjectListResponse = await fetchProjects({
				page: requestedPage,
				per_page: this.perPage,
				search: this.searchQuery || undefined,
				status: this.statusFilter,
				sort: 'updated_at',
				order: 'desc',
				signal,
			});

			if (requestedPage > 1) {
				const existingIds = new Set(this.items.map((p) => p.id));
				const newItems = response.items.filter((p) => !existingIds.has(p.id));
				this.items = [...this.items, ...newItems];
			} else {
				this.items = response.items;
			}

			this.total = response.total;
			this.page = response.page;
			this.perPage = response.per_page;
			this.hasLoaded = true;
		} catch (e: unknown) {
			if (e instanceof DOMException && e.name === 'AbortError') return;
		} finally {
			this.isLoading = false;
			this.controller = null;
		}
	}

	/** Load all projects (active + archived) for use in filter dropdowns. */
	async loadAllProjects() {
		if (this.allItemsLoaded || this.allItemsLoading) return;
		this.allItemsLoading = true;
		try {
			const [active, archived] = await Promise.all([
				fetchProjects({ per_page: 100, status: 'active' }),
				fetchProjects({ per_page: 100, status: 'archived' }),
			]);
			this.allItems = [...active.items, ...archived.items];
			this.allItemsLoaded = true;
		} finally {
			this.allItemsLoading = false;
		}
	}

	setSearch(query: string) {
		this.searchQuery = query;
		this.loadProjects();
	}

	setStatusFilter(status: 'active' | 'archived') {
		this.statusFilter = status;
		this.items = [];
		this.total = 0;
		this.hasLoaded = false;
		this.loadProjects();
	}

	async loadProject(id: string) {
		this.activeProjectLoading = true;
		try {
			this.activeProject = await fetchProject(id);
		} finally {
			this.activeProjectLoading = false;
		}
	}

	private invalidateAllItems() {
		this.allItemsLoaded = false;
		this.allItems = [];
	}

	async create(name: string, description?: string): Promise<ProjectDetail | null> {
		const project = await createProject({ name, description });
		if (project) {
			this.invalidateAllItems();
			await this.loadProjects();
		}
		return project;
	}

	async update(id: string, data: { name?: string; description?: string }): Promise<ProjectDetail | null> {
		const updatedAt = this.activeProject?.id === id ? this.activeProject.updated_at : undefined;
		const project = await updateProject(id, data, updatedAt);
		if (project) {
			if (data.name) this.invalidateAllItems();
			this.activeProject = project;
			await this.loadProjects();
		}
		return project;
	}

	async remove(id: string): Promise<boolean> {
		const success = await deleteProject(id);
		if (success) {
			this.invalidateAllItems();
			this.items = this.items.filter((p) => p.id !== id);
			this.total = Math.max(0, this.total - 1);
			if (this.activeProject?.id === id) {
				this.activeProject = null;
			}
			// Refresh history to remove orphaned entries from deleted project
			historyState.loadHistory();
		}
		return success;
	}

	async archive(id: string): Promise<ArchiveResponse | null> {
		const result = await archiveProject(id);
		if (result) {
			this.invalidateAllItems();
			if (this.statusFilter === 'active') {
				this.items = this.items.filter((p) => p.id !== id);
				this.total = Math.max(0, this.total - 1);
			} else {
				await this.loadProjects();
			}
			if (this.activeProject?.id === id) {
				this.activeProject = {
					...this.activeProject,
					status: 'archived',
					updated_at: result.updated_at,
				};
			}
		}
		return result;
	}

	async unarchive(id: string): Promise<ArchiveResponse | null> {
		const result = await unarchiveProject(id);
		if (result) {
			this.invalidateAllItems();
			if (this.statusFilter === 'archived') {
				this.items = this.items.filter((p) => p.id !== id);
				this.total = Math.max(0, this.total - 1);
			} else {
				await this.loadProjects();
			}
			if (this.activeProject?.id === id) {
				this.activeProject = {
					...this.activeProject,
					status: 'active',
					updated_at: result.updated_at,
				};
			}
		}
		return result;
	}

	async addPrompt(projectId: string, content: string) {
		const prompt = await addProjectPrompt(projectId, content);
		if (prompt && this.activeProject?.id === projectId) {
			this.activeProject = {
				...this.activeProject,
				prompts: [...this.activeProject.prompts, prompt],
			};
			// Update prompt count in list
			this.items = this.items.map((p) =>
				p.id === projectId ? { ...p, prompt_count: p.prompt_count + 1 } : p,
			);
		}
		return prompt;
	}

	async updatePrompt(projectId: string, promptId: string, content: string) {
		const prompt = await updateProjectPrompt(projectId, promptId, content);
		if (prompt && this.activeProject?.id === projectId) {
			this.activeProject = {
				...this.activeProject,
				prompts: this.activeProject.prompts.map((p) => (p.id === promptId ? prompt : p)),
			};
		}
		return prompt;
	}

	async removePrompt(projectId: string, promptId: string) {
		const success = await deleteProjectPrompt(projectId, promptId);
		if (success && this.activeProject?.id === projectId) {
			this.activeProject = {
				...this.activeProject,
				prompts: this.activeProject.prompts.filter((p) => p.id !== promptId),
			};
			this.items = this.items.map((p) =>
				p.id === projectId ? { ...p, prompt_count: Math.max(0, p.prompt_count - 1) } : p,
			);
		}
		return success;
	}

	async reorderPrompts(projectId: string, promptIds: string[]) {
		const success = await reorderProjectPrompts(projectId, promptIds);
		if (success && this.activeProject?.id === projectId) {
			// Reorder local prompts to match
			const byId = new Map(this.activeProject.prompts.map((p) => [p.id, p]));
			const reordered = promptIds
				.map((id, idx) => {
					const p = byId.get(id);
					return p ? { ...p, order_index: idx } : null;
				})
				.filter((p): p is NonNullable<typeof p> => p !== null);
			this.activeProject = { ...this.activeProject, prompts: reordered };
		}
		return success;
	}
}

export const projectsState = new ProjectsState();
