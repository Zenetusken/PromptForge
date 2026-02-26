/**
 * Settings Store — persistent user preferences.
 *
 * Layer 3 (System Libraries) in the PromptForge OS stack.
 * Persisted to localStorage. Drives reactive CSS custom properties.
 */

export type NeonColor =
	| 'neon-cyan'
	| 'neon-purple'
	| 'neon-green'
	| 'neon-red'
	| 'neon-yellow'
	| 'neon-orange'
	| 'neon-blue'
	| 'neon-pink'
	| 'neon-teal'
	| 'neon-indigo';

export const NEON_COLORS: NeonColor[] = [
	'neon-cyan',
	'neon-purple',
	'neon-green',
	'neon-red',
	'neon-yellow',
	'neon-orange',
	'neon-blue',
	'neon-pink',
	'neon-teal',
	'neon-indigo',
];

export interface SystemSettings {
	// Provider
	defaultProvider: string | null;
	maxConcurrentForges: number;
	autoRetryOnRateLimit: boolean;

	// Pipeline
	defaultStrategy: string;
	defaultSecondaryFrameworks: string[];
	defaultStages: string[];

	// Display
	accentColor: NeonColor;
	enableAnimations: boolean;
}

const STORAGE_KEY = 'pf_settings';

const DEFAULT_SETTINGS: SystemSettings = {
	defaultProvider: null,
	maxConcurrentForges: 2,
	autoRetryOnRateLimit: false,
	defaultStrategy: '',
	defaultSecondaryFrameworks: [],
	defaultStages: ['analyze', 'strategy', 'optimize', 'validate'],
	accentColor: 'neon-cyan',
	enableAnimations: true,
};

function loadSettings(): SystemSettings {
	if (typeof window === 'undefined') return { ...DEFAULT_SETTINGS };
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (raw) {
			const parsed = JSON.parse(raw);
			return { ...DEFAULT_SETTINGS, ...parsed };
		}
	} catch {
		// ignore
	}
	return { ...DEFAULT_SETTINGS };
}

class SettingsState {
	settings: SystemSettings = $state(loadSettings());

	// --- Convenience getters ---
	get accentColor(): NeonColor { return this.settings.accentColor; }
	get maxConcurrentForges(): number { return this.settings.maxConcurrentForges; }
	get enableAnimations(): boolean { return this.settings.enableAnimations; }
	get defaultStrategy(): string { return this.settings.defaultStrategy; }
	get defaultProvider(): string | null { return this.settings.defaultProvider; }
	get autoRetryOnRateLimit(): boolean { return this.settings.autoRetryOnRateLimit; }

	/**
	 * Update one or more settings fields.
	 */
	update(patch: Partial<SystemSettings>): void {
		this.settings = { ...this.settings, ...patch };
		this._persist();
		this._applyCSS();
	}

	/**
	 * Reset all settings to defaults.
	 */
	reset(): void {
		this.settings = { ...DEFAULT_SETTINGS };
		this._persist();
		this._applyCSS();
	}

	/**
	 * Apply accent color as CSS custom property on :root.
	 * Called on load and on update.
	 */
	private _applyCSS(): void {
		if (typeof document === 'undefined') return;
		document.documentElement.style.setProperty('--accent-color', `var(--${this.settings.accentColor})`);
	}

	private _persist(): void {
		if (typeof window === 'undefined') return;
		try {
			localStorage.setItem(STORAGE_KEY, JSON.stringify(this.settings));
		} catch {
			// ignore
		}
	}
}

export const settingsState = new SettingsState();
