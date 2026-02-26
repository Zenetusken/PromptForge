import { fetchHealth, fetchProviders, validateApiKey, type HealthResponse, type LLMHeaders, type ProviderInfo, type TokenBudgetStatus, type ValidateKeyResponse } from '$lib/api/client';
import { settingsState } from '$lib/stores/settings.svelte';
import { systemBus } from '$lib/services/systemBus.svelte';
import { maskApiKey } from '$lib/utils/format';

const STORAGE_PREFIX = 'pf_key_';
const MODEL_PREFIX = 'pf_model_';
const REMEMBER_KEY = 'pf_remember_keys';

export interface ValidationResult {
	valid: boolean;
	error: string | null;
}

class ProviderState {
	// Health (shared — replaces Footer local state)
	health: HealthResponse | null = $state(null);
	healthChecking: boolean = $state(true);

	// Provider list from /api/providers
	providers: ProviderInfo[] = $state([]);
	providersLoaded: boolean = $state(false);

	// User's per-session provider selection (null = auto-detect)
	selectedProvider: string | null = $state(null);

	// Token budget status from health endpoint
	tokenBudgets: Record<string, TokenBudgetStatus> = $state({});

	// Masked display values for API keys (raw keys stay in browser storage only)
	apiKeys: Record<string, string> = $state({});

	// Per-provider model selection
	selectedModels: Record<string, string> = $state({});

	// Whether to persist keys in localStorage (default: sessionStorage)
	rememberKeys: boolean = $state(false);

	// Validation state per provider
	validating: Record<string, boolean> = $state({});
	validationResult: Record<string, ValidationResult> = $state({});

	// Tracks the latest validation request ID per provider to discard stale results
	private _validationIds: Record<string, number> = {};
	private _nextValidationId = 0;

	private intervalId: ReturnType<typeof setInterval> | null = null;
	private _intervalMs = 60_000;
	private _visibilityHandler: (() => void) | null = null;

	// Staleness tracking — skip fetches when data is still fresh
	private static readonly _PROVIDERS_STALE_MS = 10_000;
	private static readonly _HEALTH_STALE_MS = 15_000;
	private _providersLastFetch = 0;
	private _healthLastFetch = 0;

	// In-flight deduplication — coalesce concurrent calls
	private _providersFetching: Promise<void> | null = null;
	private _healthFetching: Promise<void> | null = null;

	// Provider list refreshes every Nth poll tick (~180s at 60s interval)
	private static readonly _PROVIDER_REFRESH_EVERY = 3;
	private _pollCycle = 0;

	// MCP transition detection — skip first poll to avoid spurious notifications
	private _mcpPreviousState: boolean | null = null;
	private _mcpFirstPoll = true;

	constructor() {
		if (typeof window !== 'undefined') {
			this.rememberKeys = localStorage.getItem(REMEMBER_KEY) === 'true';
			this._hydrateFromStorage();
			// Apply default provider from settings if no provider was loaded from session
			if (!this.selectedProvider && settingsState.defaultProvider) {
				this.selectedProvider = settingsState.defaultProvider;
			}
		}
	}

	get activeProvider(): ProviderInfo | null {
		if (this.selectedProvider) {
			return this.providers.find((p) => p.name === this.selectedProvider) ?? null;
		}
		return this.providers.find((p) => p.is_default) ?? null;
	}

	get availableProviders(): ProviderInfo[] {
		return this.providers.filter((p) => p.available || this.hasKey(p.name));
	}

	/**
	 * Check if a provider is effectively available — either the server reports
	 * it as available, or the user has provided a client-side API key.
	 */
	isEffectivelyAvailable(providerName: string): boolean {
		const p = this.providers.find((pr) => pr.name === providerName);
		if (!p) return false;
		return p.available || this.hasKey(providerName);
	}

	// --- API Key Management ---
	// Keys are cached in reactive state to avoid synchronous storage reads
	// during render. Raw keys are only read from storage on demand (getApiKey).

