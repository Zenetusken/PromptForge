/**
 * Filesystem Orchestrator — manages hierarchical folder state and operations.
 *
 * Provides caching, mutation methods, and drop validation for the
 * folder-based filesystem. All filesystem API calls go through this store.
 */

import {
	fetchFsChildren,
	fetchFsPath,
	fetchFsTree,
	moveFsNode,
	createProject,
	updateProject,
	deleteProject,
	deletePromptDirect,
	type FsNode,
	type PathSegment,
} from '$lib/api/client';
import type { NodeDescriptor } from '$lib/utils/fileDescriptor';
import { isFolderDescriptor } from '$lib/utils/fileDescriptor';
import { systemBus } from '$lib/services/systemBus.svelte';

const MAX_FOLDER_DEPTH = 8;

/** Cache key for root-level children. */
const ROOT_KEY = '__root__';

export interface DropValidation {
	allowed: boolean;
	reason?: string;
}

function cacheKey(parentId: string | null): string {
	return parentId ?? ROOT_KEY;
}

class FilesystemOrchestratorState {
	// --- Reactive state ---
	private _childrenCache = $state(new Map<string, FsNode[]>());
	private _pathCache = $state(new Map<string, PathSegment[]>());
	private _loading = $state(new Set<string>());

	// --- Derived ---

	/** Root-level folders from cache. */
	get rootFolders(): FsNode[] {
		return this._childrenCache.get(ROOT_KEY) ?? [];
	}

	/** Check if a specific parent is currently loading. */
	isLoading(parentId: string | null): boolean {
		return this._loading.has(cacheKey(parentId));
	}

	// --- Queries ---

	/** Get cached children for a parent (returns empty if not loaded). */
	getChildren(parentId: string | null): FsNode[] {
		return this._childrenCache.get(cacheKey(parentId)) ?? [];
	}

	/** Fetch children from server and cache them. */
	async loadChildren(parentId: string | null): Promise<FsNode[]> {
		const key = cacheKey(parentId);
		this._loading.add(key);
		try {
			const resp = await fetchFsChildren(parentId);
			this._childrenCache.set(key, resp.nodes);
			if (resp.path.length > 0 && parentId) {
				this._pathCache.set(parentId, resp.path);
			}
			return resp.nodes;
		} finally {
			this._loading.delete(key);
		}
	}

	/** Get the breadcrumb path for a folder. */
	async getPath(projectId: string): Promise<PathSegment[]> {
		const cached = this._pathCache.get(projectId);
		if (cached) return cached;
		const segments = await fetchFsPath(projectId);
		this._pathCache.set(projectId, segments);
		return segments;
	}

	/** Get the full recursive tree from a root. */
	async loadTree(rootId?: string | null): Promise<FsNode[]> {
		return fetchFsTree(rootId);
	}

	// --- Mutations ---

	/** Create a new folder. */
	async createFolder(
		name: string,
		parentId: string | null,
	): Promise<FsNode | null> {
		try {
			const result = await createProject({ name, parent_id: parentId });
			if (!result) return null;
			const node: FsNode = {
				id: result.id,
				name: result.name,
				type: 'folder',
				parent_id: result.parent_id ?? null,
				depth: result.depth,
				created_at: result.created_at,
				updated_at: result.updated_at,
			};
			this.invalidate(parentId);
			systemBus.emit('fs:created', 'fsOrchestrator', { node });
			return node;
		} catch (err) {
			systemBus.emit('notification:show', 'fsOrchestrator', {
				type: 'error',
				title: 'Create folder failed',
				message: err instanceof Error ? err.message : 'Could not create folder',
			});
			return null;
		}
	}

