import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("$lib/kernel/utils/errors", () => ({
	throwIfNotOk: vi.fn(),
}));

describe("appManagerClient", () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	it("fetchApps calls GET /api/kernel/apps", async () => {
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: () => Promise.resolve({ apps: [] }),
		});
		vi.stubGlobal("fetch", fetchMock);

		const { fetchApps } = await import("./appManagerClient");
		const result = await fetchApps();
		expect(result.apps).toEqual([]);
		expect(fetchMock.mock.calls[0][0]).toContain("/api/kernel/apps");

		vi.unstubAllGlobals();
	});

	it("fetchAppStatus calls GET /api/kernel/apps/{id}/status", async () => {
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: () => Promise.resolve({ id: "pf", status: "ENABLED" }),
		});
		vi.stubGlobal("fetch", fetchMock);

		const { fetchAppStatus } = await import("./appManagerClient");
		const result = await fetchAppStatus("pf");
		expect(result.status).toBe("ENABLED");
		expect(fetchMock.mock.calls[0][0]).toContain("/api/kernel/apps/pf/status");

		vi.unstubAllGlobals();
	});

	it("enableApp calls POST /api/kernel/apps/{id}/enable", async () => {
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: () => Promise.resolve({}),
		});
		vi.stubGlobal("fetch", fetchMock);

		const { enableApp } = await import("./appManagerClient");
		await enableApp("textforge");

		const [url, options] = fetchMock.mock.calls[0];
		expect(url).toContain("/api/kernel/apps/textforge/enable");
		expect(options.method).toBe("POST");

		vi.unstubAllGlobals();
	});

	it("disableApp calls POST /api/kernel/apps/{id}/disable", async () => {
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: () => Promise.resolve({}),
		});
		vi.stubGlobal("fetch", fetchMock);

		const { disableApp } = await import("./appManagerClient");
		await disableApp("textforge");

		const [url, options] = fetchMock.mock.calls[0];
		expect(url).toContain("/api/kernel/apps/textforge/disable");
		expect(options.method).toBe("POST");

		vi.unstubAllGlobals();
	});
});
