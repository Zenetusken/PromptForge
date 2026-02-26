export type FileExtension = '.md';

export const FILE_EXTENSIONS: Record<FileExtension, { label: string; icon: string; color: string }> = {
	'.md': { label: 'Markdown Prompt', icon: 'file-text', color: 'cyan' },
};

export const DEFAULT_EXTENSION: FileExtension = '.md';

// Sort weights: system → folder → file
export const TYPE_SORT_ORDER: Record<string, number> = {
	system: 0,
	folder: 1,
	file: 2,
};

/**
 * Derive a display filename from content (and optional title).
 * "Review this Python function..." → "Review this Python function.md"
 * null/empty → "Untitled.md"
 */
export function toFilename(
	content: string,
	title?: string | null,
	ext: FileExtension = '.md'
): string {
	const source = title?.trim() || content.trim();
	if (!source) return `Untitled${ext}`;
	// If source already ends with the extension, return truncated source
	if (source.toLowerCase().endsWith(ext)) {
		return source.length > 44 ? source.slice(0, 40).trimEnd() + '...' + ext : source;
	}
	// Take first ~40 chars, break at word boundary
	if (source.length <= 40) return `${source}${ext}`;
	const truncated = source.slice(0, 40).replace(/\s+\S*$/, '').trimEnd();
	return `${truncated || source.slice(0, 40).trimEnd()}...${ext}`;
}