	/** Move a folder or prompt to a new parent. */
	async move(
		type: 'project' | 'prompt',
		id: string,
		newParentId: string | null,
	): Promise<boolean> {
		const oldParentId = this._findParentOf(id);
		try {
			const result = await moveFsNode(type, id, newParentId);
			if (!result.success) return false;
			this.invalidate(oldParentId);
			if (oldParentId !== newParentId) {
				this.invalidate(newParentId);
			}
			systemBus.emit('fs:moved', 'fsOrchestrator', { type, id, newParentId });
			return true;
		} catch (err) {
			systemBus.emit('notification:show', 'fsOrchestrator', {
				type: 'error',
				title: 'Move failed',
				message: err instanceof Error ? err.message : 'Could not move item',
			});
			return false;
		}
	}

	/** Rename a folder. */
	async renameFolder(id: string, newName: string): Promise<boolean> {
		try {
			const result = await updateProject(id, { name: newName });
			if (!result) return false;
			this.invalidate(result.parent_id ?? null);
			systemBus.emit('fs:renamed', 'fsOrchestrator', { id, newName });
			return true;
		} catch (err) {
			systemBus.emit('notification:show', 'fsOrchestrator', {
				type: 'error',
				title: 'Rename failed',
				message: err instanceof Error ? err.message : 'Could not rename folder',
			});
			return false;
		}
	}

	/** Delete a folder. */
	async deleteFolder(id: string): Promise<boolean> {
		const parentId = this._findParentOf(id);
		try {
			const ok = await deleteProject(id);
			if (!ok) return false;
			this.invalidate(parentId);
			systemBus.emit('fs:deleted', 'fsOrchestrator', { id });
			return true;
		} catch (err) {
			systemBus.emit('notification:show', 'fsOrchestrator', {
				type: 'error',
				title: 'Delete failed',
				message: err instanceof Error ? err.message : 'Could not delete folder',
			});
			return false;
		}
	}

	/** Delete a prompt by ID (works for desktop/orphan prompts). */
	async deletePrompt(id: string): Promise<boolean> {
		const parentId = this._findParentOf(id);
		try {
			const ok = await deletePromptDirect(id);
			if (!ok) return false;
			this.invalidate(parentId);
			systemBus.emit('fs:deleted', 'fsOrchestrator', { id });
			return true;
		} catch (err) {
			systemBus.emit('notification:show', 'fsOrchestrator', {
				type: 'error',
				title: 'Delete failed',
				message: err instanceof Error ? err.message : 'Could not delete prompt',
			});
			return false;
		}
	}

	// --- Drop validation ---

	/** Validate whether a drag payload can be dropped on a target folder. */
	validateDrop(
		dragDescriptor: NodeDescriptor,
		targetId: string | null,
		targetDepth: number = 0,
	): DropValidation {
		// Files can't be drop targets (only folders and desktop/null)
		// (This is checked by the caller — targetId=null means desktop)

		if (isFolderDescriptor(dragDescriptor)) {
			// Can't drop folder on itself
			if (dragDescriptor.id === targetId) {
				return { allowed: false, reason: 'Cannot move folder into itself' };
			}
			// Can't drop on own descendant (would need server check for full validation)
			// Client-side: check depth limit
			if (targetDepth + 1 > MAX_FOLDER_DEPTH) {
				return { allowed: false, reason: 'Maximum folder depth exceeded' };
			}
		}

		// Depth limit for any drag
		if (targetId !== null && targetDepth >= MAX_FOLDER_DEPTH) {
			return { allowed: false, reason: 'Maximum folder depth exceeded' };
		}

		return { allowed: true };
	}

	// --- Cache management ---

	/** Invalidate cache for a specific parent. */
	invalidate(parentId: string | null): void {
		this._childrenCache.delete(cacheKey(parentId));
		if (parentId) this._pathCache.delete(parentId);
	}

	/** Clear all caches. */
	invalidateAll(): void {
		this._childrenCache = new Map();
		this._pathCache = new Map();
	}

	// --- Private helpers ---

	/** Find the parent_id of a node from cached data. */
	private _findParentOf(nodeId: string): string | null {
		for (const [key, nodes] of this._childrenCache) {
			const found = nodes.find((n) => n.id === nodeId);
			if (found) {
				return key === ROOT_KEY ? null : key;
			}
		}
		return null;
	}
}

export const fsOrchestrator = new FilesystemOrchestratorState();
