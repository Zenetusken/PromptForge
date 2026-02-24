import { describe, it, expect, beforeEach, vi } from 'vitest';

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

	describe('reiterate sourceAction', () => {
		it('accepts reiterate sourceAction', () => {
			forgeSession.loadRequest({
				text: 'text',
				sourceAction: 'reiterate',
			});
			expect(forgeSession.draft.sourceAction).toBe('reiterate');
		});
	});
});
