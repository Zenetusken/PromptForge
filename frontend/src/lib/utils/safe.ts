/**
 * Type-safe accessors for untyped data sources (SSE payloads, API responses).
 *
 * "Or" variants return the raw fallback type (string, number, string[]).
 * "OrUndefined" variants return undefined when the value is absent or wrong-typed,
 * preserving the ability to distinguish "missing" from "zero"/"empty".
 */

export function safeString(value: unknown, fallback = ''): string {
	return typeof value === 'string' ? value : fallback;
}

export function safeNumber(value: unknown, fallback = 0): number {
	return typeof value === 'number' ? value : fallback;
}

export function safeArray(value: unknown): string[] {
	return Array.isArray(value) ? value : [];
}

export function safeStringOrUndefined(value: unknown): string | undefined {
	return typeof value === 'string' ? value : undefined;
}

export function safeNumberOrUndefined(value: unknown): number | undefined {
	return typeof value === 'number' ? value : undefined;
}

export function safeArrayOrUndefined(value: unknown): string[] | undefined {
	return Array.isArray(value) ? value : undefined;
}

/**
 * Convert a value that may be a string, string[], or undefined into a
 * newline-delimited string suitable for textarea display.
 * Handles the common case where backend JSON fields arrive as a bare string
 * instead of an array (e.g., CodebaseContext.conventions from workspace sync).
 */
export function toLines(value: string | string[] | undefined | null): string {
	if (!value) return '';
	if (Array.isArray(value)) return value.join('\n');
	return String(value);
}
