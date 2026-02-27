import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Mock providerState before importing forgeSession
vi.mock('$lib/stores/provider.svelte', () => ({
	providerState: {
		selectedProvider: null,
	},
}));

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

import { forgeSession } from './forgeSession.svelte';

describe('ForgeSessionState', () => {
	beforeEach(() => {
		forgeSession.reset();
		storageMap.clear();
	});

	describe('initial state', () => {
		it('starts with empty text', () => {
			expect(forgeSession.draft.text).toBe('');
		});

		it('hasText is false when empty', () => {
			expect(forgeSession.hasText).toBe(false);
		});

		it('hasMetadata is false when no metadata set', () => {
			expect(forgeSession.hasMetadata).toBe(false);
		});

		it('charCount is 0 when empty', () => {
			expect(forgeSession.charCount).toBe(0);
		});

		it('strategy defaults to auto', () => {
			expect(forgeSession.draft.strategy).toBe('auto');
		});

		it('isActive defaults to false', () => {
			expect(forgeSession.isActive).toBe(false);
		});
	});

	describe('loadRequest', () => {
		it('replaces the entire draft', () => {
			forgeSession.loadRequest({
				text: 'hello world',
				project: 'My Project',
				promptId: 'pid-1',
				title: 'Test Title',
				tags: 'tag1, tag2',
				version: 'v1',
				sourceAction: 'optimize',
			});

			expect(forgeSession.draft.text).toBe('hello world');
			expect(forgeSession.draft.project).toBe('My Project');
			expect(forgeSession.draft.promptId).toBe('pid-1');
			expect(forgeSession.draft.title).toBe('Test Title');
			expect(forgeSession.draft.tags).toBe('tag1, tag2');
			expect(forgeSession.draft.version).toBe('v1');
			expect(forgeSession.draft.sourceAction).toBe('optimize');
		});

		it('defaults unspecified fields to empty', () => {
			forgeSession.loadRequest({ text: 'just text' });

			expect(forgeSession.draft.project).toBe('');
			expect(forgeSession.draft.promptId).toBe('');
			expect(forgeSession.draft.title).toBe('');
			expect(forgeSession.draft.tags).toBe('');
			expect(forgeSession.draft.version).toBe('');
			expect(forgeSession.draft.sourceAction).toBeNull();
			expect(forgeSession.draft.strategy).toBe('auto');
		});

		it('clears validation errors on load', () => {
			forgeSession.validationErrors = { title: 'error' };
			forgeSession.loadRequest({ text: 'new text' });
			expect(forgeSession.validationErrors).toEqual({});
		});

		it('auto-expands metadata when metadata fields present', () => {
			forgeSession.loadRequest({ text: 'test', title: 'Title' });
			expect(forgeSession.showMetadata).toBe(true);
		});

		it('auto-expands context when contextProfile present', () => {
			forgeSession.loadRequest({
				text: 'test',
				contextProfile: { language: 'Python' },
			});
			expect(forgeSession.showContext).toBe(true);
		});

		it('auto-expands strategy when non-auto strategy present', () => {
			forgeSession.loadRequest({
				text: 'test',
				strategy: 'co-star',
			});
			expect(forgeSession.showStrategy).toBe(true);
		});

		it('reuses the empty initial tab on first load', () => {
			expect(forgeSession.tabs.length).toBe(1);
			const initialId = forgeSession.activeTabId;

			forgeSession.loadRequest({ text: 'first prompt' });

			// Should reuse the empty tab, not create a second one
			expect(forgeSession.tabs.length).toBe(1);
			expect(forgeSession.activeTabId).toBe(initialId);
			expect(forgeSession.draft.text).toBe('first prompt');
		});

		it('creates a new tab when loading into a non-empty session', () => {
			forgeSession.loadRequest({ text: 'first prompt' });
			expect(forgeSession.tabs.length).toBe(1);

			forgeSession.loadRequest({ text: 'second prompt', title: 'Second' });

			// Second load should create a new tab, preserving the first
			expect(forgeSession.tabs.length).toBe(2);
			const firstTab = forgeSession.tabs.find(t => t.draft.text === 'first prompt');
			const secondTab = forgeSession.tabs.find(t => t.draft.text === 'second prompt');
			expect(firstTab).toBeDefined();
			expect(secondTab).toBeDefined();
			expect(secondTab!.name).toBe('Second');
		});

		it('names loaded tabs using the title or next Untitled number', () => {
			// Load with title — tab gets that name
			forgeSession.loadRequest({ text: 'prompt A', title: 'My Prompt' });
			expect(forgeSession.activeTab.name).toBe('My Prompt');

			// Load without title — tab gets next available "Untitled N"
			// Since "Untitled 1" isn't taken (renamed to "My Prompt"), it picks "Untitled 1"
			forgeSession.loadRequest({ text: 'prompt B' });
			expect(forgeSession.activeTab.name).toBe('Untitled 1');

			// Load a third without title — now "Untitled 1" is taken, picks "Untitled 2"
			forgeSession.loadRequest({ text: 'prompt C' });
			expect(forgeSession.activeTab.name).toBe('Untitled 2');
		});
	});

	describe('updateDraft', () => {
		it('patches individual fields', () => {
			forgeSession.loadRequest({ text: 'original' });
			forgeSession.updateDraft({ title: 'Updated Title' });

			expect(forgeSession.draft.text).toBe('original');
			expect(forgeSession.draft.title).toBe('Updated Title');
		});

		it('multiple patches accumulate', () => {
			forgeSession.updateDraft({ text: 'first' });
			forgeSession.updateDraft({ project: 'proj' });

			expect(forgeSession.draft.text).toBe('first');
			expect(forgeSession.draft.project).toBe('proj');
		});
	});

	describe('derived properties', () => {
		it('hasText returns true for non-whitespace text', () => {
			forgeSession.updateDraft({ text: '  hello  ' });
			expect(forgeSession.hasText).toBe(true);
		});

		it('hasText returns false for whitespace-only text', () => {
			forgeSession.updateDraft({ text: '   ' });
			expect(forgeSession.hasText).toBe(false);
		});

		it('hasMetadata returns true when any metadata field is set', () => {
			forgeSession.updateDraft({ title: 'A title' });
			expect(forgeSession.hasMetadata).toBe(true);
		});

		it('hasContext returns true when contextProfile has fields', () => {
			forgeSession.updateDraft({ contextProfile: { language: 'TS' } });
			expect(forgeSession.hasContext).toBe(true);
		});

		it('hasContext returns false for null contextProfile', () => {
			forgeSession.updateDraft({ contextProfile: null });
			expect(forgeSession.hasContext).toBe(false);
		});

		it('charCount tracks text length', () => {
			forgeSession.updateDraft({ text: 'abc' });
			expect(forgeSession.charCount).toBe(3);
		});
	});

	describe('validate', () => {
		it('returns true when no sourceAction', () => {
			expect(forgeSession.validate()).toBe(true);
		});

		it('requires project, title, version when sourceAction is set', () => {
			forgeSession.updateDraft({ sourceAction: 'optimize' });
			expect(forgeSession.validate()).toBe(false);
			expect(forgeSession.validationErrors.project).toBeDefined();
			expect(forgeSession.validationErrors.title).toBeDefined();
			expect(forgeSession.validationErrors.version).toBeDefined();
		});

		it('validates version format', () => {
			forgeSession.loadRequest({
				text: 'test',
				sourceAction: 'optimize',
				project: 'proj',
				title: 'title',
				version: 'invalid',
			});
			expect(forgeSession.validate()).toBe(false);
			expect(forgeSession.validationErrors.version).toContain('v<number>');
		});

		it('passes with valid fields', () => {
			forgeSession.loadRequest({
				text: 'test',
				sourceAction: 'optimize',
				project: 'proj',
				title: 'title',
				version: 'v1',
			});
			expect(forgeSession.validate()).toBe(true);
			expect(forgeSession.validationErrors).toEqual({});
		});

		it('detects duplicate tags', () => {
			forgeSession.loadRequest({
				text: 'test',
				sourceAction: 'reiterate',
				project: 'proj',
				title: 'title',
				version: 'v2',
				tags: 'tag1, tag1',
			});
			expect(forgeSession.validate()).toBe(false);
			expect(forgeSession.validationErrors.tags).toBeDefined();
		});
	});

	describe('buildMetadata', () => {
		it('returns undefined when no metadata', () => {
			forgeSession.loadRequest({ text: 'just text' });
			expect(forgeSession.buildMetadata()).toBeUndefined();
		});

		it('includes title, project, tags, version', () => {
			forgeSession.loadRequest({
				text: 'test',
				title: 'My Title',
				project: 'Proj',
				tags: 'a, b',
				version: 'v1',
			});
			const meta = forgeSession.buildMetadata();
			expect(meta).toEqual(expect.objectContaining({
				title: 'My Title',
				project: 'Proj',
				tags: ['a', 'b'],
				version: 'v1',
			}));
		});

		it('includes strategy when not auto', () => {
			forgeSession.updateDraft({ strategy: 'co-star' });
			const meta = forgeSession.buildMetadata();
			expect(meta?.strategy).toBe('co-star');
		});

		it('excludes strategy when auto', () => {
			forgeSession.updateDraft({ strategy: 'auto', title: 'X' });
			const meta = forgeSession.buildMetadata();
			expect(meta?.strategy).toBeUndefined();
		});

		it('includes secondary frameworks', () => {
			forgeSession.updateDraft({
				strategy: 'co-star',
				secondaryStrategies: ['risen', 'step-by-step'],
			});
			const meta = forgeSession.buildMetadata();
			expect(meta?.secondary_frameworks).toEqual(['risen', 'step-by-step']);
		});

		it('includes prompt_id', () => {
			forgeSession.loadRequest({ text: 'test', promptId: 'pid-1', title: 'X' });
			const meta = forgeSession.buildMetadata();
			expect(meta?.prompt_id).toBe('pid-1');
		});

		it('includes codebase_context', () => {
			forgeSession.loadRequest({
				text: 'test',
				contextProfile: { language: 'Rust' },
				title: 'X',
			});
			const meta = forgeSession.buildMetadata();
			expect(meta?.codebase_context).toEqual({ language: 'Rust' });
		});
	});

	describe('reset', () => {
		it('clears all state', () => {
			forgeSession.loadRequest({
				text: 'some text',
				title: 'title',
				project: 'proj',
				sourceAction: 'optimize',
			});
			forgeSession.showMetadata = true;
			forgeSession.validationErrors = { title: 'err' };

			forgeSession.reset();

			expect(forgeSession.draft.text).toBe('');
			expect(forgeSession.draft.title).toBe('');
			expect(forgeSession.draft.project).toBe('');
			expect(forgeSession.draft.sourceAction).toBeNull();
			expect(forgeSession.draft.strategy).toBe('auto');
			expect(forgeSession.isActive).toBe(false);
			expect(forgeSession.showMetadata).toBe(false);
			expect(forgeSession.validationErrors).toEqual({});
		});

		it('clears sessionStorage', () => {
			forgeSession.loadRequest({ text: 'persist me' });
			expect(storageMap.has('pf_forge_draft')).toBe(true);

			forgeSession.reset();
			expect(storageMap.has('pf_forge_draft')).toBe(false);
		});
	});

	describe('storage persistence', () => {
		/** Helper to extract the active tab's draft text from persisted storage. */
		function getPersistedText(): string | undefined {
			const stored = storageMap.get('pf_forge_draft');
			if (!stored) return undefined;
			const parsed = JSON.parse(stored);
			const tab = parsed.tabs?.find((t: any) => t.id === parsed.activeTabId) ?? parsed.tabs?.[0];
			return tab?.draft?.text;
		}

		it('persists draft to sessionStorage on loadRequest', () => {
			forgeSession.loadRequest({ text: 'hello' });
			expect(storageMap.has('pf_forge_draft')).toBe(true);
			expect(getPersistedText()).toBe('hello');
		});

		it('persists draft on updateDraft', () => {
			forgeSession.updateDraft({ text: 'world' });
			expect(storageMap.has('pf_forge_draft')).toBe(true);
			expect(getPersistedText()).toBe('world');
		});

		it('persists empty text without clearing storage', () => {
			forgeSession.updateDraft({ text: 'something' });
			expect(storageMap.has('pf_forge_draft')).toBe(true);

			forgeSession.updateDraft({ text: '' });
			// Tabs-based persistence keeps storage even when text is empty
			expect(storageMap.has('pf_forge_draft')).toBe(true);
			expect(getPersistedText()).toBe('');
		});

		it('hydrates from legacy single-draft storage', () => {
			storageMap.set('pf_forge_draft', JSON.stringify({
				text: 'hydrated text',
				title: 'Hydrated',
				project: '',
				promptId: '',
				tags: '',
				version: '',
				sourceAction: null,
				strategy: 'auto',
				secondaryStrategies: [],
				contextProfile: null,
				contextSource: null,
				activeTemplateId: null,
			}));

			forgeSession._hydrateFromStorage();
			expect(forgeSession.draft.text).toBe('hydrated text');
			expect(forgeSession.draft.title).toBe('Hydrated');
		});

		it('hydrates from tabs-based storage', () => {
			const tabId = 'test-tab-id';
			storageMap.set('pf_forge_draft', JSON.stringify({
				tabs: [{
					id: tabId,
					name: 'Test Tab',
					draft: {
						text: 'tab text',
						title: 'Tab Title',
					},
				}],
				activeTabId: tabId,
			}));

			forgeSession._hydrateFromStorage();
			expect(forgeSession.draft.text).toBe('tab text');
			expect(forgeSession.draft.title).toBe('Tab Title');
		});

		it('ignores corrupted storage data', () => {
			storageMap.set('pf_forge_draft', 'not-json');
			forgeSession.reset();
			forgeSession._hydrateFromStorage();
			expect(forgeSession.draft.text).toBe('');
		});

		it('ignores empty text in storage', () => {
			storageMap.set('pf_forge_draft', JSON.stringify({ text: '  ' }));
			forgeSession.reset();
			forgeSession._hydrateFromStorage();
			expect(forgeSession.draft.text).toBe('');
		});
	});

	describe('isActive workspace flag', () => {
		it('starts inactive', () => {
			expect(forgeSession.isActive).toBe(false);
		});

		it('activate() sets isActive and persists', () => {
			forgeSession.activate();
			expect(forgeSession.isActive).toBe(true);
			const stored = JSON.parse(storageMap.get('pf_forge_draft')!);
			expect(stored.isActive).toBe(true);
		});

		it('loadRequest auto-activates', () => {
			forgeSession.loadRequest({ text: 'hello' });
			expect(forgeSession.isActive).toBe(true);
		});

		it('updateDraft with text auto-activates', () => {
			forgeSession.updateDraft({ text: 'world' });
			expect(forgeSession.isActive).toBe(true);
		});

		it('updateDraft without text does not auto-activate', () => {
			forgeSession.updateDraft({ title: 'just a title' });
			expect(forgeSession.isActive).toBe(false);
		});

		it('updateDraft with empty text does not auto-activate', () => {
			forgeSession.updateDraft({ text: '   ' });
			expect(forgeSession.isActive).toBe(false);
		});

		it('focusTextarea auto-activates', () => {
			forgeSession.focusTextarea();
			expect(forgeSession.isActive).toBe(true);
		});

		it('reset() deactivates', () => {
			forgeSession.activate();
			expect(forgeSession.isActive).toBe(true);
			forgeSession.reset();
			expect(forgeSession.isActive).toBe(false);
		});

		it('hydrates isActive from tabs storage', () => {
			storageMap.set('pf_forge_draft', JSON.stringify({
				tabs: [{ id: 'x', name: 'X', draft: { text: 'hi' } }],
				activeTabId: 'x',
				isActive: true,
			}));
			forgeSession._hydrateFromStorage();
			expect(forgeSession.isActive).toBe(true);
		});

		it('hydrates isActive=false from tabs storage', () => {
			storageMap.set('pf_forge_draft', JSON.stringify({
				tabs: [{ id: 'y', name: 'Y', draft: { text: '' } }],
				activeTabId: 'y',
				isActive: false,
			}));
			forgeSession._hydrateFromStorage();
			expect(forgeSession.isActive).toBe(false);
		});

		it('legacy single-draft hydration auto-activates', () => {
			storageMap.set('pf_forge_draft', JSON.stringify({
				text: 'legacy text',
			}));
			forgeSession._hydrateFromStorage();
			expect(forgeSession.isActive).toBe(true);
		});
	});

	describe('deactivation preserves drafts', () => {
		it('setting isActive=false preserves tabs and draft text', () => {
			forgeSession.loadRequest({ text: 'my draft', title: 'Draft Tab' });
			expect(forgeSession.isActive).toBe(true);
			expect(forgeSession.tabs.length).toBe(1);

			forgeSession.isActive = false;

			expect(forgeSession.isActive).toBe(false);
			expect(forgeSession.tabs.length).toBe(1);
			expect(forgeSession.draft.text).toBe('my draft');
			expect(forgeSession.draft.title).toBe('Draft Tab');
		});
	});

	describe('createTab', () => {
		beforeEach(() => {
			vi.useFakeTimers();
		});

		afterEach(() => {
			vi.useRealTimers();
		});

		// Helper: advance past debounce guard between createTab calls
		function advancePastDebounce() {
			vi.advanceTimersByTime(250);
		}

		it('creates a new tab and sets it active', () => {
			const tab = forgeSession.createTab();
			expect(tab).not.toBeNull();
			expect(tab!.id).toBe(forgeSession.activeTabId);
			expect(tab!.draft.text).toBe('');
			expect(tab!.mode).toBe('compose');
			expect(tab!.resultId).toBeNull();
		});

		it('generates sequential "Untitled N" names', () => {
			// Reset starts with "Untitled 1"
			expect(forgeSession.activeTab.name).toBe('Untitled 1');

			advancePastDebounce();
			const tab2 = forgeSession.createTab();
			expect(tab2!.name).toBe('Untitled 2');

			advancePastDebounce();
			const tab3 = forgeSession.createTab();
			expect(tab3!.name).toBe('Untitled 3');
		});

		it('fills gaps in naming when tabs are closed', () => {
			advancePastDebounce();
			const tab2 = forgeSession.createTab();
			advancePastDebounce();
			forgeSession.createTab(); // Untitled 3

			// Remove "Untitled 2" — next should reuse the name
			forgeSession.tabs = forgeSession.tabs.filter(t => t.id !== tab2!.id);
			advancePastDebounce();
			const tab4 = forgeSession.createTab();
			expect(tab4!.name).toBe('Untitled 2');
		});

		it('enforces MAX_TABS (5) by evicting LRU non-active tab', () => {
			// Create tabs up to 5 total (1 initial + 4 new)
			advancePastDebounce(); forgeSession.createTab();
			advancePastDebounce(); forgeSession.createTab();
			advancePastDebounce(); forgeSession.createTab();
			advancePastDebounce(); forgeSession.createTab();
			expect(forgeSession.tabs.length).toBe(5);

			// Creating a 6th should evict one and stay at 5
			advancePastDebounce();
			const tab6 = forgeSession.createTab();
			expect(tab6).not.toBeNull();
			expect(forgeSession.tabs.length).toBe(5);
		});

		it('evicts the last non-active tab when at limit', () => {
			// Fill to 5 tabs
			advancePastDebounce(); forgeSession.createTab();
			advancePastDebounce(); forgeSession.createTab();
			advancePastDebounce(); forgeSession.createTab();
			advancePastDebounce(); forgeSession.createTab();
			expect(forgeSession.tabs.length).toBe(5);

			// The active tab is the last created — eviction should remove a non-active tab
			const activeId = forgeSession.activeTabId;
			advancePastDebounce();
			forgeSession.createTab();

			// One of the earlier tabs was evicted, not the previously active one
			expect(forgeSession.tabs.length).toBe(5);
			// New tab is now active
			expect(forgeSession.activeTabId).not.toBe(activeId);
		});

		it('persists tabs to sessionStorage', () => {
			advancePastDebounce();
			forgeSession.createTab();
			const stored = storageMap.get('pf_forge_draft');
			expect(stored).toBeDefined();
			const parsed = JSON.parse(stored!);
			expect(parsed.tabs.length).toBe(2);
		});

		it('debounces rapid calls within 200ms', () => {
			// First call succeeds
			const tab1 = forgeSession.createTab();
			expect(tab1).not.toBeNull();
			expect(forgeSession.tabs.length).toBe(2);

			// Immediate second call should be blocked
			const tab2 = forgeSession.createTab();
			expect(tab2).toBeNull();
			expect(forgeSession.tabs.length).toBe(2);

			// Third call at 100ms should still be blocked
			vi.advanceTimersByTime(100);
			const tab3 = forgeSession.createTab();
			expect(tab3).toBeNull();
			expect(forgeSession.tabs.length).toBe(2);

			// After 200ms total, should succeed again
			vi.advanceTimersByTime(150);
			const tab4 = forgeSession.createTab();
			expect(tab4).not.toBeNull();
			expect(forgeSession.tabs.length).toBe(3);
		});
	});

	describe('ensureTab', () => {
		it('reuses an existing empty tab instead of creating a new one', () => {
			// Initial state has 1 empty tab ("Untitled 1")
			expect(forgeSession.tabs.length).toBe(1);
			const initialTabId = forgeSession.activeTabId;

			const tab = forgeSession.ensureTab();
			expect(tab).not.toBeNull();
			expect(tab!.id).toBe(initialTabId);
			expect(forgeSession.tabs.length).toBe(1);
		});

		it('creates a new tab when all existing tabs have content', () => {
			// Put content in the initial tab
			forgeSession.updateDraft({ text: 'some prompt text' });
			expect(forgeSession.tabs.length).toBe(1);

			const tab = forgeSession.ensureTab();
			expect(tab).not.toBeNull();
			expect(forgeSession.tabs.length).toBe(2);
			expect(tab!.draft.text).toBe('');
		});

		it('creates a new tab when existing tab has a result', () => {
			// Mark the initial tab as having a result
			forgeSession.activeTab.resultId = 'some-result-id';
			expect(forgeSession.tabs.length).toBe(1);

			const tab = forgeSession.ensureTab();
			expect(tab).not.toBeNull();
			expect(forgeSession.tabs.length).toBe(2);
		});

		it('does not reuse a tab that has metadata even if text is empty', () => {
			// Set metadata on the initial empty tab (no text, but has a project)
			forgeSession.updateDraft({ project: 'My Project' });
			expect(forgeSession.draft.text).toBe('');
			expect(forgeSession.tabs.length).toBe(1);

			const tab = forgeSession.ensureTab();
			expect(tab).not.toBeNull();
			// Should create a new tab, not reuse the one with metadata
			expect(forgeSession.tabs.length).toBe(2);
		});

		it('reuses any empty tab, not just the active one', () => {
			// Create a second tab with content, then put content in the first
			vi.useFakeTimers();
			forgeSession.updateDraft({ text: 'tab 1 content' });
			vi.advanceTimersByTime(250);
			forgeSession.createTab(); // Tab 2 — empty
			vi.advanceTimersByTime(250);
			forgeSession.createTab(); // Tab 3
			forgeSession.updateDraft({ text: 'tab 3 content' });
			vi.useRealTimers();

			expect(forgeSession.tabs.length).toBe(3);

			// ensureTab should find the empty Tab 2
			const tab = forgeSession.ensureTab();
			expect(tab).not.toBeNull();
			expect(forgeSession.tabs.length).toBe(3); // No new tab created
			expect(tab!.name).toBe('Untitled 2');
		});
	});

	describe('reiterate sourceAction', () => {
		it('accepts reiterate sourceAction', () => {
			forgeSession.loadRequest({
				text: 'text',
				sourceAction: 'reiterate',
			});
			expect(forgeSession.draft.sourceAction).toBe('reiterate');
		});
	});

	describe('per-tab state', () => {
		it('createInitialTab includes resultId: null and mode: compose', () => {
			expect(forgeSession.activeTab.resultId).toBeNull();
			expect(forgeSession.activeTab.mode).toBe('compose');
		});

		it('loadRequest creates new tab with resultId: null and mode: compose', () => {
			forgeSession.loadRequest({ text: 'first tab content' });
			forgeSession.loadRequest({ text: 'second tab content', title: 'Second' });

			const newTab = forgeSession.tabs.find(t => t.draft.text === 'second tab content');
			expect(newTab).toBeDefined();
			expect(newTab!.resultId).toBeNull();
			expect(newTab!.mode).toBe('compose');
		});

		it('hydration resets forging mode to compose', () => {
			storageMap.set('pf_forge_draft', JSON.stringify({
				tabs: [{
					id: 'tab-1',
					name: 'Forging Tab',
					draft: { text: 'test' },
					resultId: 'res-1',
					mode: 'forging',
				}],
				activeTabId: 'tab-1',
			}));

			forgeSession._hydrateFromStorage();
			expect(forgeSession.activeTab.mode).toBe('compose');
			expect(forgeSession.activeTab.resultId).toBe('res-1');
		});

		it('hydration preserves review mode with resultId', () => {
			storageMap.set('pf_forge_draft', JSON.stringify({
				tabs: [{
					id: 'tab-2',
					name: 'Review Tab',
					draft: { text: 'test' },
					resultId: 'res-2',
					mode: 'review',
				}],
				activeTabId: 'tab-2',
			}));

			forgeSession._hydrateFromStorage();
			expect(forgeSession.activeTab.mode).toBe('review');
			expect(forgeSession.activeTab.resultId).toBe('res-2');
		});

		it('hydration defaults missing resultId and mode fields', () => {
			storageMap.set('pf_forge_draft', JSON.stringify({
				tabs: [{
					id: 'tab-3',
					name: 'Old Tab',
					draft: { text: 'legacy' },
					// no resultId or mode
				}],
				activeTabId: 'tab-3',
			}));

			forgeSession._hydrateFromStorage();
			expect(forgeSession.activeTab.resultId).toBeNull();
			expect(forgeSession.activeTab.mode).toBe('compose');
		});
	});
});
