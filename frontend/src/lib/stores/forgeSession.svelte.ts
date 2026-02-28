import type { CodebaseContext, OptimizeMetadata } from '$lib/api/client';
import type { ForgeMode } from '$lib/stores/forgeMachine.svelte';
import type { FileDescriptor } from '$lib/utils/fileDescriptor';
import { FILE_DESCRIPTOR_KINDS, descriptorsMatch } from '$lib/utils/fileDescriptor';
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
	contextSource: 'manual' | 'project' | 'template' | 'workspace' | null;
	activeTemplateId: string | null;
}

export interface WorkspaceTab {
	id: string;
	name: string;
	draft: ForgeSessionDraft;
	resultId: string | null;
	mode: ForgeMode;
	/** The document this tab is viewing/editing. Null for fresh "Untitled" tabs. */
	document: FileDescriptor | null;
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
		document: null,
	};
}

/** Validate and reconstitute a FileDescriptor from sessionStorage. Returns null if invalid. */
function _hydrateDocument(raw: unknown): FileDescriptor | null {
	if (!raw || typeof raw !== 'object') return null;
	const obj = raw as Record<string, unknown>;
	if (typeof obj.kind !== 'string' || !FILE_DESCRIPTOR_KINDS.includes(obj.kind as any)) return null;
	if (typeof obj.id !== 'string' || typeof obj.name !== 'string') return null;
	return obj as unknown as FileDescriptor;
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
	 * Load content into the forge, always in its own tab.
	 * Reuses an existing empty tab if one exists; otherwise creates a new tab.
	 * Used when loading a prompt from a project card, history entry, or result action.
	 */
	loadRequest(req: Partial<ForgeSessionDraft> & { text: string }): void {
		this.isActive = true;
		windowManager.openIDE();
		const newDraft = { ...createEmptyDraft(), ...req };
		const tabName = req.title || this._nextUntitledName();

		// Reuse an existing empty tab, or create a new one
		const emptyTab = this.tabs.find((t) => this._isTabEmpty(t));
		if (emptyTab) {
			emptyTab.draft = newDraft;
			emptyTab.name = tabName;
			this.activeTabId = emptyTab.id;
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
				name: tabName,
				draft: newDraft,
				resultId: null,
				mode: 'compose',
				document: null,
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

	private _lastCreateTime = 0;

	/**
	 * Create a new tab with MAX_TABS enforcement and numbered naming.
	 * Includes a debounce guard (200ms) to prevent rapid duplicate creation
	 * from keyboard auto-repeat or double-clicks.
	 * Does NOT handle save/restore of tab coherence — callers must do that.
	 * Returns the new tab, or null if blocked.
	 */
	createTab(): WorkspaceTab | null {
		// Debounce guard — reject calls within 200ms of the last successful creation
		const now = Date.now();
		if (now - this._lastCreateTime < 200) return null;
		this._lastCreateTime = now;

		// Enforce MAX_TABS — evict LRU non-active tab
		if (this.tabs.length >= MAX_TABS) {
			const evictIdx = this.tabs.findLastIndex(t => t.id !== this.activeTabId);
			if (evictIdx >= 0) {
				this.tabs.splice(evictIdx, 1);
			} else {
				return null;
			}
		}
		const tab: WorkspaceTab = {
			id: typeof crypto !== 'undefined' ? crypto.randomUUID() : Math.random().toString(),
			name: this._nextUntitledName(),
			draft: createEmptyDraft(),
			resultId: null,
			mode: 'compose',
			document: null,
		};
		this.tabs.push(tab);
		this.activeTabId = tab.id;
		this._persistDraft();
		return tab;
	}

	/**
	 * Check if a tab is truly empty — no user-entered content whatsoever.
	 * An empty tab has: no prompt text, no title, no project, no tags,
	 * no version, no result, no context, and is in compose mode.
	 */
	private _isTabEmpty(tab: WorkspaceTab): boolean {
		return (
			tab.draft.text === '' &&
			tab.draft.title === '' &&
			tab.draft.project === '' &&
			tab.draft.tags === '' &&
			tab.draft.version === '' &&
			tab.draft.promptId === '' &&
			tab.draft.contextProfile === null &&
			tab.resultId === null &&
			tab.mode === 'compose'
		);
	}

	/**
	 * Return an existing empty tab or create a new one.
	 * Use this for "New Forge" entry points (Start Menu, desktop context menu)
	 * that should reuse an idle tab rather than stacking duplicates.
	 */
	ensureTab(): WorkspaceTab | null {
		const fresh = this.tabs.find((t) => this._isTabEmpty(t));
		if (fresh) {
			this.activeTabId = fresh.id;
			return fresh;
		}
		return this.createTab();
	}

	/** Find an existing tab whose document matches the given descriptor, or null. */
	findTabByDocument(descriptor: FileDescriptor): WorkspaceTab | null {
		return this.tabs.find(
			(t) => t.document !== null && descriptorsMatch(t.document, descriptor)
		) ?? null;
	}

	private _nextUntitledName(): string {
		const existing = new Set(this.tabs.map(t => t.name));
		for (let i = 1; i <= MAX_TABS + 1; i++) {
			const name = `Untitled ${i}`;
			if (!existing.has(name)) return name;
		}
		return `Untitled ${this.tabs.length + 1}`;
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
		this._lastCreateTime = 0;
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
						document: _hydrateDocument(t.document),
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
