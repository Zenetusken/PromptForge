import { describe, it, expect, vi, beforeEach } from 'vitest';

const { mockShow } = vi.hoisted(() => ({ mockShow: vi.fn() }));

vi.mock('$lib/api/client', () => ({
    fetchHealth: vi.fn(),
    fetchProviders: vi.fn().mockResolvedValue([]),
    validateApiKey: vi.fn(),
}));

vi.mock('$lib/stores/toast.svelte', () => ({
    toastState: { show: mockShow },
}));

vi.mock('$lib/utils/format', () => ({
    maskApiKey: vi.fn((key: string) => '***' + key.slice(-4)),
}));

import { providerState } from './provider.svelte';
import { fetchHealth } from '$lib/api/client';
import type { HealthResponse, ProviderInfo } from '$lib/api/client';

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

    describe('MCP toast notifications', () => {
        const makeHealth = (mcp_connected: boolean): HealthResponse => ({
            status: 'ok',
            claude_available: true,
            llm_available: true,
            llm_provider: 'claude-cli',
            llm_model: 'claude-opus-4-6',
            db_connected: true,
            mcp_connected,
            version: '0.2.0',
        });

        beforeEach(() => {
            mockShow.mockClear();
            // Reset internal MCP tracking state by creating a fresh poll cycle
            // Access private fields via any cast for testing
            (providerState as any)._mcpFirstPoll = true;
            (providerState as any)._mcpPreviousState = null;
        });

        it('does not fire toast on initial health check', async () => {
            vi.mocked(fetchHealth).mockResolvedValueOnce(makeHealth(true));
            await providerState.pollHealth();
            expect(mockShow).not.toHaveBeenCalled();
        });

        it('fires error toast when MCP disconnects', async () => {
            // First poll — establishes baseline (no toast)
            vi.mocked(fetchHealth).mockResolvedValueOnce(makeHealth(true));
            await providerState.pollHealth();

            // Second poll — MCP goes down
            vi.mocked(fetchHealth).mockResolvedValueOnce(makeHealth(false));
            await providerState.pollHealth();

            expect(mockShow).toHaveBeenCalledWith('MCP server disconnected', 'error', 5000);
        });

        it('fires success toast when MCP reconnects', async () => {
            // First poll — MCP is down (no toast, first poll)
            vi.mocked(fetchHealth).mockResolvedValueOnce(makeHealth(false));
            await providerState.pollHealth();

            // Second poll — MCP comes up
            vi.mocked(fetchHealth).mockResolvedValueOnce(makeHealth(true));
            await providerState.pollHealth();

            expect(mockShow).toHaveBeenCalledWith('MCP server connected', 'success');
        });

        it('does not fire toast when MCP status unchanged', async () => {
            // First poll
            vi.mocked(fetchHealth).mockResolvedValueOnce(makeHealth(true));
            await providerState.pollHealth();

            // Second poll — same status
            vi.mocked(fetchHealth).mockResolvedValueOnce(makeHealth(true));
            await providerState.pollHealth();

            expect(mockShow).not.toHaveBeenCalled();
        });
    });
});
