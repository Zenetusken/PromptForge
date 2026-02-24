export type ForgeMode = 'compose' | 'forging' | 'review' | 'compare';
export type WidthTier = 'compact' | 'standard' | 'wide';

export interface ComparisonSlots {
	slotA: string | null; // optimization ID
	slotB: string | null;
}

const WIDTH_STORAGE_KEY = 'pf_forge_panel_width';
const MIN_WIDTH = 240;
const MAX_WIDTH = 560;

function clamp(value: number, min: number, max: number): number {
	return Math.min(Math.max(value, min), max);
}

function loadPersistedWidth(): number {
	if (typeof window === 'undefined') return MIN_WIDTH;
	try {
		const stored = sessionStorage.getItem(WIDTH_STORAGE_KEY);
		if (stored) {
			const parsed = parseInt(stored, 10);
			if (!isNaN(parsed)) return clamp(parsed, MIN_WIDTH, MAX_WIDTH);
		}
	} catch {
		// ignore
	}
	return MIN_WIDTH;
}

class ForgeMachineState {
	mode: ForgeMode = $state('compose');
	panelWidth: number = $state(loadPersistedWidth());
	comparison: ComparisonSlots = $state({ slotA: null, slotB: null });

	widthTier: WidthTier = $derived(
		this.panelWidth >= 480 ? 'wide' : this.panelWidth >= 340 ? 'standard' : 'compact'
	);

	isCompact: boolean = $derived(this.widthTier === 'compact');

	// --- Guarded state transitions ---

	forge() {
		if (this.mode === 'compose') {
			this.mode = 'forging';
			// Auto-widen to standard for pipeline visibility
			if (this.panelWidth < 340) {
				this.setWidth(380);
			}
		}
	}

	complete() {
		if (this.mode === 'forging') {
			this.mode = 'review';
		}
	}

	compare(slotA: string, slotB: string) {
		this.comparison = { slotA, slotB };
		this.mode = 'compare';
		// Auto-widen to wide for comparison
		if (this.panelWidth < 480) {
			this.setWidth(560);
		}
	}

	back() {
		if (this.mode !== 'compose') {
			this.mode = 'compose';
			this.comparison = { slotA: null, slotB: null };
		}
	}

	reset() {
		this.mode = 'compose';
		this.comparison = { slotA: null, slotB: null };
	}

	// --- Panel width ---

	setWidth(w: number) {
		this.panelWidth = clamp(w, MIN_WIDTH, MAX_WIDTH);
		this._persistWidth();
	}

	private _persistWidth() {
		if (typeof window === 'undefined') return;
		try {
			sessionStorage.setItem(WIDTH_STORAGE_KEY, String(this.panelWidth));
		} catch {
			// ignore
		}
	}
}

export const forgeMachine = new ForgeMachineState();
