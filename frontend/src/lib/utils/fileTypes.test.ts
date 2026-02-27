import { describe, it, expect } from 'vitest';
import {
	toFilename,
	TYPE_SORT_ORDER,
	FILE_EXTENSIONS,
	DEFAULT_EXTENSION,
	ARTIFACT_KINDS,
	ARTIFACT_EXTENSION_MAP,
	toArtifactName,
	toForgeFilename,
	toSubArtifactFilename,
	type FileExtension,
	type ArtifactKind,
} from './fileTypes';

describe('toFilename', () => {
	it('uses title when provided', () => {
		expect(toFilename('some content', 'My Prompt')).toBe('My Prompt.md');
	});

	it('does not double the extension if title already has .md', () => {
		expect(toFilename('content', 'My Prompt.md')).toBe('My Prompt.md');
	});

	it('handles .MD case-insensitively', () => {
		expect(toFilename('content', 'My Prompt.MD')).toBe('My Prompt.MD');
	});

	it('derives filename from content when no title', () => {
		expect(toFilename('Short prompt text')).toBe('Short prompt text.md');
	});

	it('derives filename from content when title is null', () => {
		expect(toFilename('Short prompt text', null)).toBe('Short prompt text.md');
	});

	it('derives filename from content when title is empty', () => {
		expect(toFilename('Short prompt text', '')).toBe('Short prompt text.md');
	});

	it('derives filename from content when title is whitespace', () => {
		expect(toFilename('Short prompt text', '   ')).toBe('Short prompt text.md');
	});

	it('returns Untitled.md for empty content', () => {
		expect(toFilename('')).toBe('Untitled.md');
	});

	it('returns Untitled.md for whitespace-only content', () => {
		expect(toFilename('   ')).toBe('Untitled.md');
	});

	it('returns Untitled.md for empty content and empty title', () => {
		expect(toFilename('', '')).toBe('Untitled.md');
	});

	it('returns full content + .md for content <= 40 chars', () => {
		const content = 'Exactly forty characters long text here!';
		expect(content.length).toBe(40);
		expect(toFilename(content)).toBe('Exactly forty characters long text here!.md');
	});

	it('truncates long content at word boundary', () => {
		const content = 'Review this Python function for correctness and performance issues';
		const result = toFilename(content);
		expect(result).toMatch(/\.md$/);
		expect(result).toContain('...');
		// Should be reasonably short
		expect(result.length).toBeLessThan(50);
	});

	it('truncates long title with .md already present', () => {
		const title = 'This is a very long title that exceeds forty four characters limit by a lot.md';
		const result = toFilename('content', title);
		expect(result).toMatch(/\.md$/);
		expect(result).toContain('...');
	});

	it('handles single long word without spaces', () => {
		const content = 'abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJ';
		const result = toFilename(content);
		expect(result).toMatch(/\.md$/);
		expect(result).toContain('...');
	});
});

describe('TYPE_SORT_ORDER', () => {
	it('orders system < folder < shortcut < file', () => {
		expect(TYPE_SORT_ORDER['system']).toBeLessThan(TYPE_SORT_ORDER['folder']);
		expect(TYPE_SORT_ORDER['folder']).toBeLessThan(TYPE_SORT_ORDER['shortcut']);
		expect(TYPE_SORT_ORDER['shortcut']).toBeLessThan(TYPE_SORT_ORDER['file']);
	});

	it('treats prompt same weight as file', () => {
		expect(TYPE_SORT_ORDER['prompt']).toBe(TYPE_SORT_ORDER['file']);
	});
});

