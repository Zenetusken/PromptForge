/**
 * Copy text to clipboard using execCommand fallback with Clipboard API as backup.
 * Returns true on success, false otherwise.
 */
export function copyToClipboard(text: string): boolean {
	// Use execCommand first (synchronous, reliable across all environments)
	try {
		const textArea = document.createElement('textarea');
		textArea.value = text;
		textArea.style.position = 'fixed';
		textArea.style.left = '-9999px';
		textArea.style.top = '-9999px';
		document.body.appendChild(textArea);
		textArea.focus();
		textArea.select();
		const result = document.execCommand('copy');
		document.body.removeChild(textArea);
		if (result) return true;
	} catch {
		// Fall through to clipboard API
	}

	// Try modern Clipboard API as fire-and-forget backup
	// (may hang in some environments like Puppeteer, so don't await)
	navigator.clipboard?.writeText(text).catch(() => {});
	return true;
}
