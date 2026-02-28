import { describe, it, expect } from 'vitest';
import {
	createPromptDescriptor,
	createArtifactDescriptor,
	createSubArtifactDescriptor,
	createFolderDescriptor,
	isPromptDescriptor,
	isArtifactDescriptor,
	isTemplateDescriptor,
	isSubArtifactDescriptor,
	isFolderDescriptor,
	descriptorsMatch,
	FILE_DESCRIPTOR_KINDS,
	type FileDescriptor,
	type NodeDescriptor,
} from './fileDescriptor';

describe('createPromptDescriptor', () => {
	it('creates a prompt descriptor with defaults', () => {
		const d = createPromptDescriptor('p-1', 'proj-1', 'My Prompt');
		expect(d.kind).toBe('prompt');
		expect(d.id).toBe('p-1');
		expect(d.projectId).toBe('proj-1');
		expect(d.name).toBe('My Prompt');
		expect(d.extension).toBe('.md');
	});

	it('accepts custom extension', () => {
		const d = createPromptDescriptor('p-1', 'proj-1', 'Template', '.tmpl');
		expect(d.extension).toBe('.tmpl');
	});
});

describe('createArtifactDescriptor', () => {
	it('creates a forge-result artifact by default', () => {
		const d = createArtifactDescriptor('opt-1', 'Result 8/10');
		expect(d.kind).toBe('artifact');
		expect(d.id).toBe('opt-1');
		expect(d.artifactKind).toBe('forge-result');
		expect(d.name).toBe('Result 8/10');
		expect(d.sourcePromptId).toBeNull();
		expect(d.sourceProjectId).toBeNull();
	});

	it('accepts source linking', () => {
		const d = createArtifactDescriptor('opt-1', 'Result', {
			sourcePromptId: 'p-1',
			sourceProjectId: 'proj-1',
		});
		expect(d.sourcePromptId).toBe('p-1');
		expect(d.sourceProjectId).toBe('proj-1');
	});
});

describe('createSubArtifactDescriptor', () => {
	it('creates a sub-artifact for forge-analysis', () => {
		const d = createSubArtifactDescriptor('forge-1', 'forge-analysis');
		expect(d.kind).toBe('sub-artifact');
		expect(d.id).toBe('forge-1');
		expect(d.parentForgeId).toBe('forge-1');
		expect(d.artifactKind).toBe('forge-analysis');
		expect(d.name).toBe('analysis.scan');
		expect(d.extension).toBe('.scan');
	});

	it('creates a sub-artifact for forge-scores', () => {
		const d = createSubArtifactDescriptor('forge-2', 'forge-scores');
		expect(d.kind).toBe('sub-artifact');
		expect(d.artifactKind).toBe('forge-scores');
		expect(d.name).toBe('scores.val');
		expect(d.extension).toBe('.val');
	});

	it('creates a sub-artifact for forge-strategy', () => {
		const d = createSubArtifactDescriptor('forge-3', 'forge-strategy');
		expect(d.kind).toBe('sub-artifact');
		expect(d.artifactKind).toBe('forge-strategy');
		expect(d.name).toBe('strategy.strat');
		expect(d.extension).toBe('.strat');
	});

	it('accepts custom name', () => {
		const d = createSubArtifactDescriptor('forge-1', 'forge-analysis', 'custom-name.scan');
		expect(d.name).toBe('custom-name.scan');
	});

	it('uses parentForgeId as id', () => {
		const d = createSubArtifactDescriptor('parent-123', 'forge-scores');
		expect(d.id).toBe('parent-123');
		expect(d.parentForgeId).toBe('parent-123');
	});
});

