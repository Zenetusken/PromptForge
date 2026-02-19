/**
 * Format a date string into a relative time description.
 */
export function formatRelativeTime(dateStr: string): string {
	const date = new Date(dateStr);
	const now = new Date();
	const diffMs = now.getTime() - date.getTime();
	const diffSec = Math.floor(diffMs / 1000);
	const diffMin = Math.floor(diffSec / 60);
	const diffHour = Math.floor(diffMin / 60);
	const diffDay = Math.floor(diffHour / 24);

	if (diffSec < 60) return 'just now';
	if (diffMin < 60) return `${diffMin}m ago`;
	if (diffHour < 24) return `${diffHour}h ago`;
	if (diffDay < 7) return `${diffDay}d ago`;

	return date.toLocaleDateString('en-US', {
		month: 'short',
		day: 'numeric',
		year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
	});
}

/**
 * Format a date string into a full, human-readable timestamp.
 */
export function formatExactTime(dateStr: string): string {
	const date = new Date(dateStr);
	return date.toLocaleString('en-US', {
		weekday: 'short',
		month: 'short',
		day: 'numeric',
		year: 'numeric',
		hour: 'numeric',
		minute: '2-digit',
	});
}

/**
 * Truncate text to a maximum length, adding ellipsis if needed.
 */
export function truncateText(text: string, maxLength: number): string {
	if (text.length <= maxLength) return text;
	return text.slice(0, maxLength).trimEnd() + '...';
}

/**
 * Normalize a score to 0-100 scale for frontend display.
 * Scores <= 1 are treated as the backend's 0.0-1.0 DB scale; otherwise as 0-100.
 * Backend MCP tools use a separate 1-10 scale (see backend/app/utils/scores.py).
 */
export function normalizeScore(score: number | null | undefined): number | null {
	if (score === null || score === undefined) return null;
	if (score <= 1) return Math.round(score * 100);
	return Math.round(score);
}

/**
 * Format a score as a display string (e.g. "85" or "—").
 */
export function formatScore(score: number | null | undefined): string {
	const normalized = normalizeScore(score);
	if (normalized === null) return '—';
	return normalized.toString();
}

/**
 * Format a 0-1 rate as a percentage string (e.g. "73%") or "—".
 */
export function formatRate(value: number | null | undefined): string {
	if (value === null || value === undefined) return '—';
	return `${Math.round(value * 100)}%`;
}

/**
 * Strip redundant vendor prefix from model names for compact display.
 * "claude-opus-4-6" → "opus-4-6", "gpt-4o" → "gpt-4o"
 */
export function formatModelShort(model: string): string {
	return model.replace(/^claude-/, '');
}

/**
 * Mask an API key for display, showing only the first 4 and last 4 characters.
 */
export function maskApiKey(key: string): string {
	if (key.length <= 8) return '********';
	return key.slice(0, 4) + '...' + key.slice(-4);
}

/**
 * Get a Tailwind color class name based on score value.
 * Returns 'neon-green' (>= 70), 'neon-yellow' (>= 40), or 'neon-red'.
 */
export function getScoreColorClass(score: number | null | undefined): string {
	const normalized = normalizeScore(score);
	if (normalized === null) return 'neon-red';
	if (normalized >= 70) return 'neon-green';
	if (normalized >= 40) return 'neon-yellow';
	return 'neon-red';
}

/**
 * Get a text tier label for a score: "Good" (>= 70), "Fair" (>= 40), or "Low".
 * Provides a non-color quality indicator for WCAG 1.4.1 compliance.
 */
export function getScoreTierLabel(score: number | null | undefined): string {
	const normalized = normalizeScore(score);
	if (normalized === null) return '';
	if (normalized >= 70) return 'Good';
	if (normalized >= 40) return 'Fair';
	return 'Low';
}

/**
 * Return the number of filled dots (1-3) for a complexity level.
 */
export function formatComplexityDots(complexity: string): { filled: number; total: 3 } {
	switch (complexity.toLowerCase()) {
		case 'simple': return { filled: 1, total: 3 };
		case 'moderate': return { filled: 2, total: 3 };
		case 'complex': return { filled: 3, total: 3 };
		default: return { filled: 1, total: 3 };
	}
}

export type MetadataSegment = {
	type: 'identity' | 'process' | 'technical';
	value: string;
	tooltip?: string;
};

/**
 * Build a typed segment array for a metadata summary line.
 * Skips any segment whose value is empty/undefined.
 */
export function formatMetadataSummary(fields: {
	taskType?: string | null;
	framework?: string | null;
	model?: string | null;
}): MetadataSegment[] {
	const segments: MetadataSegment[] = [];
	if (fields.taskType) {
		segments.push({ type: 'identity', value: fields.taskType });
	}
	if (fields.framework) {
		segments.push({ type: 'process', value: fields.framework });
	}
	if (fields.model) {
		segments.push({ type: 'technical', value: formatModelShort(fields.model) });
	}
	return segments;
}

/**
 * Get combined Tailwind bg + text classes for a score badge.
 * Returns dim classes for null/undefined scores.
 */
export function getScoreBadgeClass(score: number | null | undefined): string {
	if (score === null || score === undefined) return 'bg-text-dim/10 text-text-dim';
	const color = getScoreColorClass(score);
	switch (color) {
		case 'neon-green': return 'bg-neon-green/10 text-neon-green';
		case 'neon-yellow': return 'bg-neon-yellow/10 text-neon-yellow';
		default: return 'bg-neon-red/10 text-neon-red';
	}
}
