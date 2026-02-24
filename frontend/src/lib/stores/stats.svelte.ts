import { fetchStats } from '$lib/api/client';
import type { StatsResponse } from '$lib/api/client';

class StatsState {
	stats = $state<StatsResponse | null>(null);
	projectStats = $state<StatsResponse | null>(null);
	activeProject = $state<string | null>(null);
	isLoading = $state(false);
	isProjectLoading = $state(false);
	private lastTotal: number | null = null;
	private lastProjectName: string | null = null;
	private projectGeneration = 0;

	async load(currentTotal: number) {
		if (this.isLoading) return;
		if (this.stats && this.lastTotal === currentTotal) return;

		this.isLoading = true;
		this.lastTotal = currentTotal;
		try {
			this.stats = await fetchStats();
			// Invalidate project stats so they refresh on next access
			if (this.activeProject) {
				this.lastProjectName = null;
				this.loadForProject(this.activeProject);
			}
		} finally {
			this.isLoading = false;
		}
	}

	async loadForProject(projectName: string) {
		if (this.lastProjectName === projectName && this.projectStats) return;
		this.lastProjectName = projectName;
		const gen = ++this.projectGeneration;
		this.isProjectLoading = true;
		try {
			const result = await fetchStats(projectName);
			if (gen === this.projectGeneration) {
				this.projectStats = result;
			}
		} finally {
			if (gen === this.projectGeneration) {
				this.isProjectLoading = false;
			}
		}
	}

	/** Set the active project context for header display. null = global. */
	setContext(projectName: string | null) {
		this.activeProject = projectName;
		if (projectName) {
			if (this.lastProjectName !== projectName) {
				this.projectStats = null; // trigger fallback to global
			}
			this.loadForProject(projectName);
		}
	}

	clearProjectContext() {
		this.activeProject = null;
		this.projectStats = null;
		this.lastProjectName = null;
		++this.projectGeneration;
	}

	/** The stats currently relevant to the active context. */
	get activeStats(): StatsResponse | null {
		if (!this.activeProject) return this.stats;
		return this.projectStats ?? this.stats; // fallback while loading
	}

	/** Clear cached stats (e.g. after clear-all history). */
	reset() {
		this.stats = null;
		this.lastTotal = null;
		this.projectStats = null;
		this.lastProjectName = null;
		this.activeProject = null;
		this.projectGeneration = 0;
	}
}

export const statsState = new StatsState();
