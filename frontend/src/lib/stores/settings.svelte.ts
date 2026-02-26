/**
 * Settings Store — persistent user preferences.
 *
 * Layer 3 (System Libraries) in the PromptForge OS stack.
 * Persisted to localStorage. Drives reactive CSS custom properties.
 */

export type WallpaperMode = 'static' | 'subtle' | 'dynamic';
export type PerformanceProfile = 'low' | 'balanced' | 'high' | 'custom';

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

/** Hex values for each neon color — shared across components that render color swatches. */
export const NEON_COLOR_HEX: Record<NeonColor, string> = {
	'neon-cyan': '#00e5ff',
	'neon-purple': '#a855f7',
	'neon-green': '#22ff88',
	'neon-red': '#ff3366',
	'neon-yellow': '#fbbf24',
	'neon-orange': '#ff8c00',
	'neon-blue': '#4d8eff',
	'neon-pink': '#ff6eb4',
	'neon-teal': '#00d4aa',
	'neon-indigo': '#7b61ff',
};

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
	wallpaperMode: WallpaperMode;
	wallpaperOpacity: number;
	performanceProfile: PerformanceProfile;
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
	wallpaperMode: 'static',
	wallpaperOpacity: 0.12,
	performanceProfile: 'low',
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

/** Governed fields that presets control. */
type PresetFields = Pick<SystemSettings, 'wallpaperMode' | 'wallpaperOpacity' | 'enableAnimations'>;

const PRESETS: Record<Exclude<PerformanceProfile, 'custom'>, PresetFields> = {
	low:      { wallpaperMode: 'static',  wallpaperOpacity: 0.12, enableAnimations: true },
	balanced: { wallpaperMode: 'subtle',  wallpaperOpacity: 0.15, enableAnimations: true },
	high:     { wallpaperMode: 'dynamic', wallpaperOpacity: 0.20, enableAnimations: true },
};

function detectProfile(s: SystemSettings): PerformanceProfile {
	for (const [key, preset] of Object.entries(PRESETS) as [Exclude<PerformanceProfile, 'custom'>, PresetFields][]) {
		if (
			s.wallpaperMode === preset.wallpaperMode &&
			s.wallpaperOpacity === preset.wallpaperOpacity &&
			s.enableAnimations === preset.enableAnimations
		) return key;
	}
	return 'custom';
}

class SettingsState {
	settings: SystemSettings = $state(loadSettings());

	constructor() {
		this._applyCSS();
	}

	// --- Convenience getters ---
	get accentColor(): NeonColor { return this.settings.accentColor; }
	get maxConcurrentForges(): number { return this.settings.maxConcurrentForges; }
	get enableAnimations(): boolean { return this.settings.enableAnimations; }
	get defaultStrategy(): string { return this.settings.defaultStrategy; }
	get defaultProvider(): string | null { return this.settings.defaultProvider; }
	get autoRetryOnRateLimit(): boolean { return this.settings.autoRetryOnRateLimit; }
	get wallpaperMode(): WallpaperMode { return this.settings.wallpaperMode; }
	get wallpaperOpacity(): number { return this.settings.wallpaperOpacity; }
	get performanceProfile(): PerformanceProfile { return this.settings.performanceProfile; }

	/** Returns the detected profile based on current governed fields. */
	get detectedProfile(): PerformanceProfile {
		return detectProfile(this.settings);
	}

	/**
	 * Apply a preset — patches all governed fields + sets performanceProfile in one call.
	 */
	applyPreset(profile: Exclude<PerformanceProfile, 'custom'>): void {
		this.update({ ...PRESETS[profile], performanceProfile: profile });
	}

	/**
	 * Update one or more settings fields.
	 */
	update(patch: Partial<SystemSettings>): void {
		const next = { ...this.settings, ...patch };
		// Auto-detect profile when governed fields change and profile wasn't explicitly set
		if (!('performanceProfile' in patch)) {
			next.performanceProfile = detectProfile(next);
		}
		this.settings = next;
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
		document.documentElement.style.setProperty('--wallpaper-opacity', String(this.settings.wallpaperOpacity));
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
