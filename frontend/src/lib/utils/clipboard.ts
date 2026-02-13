/**
 * Copy text to clipboard using the Clipboard API with a fallback.
 * Returns true if the copy was successful, false otherwise.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
	// Modern Clipboard API
	if (navigator.clipboard && window.isSecureContext) {
		try {
			await navigator.clipboard.writeText(text);
			return true;
		} catch {
			// Fall through to fallback
		}
	}

	// Fallback for older browsers or non-secure contexts
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
		return result;
	} catch {
		return false;
	}
}