	hasKey(provider: string): boolean {
		return provider in this.apiKeys;
	}

	setApiKey(provider: string, key: string) {
		this._getStorage().setItem(STORAGE_PREFIX + provider, key);
		this.apiKeys = { ...this.apiKeys, [provider]: maskApiKey(key) };
	}

	getApiKey(provider: string): string | null {
		return this._getStorage().getItem(STORAGE_PREFIX + provider);
	}

	clearApiKey(provider: string) {
		this._getStorage().removeItem(STORAGE_PREFIX + provider);
		const next = { ...this.apiKeys };
		delete next[provider];
		this.apiKeys = next;
		// Always clear validation state alongside the key
		this.clearValidation(provider);
	}

	// --- Validation ---

	async validateKey(provider: string, key: string): Promise<ValidateKeyResponse> {
		// Assign a unique ID to this request so we can discard stale results
		const requestId = ++this._nextValidationId;
		this._validationIds[provider] = requestId;

		this.validating = { ...this.validating, [provider]: true };
		// Clear previous result while validating
		const nextResult = { ...this.validationResult };
		delete nextResult[provider];
		this.validationResult = nextResult;

		const result = await validateApiKey(provider, key);

		// Only apply if this is still the latest request for this provider
		if (this._validationIds[provider] !== requestId) {
			return result;
		}

		this.validating = { ...this.validating, [provider]: false };
		this.validationResult = {
			...this.validationResult,
			[provider]: { valid: result.valid, error: result.error },
		};

		// On success, force-refresh the provider list so availability updates
		if (result.valid) {
			this.loadProviders(true);
		}
		return result;
	}

	clearValidation(provider: string) {
		// Invalidate any in-flight request for this provider
		delete this._validationIds[provider];

		const nextV = { ...this.validating };
		delete nextV[provider];
		this.validating = nextV;

		const nextR = { ...this.validationResult };
		delete nextR[provider];
		this.validationResult = nextR;
	}

	// --- Model Selection ---
	// Model selections cached in reactive state to avoid storage reads during render.

	setModel(provider: string, modelId: string) {
		this._getStorage().setItem(MODEL_PREFIX + provider, modelId);
		this.selectedModels = { ...this.selectedModels, [provider]: modelId };
	}

	getModel(provider: string): string | null {
		return this.selectedModels[provider] ?? null;
	}

	// --- Remember Keys Toggle ---

	setRememberKeys(value: boolean) {
		this.rememberKeys = value;
		localStorage.setItem(REMEMBER_KEY, String(value));

		// Migrate keys between storage backends
		const source = value ? sessionStorage : localStorage;
		const target = value ? localStorage : sessionStorage;

		for (const provider of Object.keys(this.apiKeys)) {
			const raw = source.getItem(STORAGE_PREFIX + provider);
			if (raw) {
				target.setItem(STORAGE_PREFIX + provider, raw);
				source.removeItem(STORAGE_PREFIX + provider);
			}
			const model = source.getItem(MODEL_PREFIX + provider);
			if (model) {
				target.setItem(MODEL_PREFIX + provider, model);
				source.removeItem(MODEL_PREFIX + provider);
			}
		}
	}

	/**
	 * Build LLMHeaders for the currently selected provider.
	 * Returns undefined if no overrides are needed.
	 */
	getLLMHeaders(): LLMHeaders | undefined {
		const provider = this.selectedProvider;
		if (!provider) return undefined;

		const apiKey = this.getApiKey(provider) ?? undefined;
		const model = this.getModel(provider) ?? undefined;

		if (!apiKey && !model) return { provider };
		return { provider, apiKey, model };
	}

	// --- Polling & Loading ---

	async pollHealth() {
		if (this._healthFetching) return this._healthFetching;
		this._healthFetching = this._doPollHealth();
		return this._healthFetching;
	}

