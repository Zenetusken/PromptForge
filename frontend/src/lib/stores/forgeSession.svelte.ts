import type { CodebaseContext, OptimizeMetadata } from '$lib/api/client';
import type { ForgeMode } from '$lib/stores/forgeMachine.svelte';
import { providerState } from '$lib/stores/provider.svelte';
import { settingsState } from '$lib/stores/settings.svelte';
import { windowManager } from '$lib/stores/windowManager.svelte';

export type SourceAction = 'optimize' | 'reiterate' | null;

export interface ForgeSessionDraft {
	text: string;
	title: string;
	project: string;
	promptId: string;
	tags: string;
	version: string;
	sourceAction: SourceAction;
	strategy: string;
	secondaryStrategies: string[];
	contextProfile: CodebaseContext | null;
	contextSource: 'manual' | 'project' | 'template' | null;
	activeTemplateId: string | null;
}

export interface WorkspaceTab {
	id: string;
	name: string;
	draft: ForgeSessionDraft;
	resultId: string | null;
	mode: ForgeMode;
}

export function createEmptyDraft(): ForgeSessionDraft {
	return {
		text: '',
		title: '',
		project: '',
		promptId: '',
		tags: '',
		version: '',
		sourceAction: null,
		strategy: settingsState.defaultStrategy || 'auto',
		secondaryStrategies: [],
		contextProfile: null,
		contextSource: null,
		activeTemplateId: null,
	};
}

const STORAGE_KEY = 'pf_forge_draft';
const MAX_TABS = 5;

function createInitialTab(): WorkspaceTab {
	return {
		id: typeof crypto !== 'undefined' ? crypto.randomUUID() : Math.random().toString(),
		name: 'Untitled 1',
		draft: createEmptyDraft(),
		resultId: null,
		mode: 'compose',
	};
}

class ForgeSessionState {
	tabs: WorkspaceTab[] = $state([createInitialTab()]);
	activeTabId: string = $state('');
	/** Whether the IDE workspace is visible. Set by activate(), cleared by reset(). */
	isActive: boolean = $state(false);

	constructor() {
		this.activeTabId = this.tabs[0].id;
	}

	get activeTab(): WorkspaceTab {
		return this.tabs.find((t) => t.id === this.activeTabId) || this.tabs[0];
	}

	get draft(): ForgeSessionDraft {
		return this.activeTab.draft;
	}

	set draft(value: ForgeSessionDraft) {
		const tab = this.activeTab;
		if (tab) tab.draft = value;
	}

	showMetadata: boolean = $state(false);
	showContext: boolean = $state(false);
	showStrategy: boolean = $state(false);
	validationErrors: Record<string, string> = $state({});
	duplicateTitleWarning: boolean = $state(false);
	get autoRetryOnRateLimit(): boolean { return settingsState.autoRetryOnRateLimit; }

	// Derived booleans — only recompute when the referenced draft fields change
	hasText: boolean = $derived(!!this.draft.text.trim());
	hasMetadata: boolean = $derived(
		!!(this.draft.title || this.draft.project || this.draft.tags || this.draft.version)
	);
	hasContext: boolean = $derived(
		this.draft.contextProfile !== null &&
		Object.keys(this.draft.contextProfile).length > 0
	);
	charCount: number = $derived(this.draft.text.length);

	/** Open the IDE workspace. */
	activate(): void {
		this.isActive = true;
		windowManager.openIDE();
		this._persistDraft();
	}

	/**
	 * Replace the entire draft with a new request.
	 * Used when loading a prompt from a project card, history entry, or result action.
	 */
	loadRequest(req: Partial<ForgeSessionDraft> & { text: string }): void {
		this.isActive = true;
		windowManager.openIDE();
		const newDraft = { ...createEmptyDraft(), ...req };

		if (!this.draft.text.trim()) {
			this.draft = newDraft;
			this.activeTab.name = req.title || 'Loaded Prompt';
		} else {
			// Evict LRU non-active tab when at limit
			if (this.tabs.length >= MAX_TABS) {
				const evictIdx = this.tabs.findLastIndex(t => t.id !== this.activeTabId);
				if (evictIdx >= 0) {
					this.tabs.splice(evictIdx, 1);
				}
			}
			const newTab: WorkspaceTab = {
				id: typeof crypto !== 'undefined' ? crypto.randomUUID() : Math.random().toString(),
				name: req.title || 'New Prompt',
				draft: newDraft,
				resultId: null,
				mode: 'compose',
			};
			this.tabs.push(newTab);
			this.activeTabId = newTab.id;
		}

		this.validationErrors = {};
		this.duplicateTitleWarning = false;

		// Auto-expand metadata section if metadata is present
		if (req.title || req.project || req.tags || req.version || req.sourceAction) {
			this.showMetadata = true;
		}

		// Auto-expand context section if context is present
		if (req.contextProfile) {
			this.showContext = true;
		}

		// Auto-expand strategy section if strategy is set
		if (req.strategy && req.strategy !== 'auto') {
			this.showStrategy = true;
		}

		this._persistDraft();
	}