describe('FILE_EXTENSIONS', () => {
	it('defines .md extension with full metadata', () => {
		expect(FILE_EXTENSIONS['.md']).toBeDefined();
		expect(FILE_EXTENSIONS['.md'].icon).toBe('file-text');
		expect(FILE_EXTENSIONS['.md'].editable).toBe(true);
		expect(FILE_EXTENSIONS['.md'].versionable).toBe(true);
	});

	it('defines .tmpl extension', () => {
		expect(FILE_EXTENSIONS['.tmpl']).toBeDefined();
		expect(FILE_EXTENSIONS['.tmpl'].icon).toBe('file-code');
		expect(FILE_EXTENSIONS['.tmpl'].editable).toBe(false);
	});

	it('defines .forge extension', () => {
		expect(FILE_EXTENSIONS['.forge']).toBeDefined();
		expect(FILE_EXTENSIONS['.forge'].icon).toBe('zap');
		expect(FILE_EXTENSIONS['.forge'].color).toBe('purple');
		expect(FILE_EXTENSIONS['.forge'].editable).toBe(false);
		expect(FILE_EXTENSIONS['.forge'].versionable).toBe(false);
	});

	it('defines .scan extension', () => {
		expect(FILE_EXTENSIONS['.scan']).toBeDefined();
		expect(FILE_EXTENSIONS['.scan'].icon).toBe('search');
		expect(FILE_EXTENSIONS['.scan'].color).toBe('green');
		expect(FILE_EXTENSIONS['.scan'].editable).toBe(false);
	});

	it('defines .val extension', () => {
		expect(FILE_EXTENSIONS['.val']).toBeDefined();
		expect(FILE_EXTENSIONS['.val'].icon).toBe('activity');
		expect(FILE_EXTENSIONS['.val'].color).toBe('yellow');
		expect(FILE_EXTENSIONS['.val'].editable).toBe(false);
	});

	it('defines .strat extension', () => {
		expect(FILE_EXTENSIONS['.strat']).toBeDefined();
		expect(FILE_EXTENSIONS['.strat'].icon).toBe('sliders');
		expect(FILE_EXTENSIONS['.strat'].color).toBe('indigo');
		expect(FILE_EXTENSIONS['.strat'].editable).toBe(false);
	});

	it('defines .app extension', () => {
		expect(FILE_EXTENSIONS['.app']).toBeDefined();
		expect(FILE_EXTENSIONS['.app'].icon).toBe('monitor');
		expect(FILE_EXTENSIONS['.app'].editable).toBe(false);
	});

	it('defines .lnk extension', () => {
		expect(FILE_EXTENSIONS['.lnk']).toBeDefined();
		expect(FILE_EXTENSIONS['.lnk'].icon).toBe('link');
		expect(FILE_EXTENSIONS['.lnk'].color).toBe('blue');
		expect(FILE_EXTENSIONS['.lnk'].editable).toBe(false);
	});

	it('has metadata for all FileExtension values', () => {
		const allExtensions: FileExtension[] = ['.md', '.forge', '.scan', '.val', '.strat', '.tmpl', '.app', '.lnk'];
		for (const ext of allExtensions) {
			expect(FILE_EXTENSIONS[ext]).toBeDefined();
			expect(FILE_EXTENSIONS[ext].label).toBeTruthy();
			expect(FILE_EXTENSIONS[ext].icon).toBeTruthy();
			expect(FILE_EXTENSIONS[ext].color).toBeTruthy();
		}
	});
});

describe('DEFAULT_EXTENSION', () => {
	it('is .md', () => {
		expect(DEFAULT_EXTENSION).toBe('.md');
	});
});

describe('ARTIFACT_KINDS', () => {
	it('defines forge-result kind', () => {
		expect(ARTIFACT_KINDS['forge-result']).toBeDefined();
		expect(ARTIFACT_KINDS['forge-result'].icon).toBe('zap');
		expect(ARTIFACT_KINDS['forge-result'].color).toBe('purple');
	});

	it('defines forge-analysis kind', () => {
		expect(ARTIFACT_KINDS['forge-analysis']).toBeDefined();
		expect(ARTIFACT_KINDS['forge-analysis'].icon).toBe('search');
		expect(ARTIFACT_KINDS['forge-analysis'].color).toBe('green');
	});

	it('defines forge-scores kind', () => {
		expect(ARTIFACT_KINDS['forge-scores']).toBeDefined();
		expect(ARTIFACT_KINDS['forge-scores'].icon).toBe('activity');
		expect(ARTIFACT_KINDS['forge-scores'].color).toBe('yellow');
	});

	it('defines forge-strategy kind', () => {
		expect(ARTIFACT_KINDS['forge-strategy']).toBeDefined();
		expect(ARTIFACT_KINDS['forge-strategy'].icon).toBe('sliders');
		expect(ARTIFACT_KINDS['forge-strategy'].color).toBe('indigo');
	});

	it('has metadata for all ArtifactKind values', () => {
		const allKinds: ArtifactKind[] = ['forge-result', 'forge-analysis', 'forge-scores', 'forge-strategy'];
		for (const kind of allKinds) {
			expect(ARTIFACT_KINDS[kind]).toBeDefined();
			expect(ARTIFACT_KINDS[kind].label).toBeTruthy();
			expect(ARTIFACT_KINDS[kind].icon).toBeTruthy();
			expect(ARTIFACT_KINDS[kind].color).toBeTruthy();
		}
	});
});