	private async _doPollHealth() {
		try {
			this.healthChecking = true;
			const result = await fetchHealth();
			this.health = result;
			this.tokenBudgets = result?.token_budgets ?? {};
			this._healthLastFetch = Date.now();
			this.healthChecking = false;

			// MCP transition detection
			if (result) {
				const mcpNow = result.mcp_connected;
				if (this._mcpFirstPoll) {
					// Skip notification on initial page load
					this._mcpFirstPoll = false;
				} else if (this._mcpPreviousState !== null && mcpNow !== this._mcpPreviousState) {
					if (mcpNow) {
						systemBus.emit('mcp:session_connect', 'provider', {});
					} else {
						systemBus.emit('mcp:session_disconnect', 'provider', {});
					}
				}
				this._mcpPreviousState = mcpNow;
			}
		} finally {
			this._healthFetching = null;
		}
	}

	async loadProviders(force = false) {
		// Skip if data is still fresh (unless force)
		if (
			!force &&
			this.providersLoaded &&
			Date.now() - this._providersLastFetch < ProviderState._PROVIDERS_STALE_MS
		) {
			return;
		}
		if (this._providersFetching) return this._providersFetching;
		this._providersFetching = this._doLoadProviders();
		return this._providersFetching;
	}

	private async _doLoadProviders() {
		try {
			this.providers = await fetchProviders();
			this._providersLastFetch = Date.now();
			this.providersLoaded = true;
		} finally {
			this._providersFetching = null;
		}
	}

	selectProvider(name: string | null) {
		this.selectedProvider = name;
	}

	private _pollTick() {
		this.pollHealth();
		this._pollCycle++;
		if (this._pollCycle % ProviderState._PROVIDER_REFRESH_EVERY === 0) {
			this.loadProviders(true);
		}
	}

	startPolling(intervalMs = 60_000) {
		// Guard against double-subscription on component remount
		this.stopPolling();
		this._pollCycle = 0;
		this._intervalMs = intervalMs;
		this.pollHealth();
		this.loadProviders();
		this.intervalId = setInterval(() => this._pollTick(), intervalMs);

		// Pause polling when tab is hidden, resume with jitter on return
		this._visibilityHandler = () => {
			if (document.hidden) {
				if (this.intervalId !== null) {
					clearInterval(this.intervalId);
					this.intervalId = null;
				}
			} else {
				// Add 0-2s jitter before first poll on visibility restore
				// to avoid thundering herd across many tabs
				if (this.intervalId === null) {
					const jitter = Math.random() * 2000;
					setTimeout(() => {
						if (this.intervalId === null) {
							this._pollTick();
							this.intervalId = setInterval(() => this._pollTick(), this._intervalMs);
						}
					}, jitter);
				}
			}
		};
		document.addEventListener('visibilitychange', this._visibilityHandler);
	}

	stopPolling() {
		if (this.intervalId !== null) {
			clearInterval(this.intervalId);
			this.intervalId = null;
		}
		if (this._visibilityHandler) {
			document.removeEventListener('visibilitychange', this._visibilityHandler);
			this._visibilityHandler = null;
		}
	}

	// --- Private ---

	private _getStorage(): Storage {
		return this.rememberKeys ? localStorage : sessionStorage;
	}

	private _hydrateFromStorage() {
		const storage = this._getStorage();
		const keys: Record<string, string> = {};
		const models: Record<string, string> = {};

		for (let i = 0; i < storage.length; i++) {
			const k = storage.key(i);
			if (!k) continue;
			if (k.startsWith(STORAGE_PREFIX)) {
				const provider = k.slice(STORAGE_PREFIX.length);
				const raw = storage.getItem(k);
				if (raw) keys[provider] = maskApiKey(raw);
			} else if (k.startsWith(MODEL_PREFIX)) {
				const provider = k.slice(MODEL_PREFIX.length);
				const val = storage.getItem(k);
				if (val) models[provider] = val;
			}
		}

		this.apiKeys = keys;
		this.selectedModels = models;
	}
}

export const providerState = new ProviderState();