	/**
	 * Patch individual draft fields without replacing the whole draft.
	 */
	updateDraft(patch: Partial<ForgeSessionDraft>): void {
		if ('text' in patch && patch.text?.trim()) {
			this.isActive = true;
			windowManager.openIDE();
		}
		this.draft = { ...this.draft, ...patch };
		this._persistDraft();
	}

	/**
	 * Build OptimizeMetadata from the current draft for submission.
	 */
	buildMetadata(): OptimizeMetadata | undefined {
		const meta: OptimizeMetadata = {};
		const d = this.draft;

		if (d.title.trim()) meta.title = d.title.trim();
		if (d.project.trim()) meta.project = d.project.trim();
		if (d.tags.trim()) {
			const tags = d.tags.split(',').map((t) => t.trim()).filter(Boolean);
			if (tags.length > 0) meta.tags = tags;
		}
		if (d.version.trim()) meta.version = d.version.trim();
		if (providerState.selectedProvider) meta.provider = providerState.selectedProvider;
		if (d.strategy !== 'auto') meta.strategy = d.strategy;
		if (d.secondaryStrategies.length > 0) meta.secondary_frameworks = d.secondaryStrategies;
		if (d.promptId) meta.prompt_id = d.promptId;

		if (d.contextProfile && Object.keys(d.contextProfile).length > 0) {
			meta.codebase_context = d.contextProfile;
		}

		return Object.keys(meta).length > 0 ? meta : undefined;
	}

	/**
	 * Validate required fields when sourceAction is set.
	 * Returns true if valid (or no validation needed).
	 */
	validate(): boolean {
		const errors: Record<string, string> = {};
		if (!this.draft.sourceAction) {
			this.validationErrors = {};
			return true;
		}

		if (!this.draft.project.trim()) errors.project = 'Project is required';
		if (!this.draft.title.trim()) errors.title = 'Title is required';
		if (!this.draft.version.trim()) {
			errors.version = 'Version is required';
		} else if (!/^v\d+$/i.test(this.draft.version.trim())) {
			errors.version = 'Must be v<number> (e.g. v1)';
		}
		if (this.draft.tags.trim()) {
			const tags = this.draft.tags.split(',').map((t) => t.trim()).filter(Boolean);
			if (new Set(tags).size < tags.length) {
				errors.tags = 'Duplicate tags found';
			}
		}

		this.validationErrors = errors;
		return Object.keys(errors).length === 0;
	}

	/**
	 * Reset the entire session to empty state.
	 */
	reset(): void {
		this.isActive = false;
		windowManager.closeIDE();
		this.tabs = [createInitialTab()];
		this.activeTabId = this.tabs[0].id;
		this.showMetadata = false;
		this.showContext = false;
		this.showStrategy = false;
		this.validationErrors = {};
		this.duplicateTitleWarning = false;
		this._clearStorage();
	}

	/**
	 * Focus the forge textarea in the sidebar.
	 */
	focusTextarea(): void {
		this.isActive = true;
		windowManager.openIDE();
		this._persistDraft();
		queueMicrotask(() => {
			document.querySelector<HTMLTextAreaElement>(
				'[data-testid="forge-panel-textarea"]',
			)?.focus();
		});
	}

	/** Persist current tab state to sessionStorage. Called by tabCoherence after state changes. */
	persistTabs(): void {
		this._persistDraft();
	}

	// --- Storage persistence ---

	private _persistDraft(): void {
		if (typeof window === 'undefined') return;
		try {
			sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
				tabs: this.tabs,
				activeTabId: this.activeTabId,
				isActive: this.isActive
			}));
		} catch {
			// Storage full or unavailable — ignore
		}
	}

	private _clearStorage(): void {
		if (typeof window === 'undefined') return;
		try {
			sessionStorage.removeItem(STORAGE_KEY);
		} catch {
			// ignore
		}
	}

	/** Hydrate draft from sessionStorage on construction. */
	_hydrateFromStorage(): void {
		if (typeof window === 'undefined') return;
		try {
			const raw = sessionStorage.getItem(STORAGE_KEY);
			if (raw) {
				const parsed = JSON.parse(raw);
				if (parsed && parsed.tabs && Array.isArray(parsed.tabs)) {
					this.tabs = parsed.tabs.map((t: any) => ({
						...t,
						draft: { ...createEmptyDraft(), ...t.draft },
						resultId: t.resultId ?? null,
						mode: t.mode === 'forging' ? 'compose' : (t.mode ?? 'compose'),
					}));
					this.activeTabId = parsed.activeTabId || this.tabs[0].id;
					this.isActive = !!parsed.isActive;
				} else if (parsed && typeof parsed === 'object' && typeof parsed.text === 'string' && parsed.text.trim()) {
					this.draft = { ...createEmptyDraft(), ...parsed };
					this.activeTab.name = parsed.title || 'Recovered Prompt';
					this.isActive = true;
				}
			}
		} catch {
			// Corrupted data — ignore
		}
	}
}

export const forgeSession = new ForgeSessionState();

// Hydrate on module load (client-side only)
if (typeof window !== 'undefined') {
	forgeSession._hydrateFromStorage();
}
