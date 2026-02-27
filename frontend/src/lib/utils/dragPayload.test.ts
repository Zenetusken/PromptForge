import { describe, it, expect } from 'vitest';
import { encodeDragPayload, decodeDragPayload, DRAG_MIME, type DragPayload } from './dragPayload';
import { createPromptDescriptor, createArtifactDescriptor, createFolderDescriptor } from './fileDescriptor';

describe('DRAG_MIME', () => {
	it('is a valid MIME type string', () => {
		expect(DRAG_MIME).toBe('application/x-promptforge');
	});
});

describe('encodeDragPayload / decodeDragPayload', () => {
	it('round-trips a prompt descriptor', () => {
		const payload: DragPayload = {
			descriptor: createPromptDescriptor('p-1', 'proj-1', 'My Prompt'),
			source: 'projects-window',
		};
		const encoded = encodeDragPayload(payload);
		const decoded = decodeDragPayload(encoded);
		expect(decoded).not.toBeNull();
		expect(decoded!.descriptor.kind).toBe('prompt');
		expect(decoded!.descriptor.id).toBe('p-1');
		expect(decoded!.source).toBe('projects-window');
	});

	it('round-trips an artifact descriptor', () => {
		const payload: DragPayload = {
			descriptor: createArtifactDescriptor('opt-1', 'Result 8/10'),
			source: 'history-window',
		};
		const encoded = encodeDragPayload(payload);
		const decoded = decodeDragPayload(encoded);
		expect(decoded).not.toBeNull();
		expect(decoded!.descriptor.kind).toBe('artifact');
		expect(decoded!.descriptor.id).toBe('opt-1');
		expect(decoded!.source).toBe('history-window');
	});

	it('preserves all artifact descriptor fields', () => {
		const payload: DragPayload = {
			descriptor: createArtifactDescriptor('opt-1', 'Result', {
				sourcePromptId: 'p-1',
				sourceProjectId: 'proj-1',
			}),
			source: 'tab-bar',
		};
		const decoded = decodeDragPayload(encodeDragPayload(payload));
		expect(decoded).not.toBeNull();
		const d = decoded!.descriptor;
		expect(d.kind).toBe('artifact');
		if (d.kind === 'artifact') {
			expect(d.sourcePromptId).toBe('p-1');
			expect(d.sourceProjectId).toBe('proj-1');
			expect(d.artifactKind).toBe('forge-result');
		}
	});

	it('returns null for invalid JSON', () => {
		expect(decodeDragPayload('not json')).toBeNull();
	});

	it('returns null for empty string', () => {
		expect(decodeDragPayload('')).toBeNull();
	});

	it('returns null for object missing descriptor', () => {
		expect(decodeDragPayload(JSON.stringify({ source: 'desktop' }))).toBeNull();
	});

	it('returns null for object missing source', () => {
		expect(decodeDragPayload(JSON.stringify({
			descriptor: { kind: 'prompt', id: 'x', name: 'y' },
		}))).toBeNull();
	});

	it('returns null for null value', () => {
		expect(decodeDragPayload('null')).toBeNull();
	});

	it('returns null for array value', () => {
		expect(decodeDragPayload('[]')).toBeNull();
	});

	it('returns null for number value', () => {
		expect(decodeDragPayload('42')).toBeNull();
	});

	it('round-trips a folder descriptor', () => {
		const payload: DragPayload = {
			descriptor: createFolderDescriptor('f-1', 'My Folder', null, 0),
			source: 'folder-window',
		};
		const encoded = encodeDragPayload(payload);
		const decoded = decodeDragPayload(encoded);
		expect(decoded).not.toBeNull();
		expect(decoded!.descriptor.kind).toBe('folder');
		expect(decoded!.descriptor.id).toBe('f-1');
		expect(decoded!.source).toBe('folder-window');
	});

	it('preserves folder descriptor parentId and depth', () => {
		const payload: DragPayload = {
			descriptor: createFolderDescriptor('f-2', 'Sub', 'f-1', 3),
			source: 'projects-window',
		};
		const decoded = decodeDragPayload(encodeDragPayload(payload));
		expect(decoded).not.toBeNull();
		const d = decoded!.descriptor;
		expect(d.kind).toBe('folder');
		if (d.kind === 'folder') {
			expect(d.parentId).toBe('f-1');
			expect(d.depth).toBe(3);
		}
	});
});
