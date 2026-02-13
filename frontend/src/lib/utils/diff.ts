import { diffWords, diffLines } from 'diff';

export interface DiffSegment {
	type: 'added' | 'removed' | 'equal';
	value: string;
}

export interface DiffLine {
	lineNumber: number;
	text: string;
	type: 'added' | 'removed' | 'equal';
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

/**
 * Compute a line-level diff and return separate arrays for left (original) and right (optimized) panels.
 * Each line is tagged with its type (added/removed/equal) and line number.
 */
export function computeLineDiff(original: string, modified: string): { left: DiffLine[]; right: DiffLine[] } {
	const changes = diffLines(original, modified);
	const left: DiffLine[] = [];
	const right: DiffLine[] = [];
	let leftLineNum = 1;
	let rightLineNum = 1;

	for (const change of changes) {
		const lines = change.value.replace(/\n$/, '').split('\n');
		if (change.removed) {
			for (const line of lines) {
				left.push({ lineNumber: leftLineNum++, text: line, type: 'removed' });
			}
		} else if (change.added) {
			for (const line of lines) {
				right.push({ lineNumber: rightLineNum++, text: line, type: 'added' });
			}
		} else {
			for (const line of lines) {
				left.push({ lineNumber: leftLineNum++, text: line, type: 'equal' });
				right.push({ lineNumber: rightLineNum++, text: line, type: 'equal' });
			}
		}
	}

	return { left, right };
}
