import { processScheduler } from '$lib/stores/processScheduler.svelte';

export type ForgeMode = 'compose' | 'forging' | 'review' | 'compare';
export type WidthTier = 'compact' | 'standard' | 'wide';

export interface ComparisonSlots {
	slotA: string | null; // optimization ID
	slotB: string | null;
}

const WIDTH_STORAGE_KEY = 'pf_forge_panel_width';
const MACHINE_STORAGE_KEY = 'pf_forge_machine';
const MIN_WIDTH = 240;
const MAX_WIDTH = 560;

function clamp(value: number, min: number, max: number): number {
	return Math.min(Math.max(value, min), max);
}

function loadPersistedWidth(): number {
	if (typeof window === 'undefined') return MIN_WIDTH;
	try {
		let stored = localStorage.getItem(WIDTH_STORAGE_KEY);
		if (!stored) {
			// Migrate from sessionStorage (old location)
			stored = sessionStorage.getItem(WIDTH_STORAGE_KEY);
			if (stored) {
				localStorage.setItem(WIDTH_STORAGE_KEY, stored);
				sessionStorage.removeItem(WIDTH_STORAGE_KEY);
			}
		}
		if (stored) {
			const parsed = parseInt(stored, 10);
			if (!isNaN(parsed)) return clamp(parsed, MIN_WIDTH, MAX_WIDTH);
		}
	} catch {
		// ignore
	}
	return MIN_WIDTH;
}

function loadPersistedMachine(): { mode: ForgeMode; isMinimized: boolean } | null {
	if (typeof window === 'undefined') return null;
	try {
		const raw = sessionStorage.getItem(MACHINE_STORAGE_KEY);
		if (raw) return JSON.parse(raw);
	} catch {
		// ignore
	}
	return null;
}

class ForgeMachineState {
	mode: ForgeMode = $state('compose');
	panelWidth: number = $state(loadPersistedWidth());
	comparison: ComparisonSlots = $state({ slotA: null, slotB: null });
	isMinimized: boolean = $state(false);

	widthTier: WidthTier = $derived(
		this.panelWidth >= 480 ? 'wide' : this.panelWidth >= 340 ? 'standard' : 'compact'
	);

	isCompact: boolean = $derived(this.widthTier === 'compact');

	// Process state delegated to processScheduler — use it directly

	runningCount: number = $derived(processScheduler.runningCount);

	constructor() {
		// Hydrate machine state
		const saved = loadPersistedMachine();
		if (saved) {
			// Only restore non-running states
			if (saved.mode !== 'forging') {
				this.mode = saved.mode;
			}
			this.isMinimized = saved.isMinimized;
		}
	}

	// --- Guarded state transitions ---

	forge() {
		if (this.mode === 'compose') {
			this.mode = 'forging';
			// Auto-widen to standard for pipeline visibility
			if (this.panelWidth < 340) {
				this.setWidth(380);
			}
			this._persistMachine();
		}
	}

	complete() {
		if (this.mode === 'forging') {
			this.mode = 'review';
			this._persistMachine();
		}
	}

	compare(slotA: string, slotB: string) {
		this.comparison = { slotA, slotB };
		this.mode = 'compare';
		// Auto-widen to wide for comparison
		if (this.panelWidth < 480) {
			this.setWidth(560);
		}
		this._persistMachine();
	}

	back() {
		if (this.mode !== 'compose') {
			this.mode = 'compose';
			this.comparison = { slotA: null, slotB: null };
			this.isMinimized = false;
			this._persistMachine();
		}
	}

	reset() {
		this.mode = 'compose';
		this.comparison = { slotA: null, slotB: null };
		this.isMinimized = false;
		this._persistMachine();
	}

	minimize() {
		if (this.mode !== 'compose') {
			this.isMinimized = true;
			this._persistMachine();
		}
	}

	restore() {
		this.isMinimized = false;
		this._persistMachine();
	}

	/** Enter review mode directly (for viewing results outside the normal pipeline flow). */
	enterReview() {
		this.mode = 'review';
		this.isMinimized = false;
		this._persistMachine();
	}

	/** Enter forging mode directly (for re-forge outside the compose → forging flow). */
	enterForging() {
		this.mode = 'forging';
		if (this.panelWidth < 340) {
			this.setWidth(380);
		}
		this._persistMachine();
	}

	// --- Panel width ---

	setWidth(w: number) {
		this.panelWidth = clamp(w, MIN_WIDTH, MAX_WIDTH);
		this._persistWidth();
	}

	private _persistWidth() {
		if (typeof window === 'undefined') return;
		try {
			localStorage.setItem(WIDTH_STORAGE_KEY, String(this.panelWidth));
		} catch {
			// ignore
		}
	}

	private _persistMachine() {
		if (typeof window === 'undefined') return;
		try {
			sessionStorage.setItem(MACHINE_STORAGE_KEY, JSON.stringify({
				mode: this.mode,
				isMinimized: this.isMinimized,
			}));
		} catch {
			// ignore
		}
	}
}

export const forgeMachine = new ForgeMachineState();
