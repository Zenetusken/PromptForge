import type { NodeDescriptor } from './fileDescriptor';

export type DragSource =
	| 'projects-window'
	| 'history-window'
	| 'tab-bar'
	| 'desktop'
	| 'template-library'
	| 'folder-window';

export interface DragPayload {
	descriptor: NodeDescriptor;
	source: DragSource;
}

export const DRAG_MIME = 'application/x-promptforge';

export function encodeDragPayload(payload: DragPayload): string {
	return JSON.stringify(payload);
}

export function decodeDragPayload(data: string): DragPayload | null {
	try {
		const parsed = JSON.parse(data);
		if (parsed && parsed.descriptor && parsed.source) {
			return parsed as DragPayload;
		}
	} catch {
		// Invalid payload — ignore
	}
	return null;
}
