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
 * Truncate text to a maximum length, adding ellipsis if needed.
 */
export function truncateText(text: string, maxLength: number): string {
	if (text.length <= maxLength) return text;
	return text.slice(0, maxLength).trimEnd() + '...';
}

/**
 * Normalize a score to 0-100 scale.
 * Scores <= 1 are treated as 0-1 scale; otherwise as 0-100.
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
