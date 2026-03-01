import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("$lib/kernel/utils/errors", () => ({
	throwIfNotOk: vi.fn(),
}));

describe("auditClient", () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	it("fetchAuditLogs calls correct URL for all apps", async () => {
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: () => Promise.resolve({ logs: [], total: 0 }),
		});
		vi.stubGlobal("fetch", fetchMock);

		const { fetchAuditLogs } = await import("./auditClient");
		const result = await fetchAuditLogs();
		expect(result.logs).toEqual([]);
		expect(fetchMock.mock.calls[0][0]).toContain("/api/kernel/audit/all");

		vi.unstubAllGlobals();
	});

	it("fetchAuditLogs calls correct URL for specific app", async () => {
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: () => Promise.resolve({ logs: [], total: 0 }),
		});
		vi.stubGlobal("fetch", fetchMock);

		const { fetchAuditLogs } = await import("./auditClient");
		await fetchAuditLogs("promptforge");
		expect(fetchMock.mock.calls[0][0]).toContain("/api/kernel/audit/promptforge");

		vi.unstubAllGlobals();
	});

	it("fetchAuditSummary calls correct URL", async () => {
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: () => Promise.resolve({ summary: [] }),
		});
		vi.stubGlobal("fetch", fetchMock);

		const { fetchAuditSummary } = await import("./auditClient");
		const result = await fetchAuditSummary();
		expect(result.summary).toEqual([]);
		expect(fetchMock.mock.calls[0][0]).toContain("/api/kernel/audit/summary");

		vi.unstubAllGlobals();
	});

	it("fetchAllUsage calls correct URL", async () => {
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: () => Promise.resolve({ usage: [] }),
		});
		vi.stubGlobal("fetch", fetchMock);

		const { fetchAllUsage } = await import("./auditClient");
		const result = await fetchAllUsage();
		expect(result.usage).toEqual([]);
		expect(fetchMock.mock.calls[0][0]).toContain("/api/kernel/audit/usage");

		vi.unstubAllGlobals();
	});
});