describe('type guards', () => {
	const prompt = createPromptDescriptor('p-1', 'proj-1', 'Test');
	const artifact = createArtifactDescriptor('opt-1', 'Result');
	const template: FileDescriptor = {
		kind: 'template',
		id: 't-1',
		name: 'Template',
		extension: '.tmpl',
		category: 'coding',
	};
	const subArtifact = createSubArtifactDescriptor('forge-1', 'forge-analysis');

	it('isPromptDescriptor identifies prompts', () => {
		expect(isPromptDescriptor(prompt)).toBe(true);
		expect(isPromptDescriptor(artifact)).toBe(false);
		expect(isPromptDescriptor(template)).toBe(false);
		expect(isPromptDescriptor(subArtifact)).toBe(false);
	});

	it('isArtifactDescriptor identifies artifacts', () => {
		expect(isArtifactDescriptor(artifact)).toBe(true);
		expect(isArtifactDescriptor(prompt)).toBe(false);
		expect(isArtifactDescriptor(subArtifact)).toBe(false);
	});

	it('isTemplateDescriptor identifies templates', () => {
		expect(isTemplateDescriptor(template)).toBe(true);
		expect(isTemplateDescriptor(prompt)).toBe(false);
		expect(isTemplateDescriptor(subArtifact)).toBe(false);
	});

	it('isSubArtifactDescriptor identifies sub-artifacts', () => {
		expect(isSubArtifactDescriptor(subArtifact)).toBe(true);
		expect(isSubArtifactDescriptor(prompt)).toBe(false);
		expect(isSubArtifactDescriptor(artifact)).toBe(false);
		expect(isSubArtifactDescriptor(template)).toBe(false);
	});
});

describe('FILE_DESCRIPTOR_KINDS', () => {
	it('includes sub-artifact', () => {
		expect(FILE_DESCRIPTOR_KINDS).toContain('sub-artifact');
	});

	it('includes all 4 file kinds', () => {
		expect(FILE_DESCRIPTOR_KINDS).toContain('prompt');
		expect(FILE_DESCRIPTOR_KINDS).toContain('artifact');
		expect(FILE_DESCRIPTOR_KINDS).toContain('template');
		expect(FILE_DESCRIPTOR_KINDS).toContain('sub-artifact');
		expect(FILE_DESCRIPTOR_KINDS).toHaveLength(4);
	});
});

describe('createFolderDescriptor', () => {
	it('creates a folder descriptor with defaults', () => {
		const d = createFolderDescriptor('f-1', 'My Folder');
		expect(d.kind).toBe('folder');
		expect(d.id).toBe('f-1');
		expect(d.name).toBe('My Folder');
		expect(d.parentId).toBeNull();
		expect(d.depth).toBe(0);
	});

	it('accepts parentId and depth', () => {
		const d = createFolderDescriptor('f-2', 'Sub', 'f-1', 3);
		expect(d.parentId).toBe('f-1');
		expect(d.depth).toBe(3);
	});
});

describe('isFolderDescriptor', () => {
	it('identifies folder descriptors', () => {
		const folder = createFolderDescriptor('f-1', 'Folder');
		const prompt = createPromptDescriptor('p-1', 'proj-1', 'Test');
		expect(isFolderDescriptor(folder)).toBe(true);
		expect(isFolderDescriptor(prompt)).toBe(false);
	});
});

describe('descriptorsMatch', () => {
	it('returns true for same prompt ID', () => {
		const a = createPromptDescriptor('p-1', 'proj-1', 'A');
		const b = createPromptDescriptor('p-1', 'proj-2', 'B');
		expect(descriptorsMatch(a, b)).toBe(true);
	});

	it('returns false for different prompt IDs', () => {
		const a = createPromptDescriptor('p-1', 'proj-1', 'A');
		const b = createPromptDescriptor('p-2', 'proj-1', 'B');
		expect(descriptorsMatch(a, b)).toBe(false);
	});

	it('returns false for cross-kind (prompt vs artifact with same ID)', () => {
		const prompt = createPromptDescriptor('id-1', 'proj-1', 'A');
		const artifact = createArtifactDescriptor('id-1', 'A');
		expect(descriptorsMatch(prompt, artifact)).toBe(false);
	});

	it('returns true for same sub-artifact (parentForgeId + artifactKind)', () => {
		const a = createSubArtifactDescriptor('forge-1', 'forge-analysis');
		const b = createSubArtifactDescriptor('forge-1', 'forge-analysis', 'custom-name.scan');
		expect(descriptorsMatch(a, b)).toBe(true);
	});

	it('returns false for different sub-artifact kinds on same parent', () => {
		const a = createSubArtifactDescriptor('forge-1', 'forge-analysis');
		const b = createSubArtifactDescriptor('forge-1', 'forge-scores');
		expect(descriptorsMatch(a, b)).toBe(false);
	});
});
