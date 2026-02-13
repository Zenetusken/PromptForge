import { diffWords } from 'diff';

export interface DiffSegment {
	type: 'added' | 'removed' | 'equal';
	value: string;
}

/**
 * Compute a word-level diff between two strings.
 * Returns an array of segments marked as added, removed, or equal.
 */
export function computeDiff(original: string, modified: string): DiffSegment[] {
	const changes = diffWords(original, modified);

	return changes.map((change) => ({
		type: change.added ? 'added' : change.removed ? 'removed' : 'equal',
		value: change.value
	}));
}
