import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createFolderDescriptor, createPromptDescriptor } from '$lib/utils/fileDescriptor';

// Mock API client
vi.mock('$lib/api/client', () => ({
	fetchFsChildren: vi.fn(),
	fetchFsPath: vi.fn(),
	fetchFsTree: vi.fn(),
	moveFsNode: vi.fn(),
	createProject: vi.fn(),
	updateProject: vi.fn(),
	deleteProject: vi.fn(),
}));

// Mock system bus
vi.mock('$lib/services/systemBus.svelte', () => ({
	systemBus: { emit: vi.fn(), on: vi.fn(() => () => {}) },
}));

import { fsOrchestrator } from './filesystemOrchestrator.svelte';
import {
	fetchFsChildren,
	moveFsNode,
	createProject,
	deleteProject,
} from '$lib/api/client';
import { systemBus } from '$lib/services/systemBus.svelte';

const mockFetchFsChildren = vi.mocked(fetchFsChildren);
const mockMoveFsNode = vi.mocked(moveFsNode);
const mockCreateProject = vi.mocked(createProject);
const mockDeleteProject = vi.mocked(deleteProject);

beforeEach(() => {
	vi.clearAllMocks();
	fsOrchestrator.invalidateAll();
});

describe('loadChildren / getChildren', () => {
	it('fetches and caches root children', async () => {
		const nodes = [
			{ id: 'f1', name: 'Folder 1', type: 'folder' as const, parent_id: null, depth: 0 },
		];
		mockFetchFsChildren.mockResolvedValue({ nodes, path: [] });

		const result = await fsOrchestrator.loadChildren(null);
		expect(result).toEqual(nodes);
		expect(fsOrchestrator.getChildren(null)).toEqual(nodes);
		expect(fsOrchestrator.rootFolders).toEqual(nodes);
	});

	it('returns empty array from cache when not loaded', () => {
		expect(fsOrchestrator.getChildren('some-id')).toEqual([]);
	});
});

describe('invalidation', () => {
	it('invalidate clears specific entry', async () => {
		mockFetchFsChildren.mockResolvedValue({ nodes: [{ id: 'x', name: 'X', type: 'folder', parent_id: null, depth: 0 }], path: [] });
		await fsOrchestrator.loadChildren(null);
		expect(fsOrchestrator.getChildren(null)).toHaveLength(1);

		fsOrchestrator.invalidate(null);
		expect(fsOrchestrator.getChildren(null)).toEqual([]);
	});

	it('invalidateAll clears all entries', async () => {
		mockFetchFsChildren.mockResolvedValue({ nodes: [{ id: 'a', name: 'A', type: 'folder', parent_id: null, depth: 0 }], path: [] });
		await fsOrchestrator.loadChildren(null);

		mockFetchFsChildren.mockResolvedValue({ nodes: [{ id: 'b', name: 'B', type: 'folder', parent_id: 'a', depth: 1 }], path: [] });
		await fsOrchestrator.loadChildren('a');

		fsOrchestrator.invalidateAll();
		expect(fsOrchestrator.getChildren(null)).toEqual([]);
		expect(fsOrchestrator.getChildren('a')).toEqual([]);
	});
});

describe('move', () => {
	it('invalidates source and destination caches on success', async () => {
		// Pre-populate caches
		mockFetchFsChildren.mockResolvedValue({ nodes: [{ id: 'item', name: 'Item', type: 'folder', parent_id: null, depth: 0 }], path: [] });
		await fsOrchestrator.loadChildren(null);

		mockMoveFsNode.mockResolvedValue({ success: true });

		const result = await fsOrchestrator.move('project', 'item', 'target-id');
		expect(result).toBe(true);
		// Source (root) cache should be invalidated
		expect(fsOrchestrator.getChildren(null)).toEqual([]);
		expect(systemBus.emit).toHaveBeenCalledWith('fs:moved', 'fsOrchestrator', expect.any(Object));
	});

	it('returns false on failure', async () => {
		mockMoveFsNode.mockResolvedValue({ success: false });
		const result = await fsOrchestrator.move('project', 'x', 'y');
		expect(result).toBe(false);
	});
});

describe('createFolder', () => {
	it('returns node and emits event on success', async () => {
		mockCreateProject.mockResolvedValue({
			id: 'new-id', name: 'New Folder', description: null,
			context_profile: null, status: 'active', parent_id: null, depth: 0,
			created_at: '2026-01-01', updated_at: '2026-01-01', prompts: [],
		});

		const node = await fsOrchestrator.createFolder('New Folder', null);
		expect(node).not.toBeNull();
		expect(node!.id).toBe('new-id');
		expect(systemBus.emit).toHaveBeenCalledWith('fs:created', 'fsOrchestrator', expect.any(Object));
	});
});

describe('deleteFolder', () => {
	it('invalidates parent cache and emits event', async () => {
		mockDeleteProject.mockResolvedValue(true);
		const result = await fsOrchestrator.deleteFolder('some-id');
		expect(result).toBe(true);
		expect(systemBus.emit).toHaveBeenCalledWith('fs:deleted', 'fsOrchestrator', { id: 'some-id' });
	});
});

describe('validateDrop', () => {
	it('rejects self-nesting', () => {
		const folder = createFolderDescriptor('f1', 'Folder', null, 0);
		const result = fsOrchestrator.validateDrop(folder, 'f1');
		expect(result.allowed).toBe(false);
		expect(result.reason).toContain('itself');
	});

	it('rejects depth > MAX_FOLDER_DEPTH', () => {
		const folder = createFolderDescriptor('f1', 'Folder', null, 0);
		const result = fsOrchestrator.validateDrop(folder, 'deep-target', 8);
		expect(result.allowed).toBe(false);
		expect(result.reason).toContain('depth');
	});

	it('allows valid folder-to-folder drop', () => {
		const folder = createFolderDescriptor('f1', 'Folder', null, 0);
		const result = fsOrchestrator.validateDrop(folder, 'f2', 2);
		expect(result.allowed).toBe(true);
	});

	it('allows prompt-to-folder drop', () => {
		const prompt = createPromptDescriptor('p1', 'proj1', 'Test');
		const result = fsOrchestrator.validateDrop(prompt, 'f1', 0);
		expect(result.allowed).toBe(true);
	});

	it('allows drop to desktop (null target)', () => {
		const folder = createFolderDescriptor('f1', 'Folder', 'parent', 1);
		const result = fsOrchestrator.validateDrop(folder, null);
		expect(result.allowed).toBe(true);
	});
});
