import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('$lib/api/client', () => ({
    fetchHealth: vi.fn(),
    fetchProviders: vi.fn().mockResolvedValue([]),
    validateApiKey: vi.fn(),
}));

vi.mock('$lib/utils/format', () => ({
    maskApiKey: vi.fn((key: string) => '***' + key.slice(-4)),
}));

import { providerState } from './provider.svelte';
import type { ProviderInfo } from '$lib/api/client';

// Stub browser storage APIs for Node test environment
const storageStub = (() => {
    let store: Record<string, string> = {};
    return {
        getItem: (key: string) => store[key] ?? null,
        setItem: (key: string, value: string) => { store[key] = value; },
        removeItem: (key: string) => { delete store[key]; },
        clear: () => { store = {}; },
        get length() { return Object.keys(store).length; },
        key: (i: number) => Object.keys(store)[i] ?? null,
    } as Storage;
})();

if (typeof globalThis.sessionStorage === 'undefined') {
    Object.defineProperty(globalThis, 'sessionStorage', { value: storageStub, writable: true });
}
if (typeof globalThis.localStorage === 'undefined') {
    Object.defineProperty(globalThis, 'localStorage', { value: storageStub, writable: true });
}

describe('ProviderState', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        providerState.selectedProvider = null;
        providerState.providers = [];
    });

    describe('getLLMHeaders', () => {
        it('returns undefined when no provider selected', () => {
            expect(providerState.getLLMHeaders()).toBeUndefined();
        });

        it('returns provider name when selected without key', () => {
            providerState.selectedProvider = 'openai';
            const headers = providerState.getLLMHeaders();
            expect(headers).toEqual({ provider: 'openai' });
        });
    });

    describe('selectProvider', () => {
        it('sets selectedProvider', () => {
            providerState.selectProvider('anthropic');
            expect(providerState.selectedProvider).toBe('anthropic');
        });

        it('clears selectedProvider with null', () => {
            providerState.selectedProvider = 'openai';
            providerState.selectProvider(null);
            expect(providerState.selectedProvider).toBeNull();
        });
    });

    describe('activeProvider', () => {
        const mockProviders: ProviderInfo[] = [
            { name: 'claude-cli', display_name: 'Claude CLI', model: 'claude', available: true, is_default: true, requires_api_key: false, models: [] },
            { name: 'openai', display_name: 'OpenAI', model: 'gpt-4', available: false, is_default: false, requires_api_key: true, models: [] },
        ];

        it('returns default provider when none selected', () => {
            providerState.providers = mockProviders;
            expect(providerState.activeProvider?.name).toBe('claude-cli');
        });

        it('returns selected provider when one is chosen', () => {
            providerState.providers = mockProviders;
            providerState.selectedProvider = 'openai';
            expect(providerState.activeProvider?.name).toBe('openai');
        });

        it('returns null when selected provider not in list', () => {
            providerState.providers = mockProviders;
            providerState.selectedProvider = 'nonexistent';
            expect(providerState.activeProvider).toBeNull();
        });
    });

    describe('isEffectivelyAvailable', () => {
        it('returns true for available provider', () => {
            providerState.providers = [
                { name: 'claude-cli', display_name: 'Claude', model: 'm', available: true, is_default: true, requires_api_key: false, models: [] },
            ];
            expect(providerState.isEffectivelyAvailable('claude-cli')).toBe(true);
        });

        it('returns false for unknown provider', () => {
            providerState.providers = [];
            expect(providerState.isEffectivelyAvailable('unknown')).toBe(false);
        });

        it('returns true for unavailable provider with API key', () => {
            providerState.providers = [
                { name: 'openai', display_name: 'OpenAI', model: 'm', available: false, is_default: false, requires_api_key: true, models: [] },
            ];
            providerState.apiKeys = { openai: '***1234' };
            expect(providerState.isEffectivelyAvailable('openai')).toBe(true);
        });
    });

    describe('availableProviders', () => {
        it('filters to available providers and those with keys', () => {
            providerState.providers = [
                { name: 'a', display_name: 'A', model: 'm', available: true, is_default: true, requires_api_key: false, models: [] },
                { name: 'b', display_name: 'B', model: 'm', available: false, is_default: false, requires_api_key: true, models: [] },
                { name: 'c', display_name: 'C', model: 'm', available: false, is_default: false, requires_api_key: true, models: [] },
            ];
            providerState.apiKeys = { b: '***key' };

            const available = providerState.availableProviders;
            expect(available.map(p => p.name)).toEqual(['a', 'b']);
        });
    });
});
