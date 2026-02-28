import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock the API_BASE import
vi.mock("$lib/api/client", () => ({
	API_BASE: "http://localhost:8000",
}));

describe("AppSettingsService", () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	it("should export appSettings", async () => {
		const { appSettings } = await import("./appSettings.svelte");
		expect(appSettings).toBeDefined();
		expect(typeof appSettings.load).toBe("function");
		expect(typeof appSettings.save).toBe("function");
		expect(typeof appSettings.reset).toBe("function");
		expect(typeof appSettings.get).toBe("function");
	});

	it("get returns empty object for unknown app", async () => {
		const { appSettings } = await import("./appSettings.svelte");
		const result = appSettings.get("unknown-app");
		expect(result).toEqual({});
	});

	it("isLoading returns false initially", async () => {
		const { appSettings } = await import("./appSettings.svelte");
		expect(appSettings.isLoading("test-app")).toBe(false);
	});
});
