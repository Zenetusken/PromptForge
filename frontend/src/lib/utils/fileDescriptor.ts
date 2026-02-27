import type { FileExtension, ArtifactKind } from './fileTypes';
import { ARTIFACT_EXTENSION_MAP, toSubArtifactFilename } from './fileTypes';

/** Valid FileDescriptor kind values for hydration validation. */
export const FILE_DESCRIPTOR_KINDS = ['prompt', 'artifact', 'template', 'sub-artifact'] as const;

/** All valid node descriptor kinds (files + folders). */
export const NODE_DESCRIPTOR_KINDS = ['prompt', 'artifact', 'template', 'sub-artifact', 'folder'] as const;

// ── Discriminated union — the core abstraction ──

export interface PromptDescriptor {
	readonly kind: 'prompt';
	readonly id: string;
	readonly projectId: string;
	readonly name: string;
	readonly extension: FileExtension;
}

export interface ArtifactDescriptor {
	readonly kind: 'artifact';
	readonly id: string;
	readonly artifactKind: ArtifactKind;
	readonly name: string;
	readonly sourcePromptId: string | null;
	readonly sourceProjectId: string | null;
}

export interface TemplateDescriptor {
	readonly kind: 'template';
	readonly id: string;
	readonly name: string;
	readonly extension: '.tmpl';
	readonly category: string;
}

export interface SubArtifactDescriptor {
	readonly kind: 'sub-artifact';
	readonly id: string;
	readonly artifactKind: ArtifactKind;
	readonly name: string;
	readonly parentForgeId: string;
	readonly extension: FileExtension;
}

export type FileDescriptor = PromptDescriptor | ArtifactDescriptor | TemplateDescriptor | SubArtifactDescriptor;

export interface FolderDescriptor {
	readonly kind: 'folder';
	readonly id: string;
	readonly name: string;
	readonly parentId: string | null;
	readonly depth: number;
}

/** A node in the filesystem — either a file (prompt/artifact/template/sub-artifact) or a folder. */
export type NodeDescriptor = FileDescriptor | FolderDescriptor;

// ── Factory helpers ──

export function createPromptDescriptor(
	id: string,
	projectId: string,
	name: string,
	extension: FileExtension = '.md',
): PromptDescriptor {
	return { kind: 'prompt', id, projectId, name, extension };
}

export function createArtifactDescriptor(
	id: string,
	name: string,
	opts?: { artifactKind?: ArtifactKind; sourcePromptId?: string | null; sourceProjectId?: string | null },
): ArtifactDescriptor {
	return {
		kind: 'artifact',
		id,
		artifactKind: opts?.artifactKind ?? 'forge-result',
		name,
		sourcePromptId: opts?.sourcePromptId ?? null,
		sourceProjectId: opts?.sourceProjectId ?? null,
	};
}

export function createSubArtifactDescriptor(
	parentForgeId: string,
	artifactKind: ArtifactKind,
	name?: string,
): SubArtifactDescriptor {
	return {
		kind: 'sub-artifact',
		id: parentForgeId,
		artifactKind,
		name: name ?? toSubArtifactFilename(artifactKind),
		parentForgeId,
		extension: ARTIFACT_EXTENSION_MAP[artifactKind],
	};
}

export function createFolderDescriptor(
	id: string,
	name: string,
	parentId: string | null = null,
	depth: number = 0,
): FolderDescriptor {
	return { kind: 'folder', id, name, parentId, depth };
}

// ── Type guards ──

export function isPromptDescriptor(d: FileDescriptor): d is PromptDescriptor {
	return d.kind === 'prompt';
}

export function isArtifactDescriptor(d: FileDescriptor): d is ArtifactDescriptor {
	return d.kind === 'artifact';
}

export function isTemplateDescriptor(d: FileDescriptor): d is TemplateDescriptor {
	return d.kind === 'template';
}

export function isSubArtifactDescriptor(d: FileDescriptor): d is SubArtifactDescriptor {
	return d.kind === 'sub-artifact';
}

export function isFolderDescriptor(d: NodeDescriptor): d is FolderDescriptor {
	return d.kind === 'folder';
}
