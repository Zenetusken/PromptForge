/**
 * Shared formatting utilities for scores, numbers, and text display.
 */

/** Format a numeric score for display (e.g. 7.3). Returns '--' for null/undefined. */
export function formatScore(score: number | null | undefined, decimals = 1): string {
  if (score === null || score === undefined) return '--';
  return score.toFixed(decimals);
}

/** Format a delta value with sign prefix (e.g. '+1.2', '-0.3'). */
export function formatDelta(delta: number, decimals = 1): string {
  return (delta > 0 ? '+' : '') + delta.toFixed(decimals);
}

/** Truncate text to maxLen characters, appending '...' if truncated. */
export function truncateText(text: string, maxLen = 80): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen).trimEnd() + '...';
}

/**
 * Copy text to clipboard with fallback for older browsers.
 * Returns true on success, false on failure.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Fallback: temporary textarea + execCommand
    const el = document.createElement('textarea');
    el.value = text;
    document.body.appendChild(el);
    el.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(el);
    return ok;
  }
}
