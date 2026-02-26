/**
 * Clipboard Service — unified clipboard with history for rapid prompt iteration.
 *
 * Layer 3 (System Libraries) in the PromptForge OS stack.
 * Wraps navigator.clipboard with copy history, labels, and bus integration.
 */

import { systemBus } from './systemBus.svelte';

export interface ClipboardEntry {
	id: string;
	text: string;
	label: string;
	source: string;
	timestamp: number;
}

const MAX_HISTORY = 10;
const STORAGE_KEY = 'pf_clipboard_history';
let clipCounter = 0;

function loadPersistedHistory(): ClipboardEntry[] {
	if (typeof window === 'undefined') return [];
	try {
		const raw = sessionStorage.getItem(STORAGE_KEY);
		if (raw) return JSON.parse(raw);
	} catch {
		// ignore
	}
	return [];
}

class ClipboardService {
	history: ClipboardEntry[] = $state(loadPersistedHistory());

	/**
	 * Copy text to the system clipboard and record in history.
	 * Returns true on success, false on failure.
	 */
	async copy(text: string, label = 'Copied text', source = 'manual'): Promise<boolean> {
		try {
			await navigator.clipboard.writeText(text);
		} catch {
			// Fallback: textarea method
			try {
				const textarea = document.createElement('textarea');
				textarea.value = text;
				textarea.style.position = 'fixed';
				textarea.style.opacity = '0';
				document.body.appendChild(textarea);
				textarea.select();
				document.execCommand('copy');
				document.body.removeChild(textarea);
			} catch {
				return false;
			}
		}

		const entry: ClipboardEntry = {
			id: `clip_${++clipCounter}`,
			text,
			label,
			source,
			timestamp: Date.now(),
		};

		this.history = [entry, ...this.history].slice(0, MAX_HISTORY);
		this._persist();

		systemBus.emit('clipboard:copied', 'clipboardService', {
			label,
			source,
			textLength: text.length,
		});

		return true;
	}

	/**
	 * Get the most recent clipboard entry.
	 */
	getLatest(): ClipboardEntry | null {
		return this.history[0] ?? null;
	}

	/**
	 * Clear all clipboard history.
	 */
	clear(): void {
		this.history = [];
		this._persist();
	}

	/**
	 * Full reset for testing.
	 */
	reset(): void {
		this.history = [];
		clipCounter = 0;
		if (typeof window !== 'undefined') {
			try { sessionStorage.removeItem(STORAGE_KEY); } catch { /* ignore */ }
		}
	}

	private _persist(): void {
		if (typeof window === 'undefined') return;
		try {
			sessionStorage.setItem(STORAGE_KEY, JSON.stringify(this.history));
		} catch {
			// ignore
		}
	}
}

export const clipboardService = new ClipboardService();
