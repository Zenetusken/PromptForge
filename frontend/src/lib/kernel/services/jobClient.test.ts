import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("$lib/kernel/utils/errors", () => ({
	throwIfNotOk: vi.fn(),
}));

describe("jobClient", () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	it("submitJob calls POST /api/kernel/jobs/submit", async () => {
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: () =>
				Promise.resolve({
					job_id: "j1",
					status: "pending",
					job: null,
				}),
		});
		vi.stubGlobal("fetch", fetchMock);

		const { submitJob } = await import("./jobClient");
		const result = await submitJob("test-app", "echo", { msg: "hi" });
		expect(result.job_id).toBe("j1");

		const [url, options] = fetchMock.mock.calls[0];
		expect(url).toContain("/api/kernel/jobs/submit");
		expect(options.method).toBe("POST");
		const body = JSON.parse(options.body);
		expect(body.app_id).toBe("test-app");
		expect(body.job_type).toBe("echo");

		vi.unstubAllGlobals();
	});

	it("getJob calls GET /api/kernel/jobs/{id}", async () => {
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: () =>
				Promise.resolve({ id: "j1", status: "completed" }),
		});
		vi.stubGlobal("fetch", fetchMock);

		const { getJob } = await import("./jobClient");
		const result = await getJob("j1");
		expect(result.status).toBe("completed");
		expect(fetchMock.mock.calls[0][0]).toContain("/api/kernel/jobs/j1");

		vi.unstubAllGlobals();
	});

	it("cancelJob calls POST /api/kernel/jobs/{id}/cancel", async () => {
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: () => Promise.resolve({ job_id: "j1", status: "cancelled" }),
		});
		vi.stubGlobal("fetch", fetchMock);

		const { cancelJob } = await import("./jobClient");
		const result = await cancelJob("j1");
		expect(result.status).toBe("cancelled");

		const [url, options] = fetchMock.mock.calls[0];
		expect(url).toContain("/api/kernel/jobs/j1/cancel");
		expect(options.method).toBe("POST");

		vi.unstubAllGlobals();
	});

	it("listJobs calls GET /api/kernel/jobs with query params", async () => {
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: () => Promise.resolve({ jobs: [], total: 0 }),
		});
		vi.stubGlobal("fetch", fetchMock);

		const { listJobs } = await import("./jobClient");
		const result = await listJobs({
			app_id: "promptforge",
			status: "running",
		});
		expect(result.jobs).toEqual([]);

		const url = fetchMock.mock.calls[0][0] as string;
		expect(url).toContain("app_id=promptforge");
		expect(url).toContain("status=running");

		vi.unstubAllGlobals();
	});
});
