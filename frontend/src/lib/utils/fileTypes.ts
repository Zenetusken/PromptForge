export type FileExtension = '.md' | '.forge' | '.scan' | '.val' | '.strat' | '.tmpl' | '.app' | '.lnk';

export interface FileTypeMetadata {
	readonly label: string;
	readonly icon: string;
	readonly color: string;
	readonly editable: boolean;
	readonly versionable: boolean;
}

export const FILE_EXTENSIONS: Record<FileExtension, FileTypeMetadata> = {
	'.md': { label: 'Markdown Prompt', icon: 'file-text', color: 'cyan', editable: true, versionable: true },
	'.forge': { label: 'Forge Result', icon: 'zap', color: 'purple', editable: false, versionable: false },
	'.scan': { label: 'Forge Analysis', icon: 'search', color: 'green', editable: false, versionable: false },
	'.val': { label: 'Forge Scores', icon: 'activity', color: 'yellow', editable: false, versionable: false },
	'.strat': { label: 'Forge Strategy', icon: 'sliders', color: 'indigo', editable: false, versionable: false },
	'.tmpl': { label: 'Prompt Template', icon: 'file-code', color: 'teal', editable: false, versionable: false },
	'.app': { label: 'Application', icon: 'monitor', color: 'cyan', editable: false, versionable: false },
	'.lnk': { label: 'Shortcut', icon: 'link', color: 'blue', editable: false, versionable: false },
};

// ── Artifact types (system-produced, immutable records) ──

export type ArtifactKind = 'forge-result' | 'forge-analysis' | 'forge-scores' | 'forge-strategy';

export interface ArtifactKindMetadata {
	readonly label: string;
	readonly icon: string;
	readonly color: string;
}

export const ARTIFACT_KINDS: Record<ArtifactKind, ArtifactKindMetadata> = {
	'forge-result': { label: 'Forge Result', icon: 'zap', color: 'purple' },
	'forge-analysis': { label: 'Analysis', icon: 'search', color: 'green' },
	'forge-scores': { label: 'Scores', icon: 'activity', color: 'yellow' },
	'forge-strategy': { label: 'Strategy', icon: 'sliders', color: 'indigo' },
};

/** Map each artifact kind to its canonical file extension. */
export const ARTIFACT_EXTENSION_MAP: Record<ArtifactKind, FileExtension> = {
	'forge-result': '.forge',
	'forge-analysis': '.scan',
	'forge-scores': '.val',
	'forge-strategy': '.strat',
};

/**
 * Derive a display name for a forge result artifact.
 * "My Title" → "My Title"
 * score 0.8 → "Forge Result (8/10)"
 * neither → "Forge Result"
 */
export function toArtifactName(title?: string | null, overallScore?: number | null): string {
	if (title?.trim()) return title.trim();
	if (overallScore != null && overallScore > 0) {
		return `Forge Result (${Math.round(overallScore * 10)}/10)`;
	}
	return 'Forge Result';
}

/**
 * Derive a display filename for a .forge file.
 * Uses title if available, falls back to score-based name, appends version if provided.
 * "My Title", 0.8, "v2" → "My Title v2.forge"
 * null, 0.8 → "Forge Result (8/10).forge"
 * null, null → "Forge Result.forge"
 */
export function toForgeFilename(
	title?: string | null,
	overallScore?: number | null,
	version?: string | null,
): string {
	let base = toArtifactName(title, overallScore);
	if (version?.trim()) {
		base = `${base} ${version.trim()}`;
	}
	return `${base}.forge`;
}

/**
 * Return the canonical filename for a sub-artifact kind.
 * 'forge-analysis' → "analysis.scan"
 * 'forge-scores' → "scores.val"
 * 'forge-strategy' → "strategy.strat"
 */
export function toSubArtifactFilename(artifactKind: ArtifactKind): string {
	const ext = ARTIFACT_EXTENSION_MAP[artifactKind];
	switch (artifactKind) {
		case 'forge-analysis': return `analysis${ext}`;
		case 'forge-scores': return `scores${ext}`;
		case 'forge-strategy': return `strategy${ext}`;
		default: return `result${ext}`;
	}
}

export const DEFAULT_EXTENSION: FileExtension = '.md';

// Sort weights: system → folder → shortcut → file
export const TYPE_SORT_ORDER: Record<string, number> = {
	system: 0,
	folder: 1,
	shortcut: 2,
	file: 3,
	prompt: 3,
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