describe('ARTIFACT_EXTENSION_MAP', () => {
	it('maps forge-result to .forge', () => {
		expect(ARTIFACT_EXTENSION_MAP['forge-result']).toBe('.forge');
	});

	it('maps forge-analysis to .scan', () => {
		expect(ARTIFACT_EXTENSION_MAP['forge-analysis']).toBe('.scan');
	});

	it('maps forge-scores to .val', () => {
		expect(ARTIFACT_EXTENSION_MAP['forge-scores']).toBe('.val');
	});

	it('maps forge-strategy to .strat', () => {
		expect(ARTIFACT_EXTENSION_MAP['forge-strategy']).toBe('.strat');
	});

	it('has an entry for every ArtifactKind', () => {
		const allKinds: ArtifactKind[] = ['forge-result', 'forge-analysis', 'forge-scores', 'forge-strategy'];
		for (const kind of allKinds) {
			expect(ARTIFACT_EXTENSION_MAP[kind]).toBeDefined();
			// Verify the extension exists in FILE_EXTENSIONS
			expect(FILE_EXTENSIONS[ARTIFACT_EXTENSION_MAP[kind]]).toBeDefined();
		}
	});
});

describe('toArtifactName', () => {
	it('uses title when provided', () => {
		expect(toArtifactName('My Result')).toBe('My Result');
	});

	it('uses score when no title', () => {
		expect(toArtifactName(null, 0.8)).toBe('Forge Result (8/10)');
	});

	it('rounds score correctly', () => {
		expect(toArtifactName(null, 0.75)).toBe('Forge Result (8/10)');
	});

	it('returns default when neither title nor score', () => {
		expect(toArtifactName()).toBe('Forge Result');
	});

	it('returns default for empty title and zero score', () => {
		expect(toArtifactName('', 0)).toBe('Forge Result');
	});

	it('prefers title over score', () => {
		expect(toArtifactName('Custom Title', 0.9)).toBe('Custom Title');
	});
});

describe('toForgeFilename', () => {
	it('uses title with .forge extension', () => {
		expect(toForgeFilename('My Result')).toBe('My Result.forge');
	});

	it('uses score when no title', () => {
		expect(toForgeFilename(null, 0.8)).toBe('Forge Result (8/10).forge');
	});

	it('returns default .forge for no title or score', () => {
		expect(toForgeFilename()).toBe('Forge Result.forge');
	});

	it('appends version when provided', () => {
		expect(toForgeFilename('My Result', null, 'v2')).toBe('My Result v2.forge');
	});

	it('appends version with score fallback', () => {
		expect(toForgeFilename(null, 0.9, 'v3')).toBe('Forge Result (9/10) v3.forge');
	});

	it('trims whitespace-only version', () => {
		expect(toForgeFilename('My Result', null, '  ')).toBe('My Result.forge');
	});

	it('handles null version', () => {
		expect(toForgeFilename('My Result', 0.5, null)).toBe('My Result.forge');
	});
});

describe('toSubArtifactFilename', () => {
	it('returns analysis.scan for forge-analysis', () => {
		expect(toSubArtifactFilename('forge-analysis')).toBe('analysis.scan');
	});

	it('returns scores.val for forge-scores', () => {
		expect(toSubArtifactFilename('forge-scores')).toBe('scores.val');
	});

	it('returns strategy.strat for forge-strategy', () => {
		expect(toSubArtifactFilename('forge-strategy')).toBe('strategy.strat');
	});

	it('returns result with extension for forge-result', () => {
		expect(toSubArtifactFilename('forge-result')).toBe('result.forge');
	});
});
