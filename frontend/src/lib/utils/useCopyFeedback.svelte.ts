import { copyToClipboard } from '$lib/utils/clipboard';

export function useCopyFeedback(resetMs = 2000) {
	let copied = $state(false);
	let timer: ReturnType<typeof setTimeout> | null = null;

	function copy(text: string): boolean {
		const ok = copyToClipboard(text);
		if (ok) {
			copied = true;
			if (timer) clearTimeout(timer);
			timer = setTimeout(() => {
				copied = false;
				timer = null;
			}, resetMs);
		}
		return ok;
	}

	return {
		get copied() { return copied; },
		copy
	};
}
