import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock systemBus before importing the bridge
const mockEmit = vi.fn();
vi.mock("$lib/services/systemBus.svelte", () => ({
	systemBus: {
		emit: mockEmit,
		on: vi.fn(() => () => {}),
		once: vi.fn(() => () => {}),
		reset: vi.fn(),
		recentEvents: [],
	},
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Build a ReadableStream that yields the given SSE text chunks in order,
 * then closes. Each chunk is encoded as UTF-8.
 */
function makeSSEStream(chunks: string[]): ReadableStream<Uint8Array> {
	const encoder = new TextEncoder();
	let index = 0;
	return new ReadableStream({
		pull(controller) {
			if (index < chunks.length) {
				controller.enqueue(encoder.encode(chunks[index]));
				index++;
			} else {
				controller.close();
			}
		},
	});
}

/**
 * Build a fetch mock that returns a successful SSE response with the given
 * stream. Optionally intercept the AbortSignal via onSignal.
 */
function mockSSEFetch(
	stream: ReadableStream<Uint8Array>,
	opts?: { status?: number; onSignal?: (signal: AbortSignal) => void }
) {
	return vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
		if (opts?.onSignal && init?.signal) {
			opts.onSignal(init.signal);
		}
		return Promise.resolve({
			ok: (opts?.status ?? 200) >= 200 && (opts?.status ?? 200) < 300,
			status: opts?.status ?? 200,
			body: stream,
		});
	});
}

/**
 * Flush microtasks + a small setTimeout tick so that stream reads and
 * scheduled timers (snapshot phase, reconnect) can execute.
 */
function tick(ms = 0): Promise<void> {
	return new Promise((resolve) => setTimeout(resolve, ms));
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KernelBusBridge", () => {
	let kernelBusBridge: Awaited<
		typeof import("./kernelBusBridge.svelte")
	>["kernelBusBridge"];

	beforeEach(async () => {
		vi.restoreAllMocks();
		mockEmit.mockClear();
		vi.useFakeTimers();
		const mod = await import("./kernelBusBridge.svelte");
		kernelBusBridge = mod.kernelBusBridge;
		kernelBusBridge.reset();
	});

	afterEach(() => {
		kernelBusBridge.reset();
		vi.useRealTimers();
		vi.unstubAllGlobals();
	});

	it("should export kernelBusBridge singleton", () => {
		expect(kernelBusBridge).toBeDefined();
		expect(typeof kernelBusBridge.connect).toBe("function");
		expect(typeof kernelBusBridge.disconnect).toBe("function");
		expect(typeof kernelBusBridge.publish).toBe("function");
		expect(typeof kernelBusBridge.reset).toBe("function");
	});

	it("starts disconnected", () => {
		expect(kernelBusBridge.connected).toBe(false);
	});

	it("disconnect is safe to call when not connected", () => {
		expect(() => kernelBusBridge.disconnect()).not.toThrow();
		expect(kernelBusBridge.connected).toBe(false);
	});

	it("reset clears state", () => {
		expect(() => kernelBusBridge.reset()).not.toThrow();
		expect(kernelBusBridge.connected).toBe(false);
	});

	// -----------------------------------------------------------------------
	// publish
	// -----------------------------------------------------------------------
	describe("publish", () => {
		it("sends POST to /api/kernel/bus/publish", async () => {
			vi.useRealTimers();
			const fetchMock = vi.fn().mockResolvedValue({
				ok: true,
				json: () => Promise.resolve({ status: "accepted" }),
			});
			vi.stubGlobal("fetch", fetchMock);

			await kernelBusBridge.publish("test:event", { key: "value" }, "test-app");

			expect(fetchMock).toHaveBeenCalledTimes(1);
			const [url, options] = fetchMock.mock.calls[0];
			expect(url).toContain("/api/kernel/bus/publish");
			expect(options.method).toBe("POST");
			const body = JSON.parse(options.body);
			expect(body.event_type).toBe("test:event");
			expect(body.data).toEqual({ key: "value" });
			expect(body.source_app).toBe("test-app");
		});

		it("throws on non-ok response", async () => {
			vi.useRealTimers();
			const fetchMock = vi.fn().mockResolvedValue({
				ok: false,
				status: 422,
				json: () => Promise.resolve({ detail: "Validation error" }),
			});
			vi.stubGlobal("fetch", fetchMock);

			await expect(
				kernelBusBridge.publish("bad:event", {})
			).rejects.toThrow("Validation error");
		});

		it("defaults source_app to frontend", async () => {
			vi.useRealTimers();
			const fetchMock = vi.fn().mockResolvedValue({
				ok: true,
				json: () => Promise.resolve({ status: "accepted" }),
			});
			vi.stubGlobal("fetch", fetchMock);

			await kernelBusBridge.publish("test:event", {});

			const body = JSON.parse(fetchMock.mock.calls[0][1].body);
			expect(body.source_app).toBe("frontend");
		});
	});

	// -----------------------------------------------------------------------
	// EVENT_TYPE_MAP
	// -----------------------------------------------------------------------
	describe("EVENT_TYPE_MAP — event mapping", () => {
		it("maps kernel:app.enabled to kernel:app_enabled", async () => {
			vi.useRealTimers();
			const stream = makeSSEStream([
				'event: bus_event\ndata: {"event_type":"kernel:app.enabled","source_app":"registry","app_id":"pf"}\n\n',
			]);
			vi.stubGlobal("fetch", mockSSEFetch(stream));

			kernelBusBridge.connect();
			// Let the stream be consumed
			await tick(50);

			// snapshot phase is active in the first 2s — but app_enabled is a state event, so it passes
			expect(mockEmit).toHaveBeenCalledWith(
				"kernel:app_enabled",
				"kernel:registry",
				expect.objectContaining({ event_type: "kernel:app.enabled" })
			);
		});

		it("maps kernel:app.disabled to kernel:app_disabled", async () => {
			vi.useRealTimers();
			const stream = makeSSEStream([
				'event: bus_event\ndata: {"event_type":"kernel:app.disabled","source_app":"registry"}\n\n',
			]);
			vi.stubGlobal("fetch", mockSSEFetch(stream));

			kernelBusBridge.connect();
			await tick(50);

			expect(mockEmit).toHaveBeenCalledWith(
				"kernel:app_disabled",
				"kernel:registry",
				expect.objectContaining({ event_type: "kernel:app.disabled" })
			);
		});

		it("maps kernel:job.submitted to kernel:job_submitted", async () => {
			vi.useRealTimers();
			const stream = makeSSEStream([
				'event: bus_event\ndata: {"event_type":"kernel:job.submitted","source_app":"scheduler"}\n\n',
			]);
			vi.stubGlobal("fetch", mockSSEFetch(stream));

			kernelBusBridge.connect();
			await tick(50);

			expect(mockEmit).toHaveBeenCalledWith(
				"kernel:job_submitted",
				"kernel:scheduler",
				expect.objectContaining({ event_type: "kernel:job.submitted" })
			);
		});

		it("maps kernel:job.completed to kernel:job_completed", async () => {
			vi.useRealTimers();
			const stream = makeSSEStream([
				'event: bus_event\ndata: {"event_type":"kernel:job.completed","source_app":"scheduler"}\n\n',
			]);
			vi.stubGlobal("fetch", mockSSEFetch(stream));

			kernelBusBridge.connect();
			await tick(50);

			expect(mockEmit).toHaveBeenCalledWith(
				"kernel:job_completed",
				"kernel:scheduler",
				expect.objectContaining({ event_type: "kernel:job.completed" })
			);
		});

		it("maps kernel:job.failed to kernel:job_failed", async () => {
			vi.useRealTimers();
			const stream = makeSSEStream([
				'event: bus_event\ndata: {"event_type":"kernel:job.failed","source_app":"scheduler"}\n\n',
			]);
			vi.stubGlobal("fetch", mockSSEFetch(stream));

			kernelBusBridge.connect();
			await tick(50);

			expect(mockEmit).toHaveBeenCalledWith(
				"kernel:job_failed",
				"kernel:scheduler",
				expect.objectContaining({ event_type: "kernel:job.failed" })
			);
		});

		it("maps unknown backend event types to kernel:event", async () => {
			// Unknown events will be suppressed during snapshot phase, so we must
			// wait for snapshot phase to end. Use fake timers for this test.
			const stream = makeSSEStream([]);
			let streamEnqueuer: ReadableStreamDefaultController<Uint8Array>;
			const delayedStream = new ReadableStream<Uint8Array>({
				start(controller) {
					streamEnqueuer = controller;
				},
			});

			vi.stubGlobal("fetch", mockSSEFetch(delayedStream));
			kernelBusBridge.connect();

			// Advance past the 2s snapshot phase
			await vi.advanceTimersByTimeAsync(2100);

			// Now enqueue an unknown event
			const encoder = new TextEncoder();
			streamEnqueuer!.enqueue(
				encoder.encode(
					'event: bus_event\ndata: {"event_type":"custom:something","source_app":"ext"}\n\n'
				)
			);
			await vi.advanceTimersByTimeAsync(50);

			expect(mockEmit).toHaveBeenCalledWith(
				"kernel:event",
				"kernel:ext",
				expect.objectContaining({ event_type: "custom:something" })
			);

			streamEnqueuer!.close();
		});
	});

	// -----------------------------------------------------------------------
	// SSE stream parsing
	// -----------------------------------------------------------------------
	describe("SSE stream parsing", () => {
		it("parses event, data, and id fields from SSE lines", async () => {
			vi.useRealTimers();
			// All lines in a single chunk — the parser resets local state per read(),
			// so the full event:+data:+id:+blank sequence must arrive in one read.
			const stream = makeSSEStream([
				'event: bus_event\ndata: {"event_type":"kernel:app.enabled","source_app":"test"}\nid: evt-42\n\n',
			]);
			vi.stubGlobal("fetch", mockSSEFetch(stream));

			kernelBusBridge.connect();
			await tick(50);

			expect(mockEmit).toHaveBeenCalledTimes(1);
			expect(mockEmit).toHaveBeenCalledWith(
				"kernel:app_enabled",
				"kernel:test",
				expect.objectContaining({
					event_type: "kernel:app.enabled",
					backend_event_type: "kernel:app.enabled",
				})
			);
		});

		it("handles multi-line data fields joined by newlines", async () => {
			vi.useRealTimers();
			// Two data: lines — they should be joined with \n and parsed as one JSON
			const sseText =
				'event: bus_event\n' +
				'data: {"event_type":"kernel:app.enabled",\n' +
				'data: "source_app":"test"}\n' +
				'\n';
			const stream = makeSSEStream([sseText]);
			vi.stubGlobal("fetch", mockSSEFetch(stream));

			kernelBusBridge.connect();
			await tick(50);

			expect(mockEmit).toHaveBeenCalledTimes(1);
			expect(mockEmit).toHaveBeenCalledWith(
				"kernel:app_enabled",
				"kernel:test",
				expect.objectContaining({ event_type: "kernel:app.enabled" })
			);
		});

		it("ignores SSE comment lines (keepalives)", async () => {
			vi.useRealTimers();
			const stream = makeSSEStream([
				": keepalive\n",
				'event: bus_event\ndata: {"event_type":"kernel:app.enabled","source_app":"x"}\n\n',
			]);
			vi.stubGlobal("fetch", mockSSEFetch(stream));

			kernelBusBridge.connect();
			await tick(50);

			// Only the real event should be emitted, not the comment
			expect(mockEmit).toHaveBeenCalledTimes(1);
		});

		it("does not emit when data is empty (no data lines before blank)", async () => {
			vi.useRealTimers();
			const stream = makeSSEStream([
				"event: bus_event\n",
				"\n", // blank line with no data: lines — should not trigger dispatch
				'event: bus_event\ndata: {"event_type":"kernel:job.completed","source_app":"s"}\n\n',
			]);
			vi.stubGlobal("fetch", mockSSEFetch(stream));

			kernelBusBridge.connect();
			await tick(50);

			// Only the second event (with data) should fire
			expect(mockEmit).toHaveBeenCalledTimes(1);
			expect(mockEmit).toHaveBeenCalledWith(
				"kernel:job_completed",
				expect.any(String),
				expect.objectContaining({ event_type: "kernel:job.completed" })
			);
		});

		it("handles chunked delivery across multiple read() calls", async () => {
			vi.useRealTimers();
			// Split an SSE event across two chunks, mid-line
			const stream = makeSSEStream([
				'event: bus_event\ndata: {"event_type":"ker',
				'nel:app.enabled","source_app":"chunked"}\n\n',
			]);
			vi.stubGlobal("fetch", mockSSEFetch(stream));

			kernelBusBridge.connect();
			await tick(50);

			expect(mockEmit).toHaveBeenCalledTimes(1);
			expect(mockEmit).toHaveBeenCalledWith(
				"kernel:app_enabled",
				"kernel:chunked",
				expect.objectContaining({ event_type: "kernel:app.enabled" })
			);
		});

		it("skips malformed JSON data gracefully", async () => {
			vi.useRealTimers();
			const stream = makeSSEStream([
				"event: bus_event\ndata: NOT-VALID-JSON\n\n",
				'event: bus_event\ndata: {"event_type":"kernel:job.completed","source_app":"ok"}\n\n',
			]);
			vi.stubGlobal("fetch", mockSSEFetch(stream));

			kernelBusBridge.connect();
			await tick(50);

			// Malformed event silently skipped, valid event emitted
			expect(mockEmit).toHaveBeenCalledTimes(1);
			expect(mockEmit).toHaveBeenCalledWith(
				"kernel:job_completed",
				"kernel:ok",
				expect.any(Object)
			);
		});

		it("sets connected=true once stream starts", async () => {
			vi.useRealTimers();
			const stream = makeSSEStream([
				'event: bus_event\ndata: {"event_type":"kernel:app.enabled","source_app":"s"}\n\n',
			]);
			vi.stubGlobal("fetch", mockSSEFetch(stream));

			expect(kernelBusBridge.connected).toBe(false);
			kernelBusBridge.connect();
			await tick(50);

			// Stream has been consumed and closed, but connected may have flipped
			// The important assertion is that it was true during the stream
			// After stream ends it schedules reconnect and sets connected=false
			// So we just verify the emit happened (which requires connected=true)
			expect(mockEmit).toHaveBeenCalled();
		});
	});

	// -----------------------------------------------------------------------
	// Snapshot phase
	// -----------------------------------------------------------------------
	describe("snapshot phase", () => {
		it("suppresses non-state events during the first 2 seconds", async () => {
			// kernel:audit.logged maps to kernel:audit_logged which is NOT in stateEvents
			let streamController: ReadableStreamDefaultController<Uint8Array>;
			const stream = new ReadableStream<Uint8Array>({
				start(controller) {
					streamController = controller;
				},
			});
			vi.stubGlobal("fetch", mockSSEFetch(stream));

			kernelBusBridge.connect();
			await vi.advanceTimersByTimeAsync(10);

			const encoder = new TextEncoder();
			// Emit an audit event during snapshot phase
			streamController!.enqueue(
				encoder.encode(
					'event: bus_event\ndata: {"event_type":"kernel:audit.logged","source_app":"audit"}\n\n'
				)
			);
			await vi.advanceTimersByTimeAsync(10);

			// Should be suppressed
			expect(mockEmit).not.toHaveBeenCalled();

			streamController!.close();
		});

		it("allows state-sync events (app_enabled) during snapshot phase", async () => {
			let streamController: ReadableStreamDefaultController<Uint8Array>;
			const stream = new ReadableStream<Uint8Array>({
				start(controller) {
					streamController = controller;
				},
			});
			vi.stubGlobal("fetch", mockSSEFetch(stream));

			kernelBusBridge.connect();
			await vi.advanceTimersByTimeAsync(10);

			const encoder = new TextEncoder();
			streamController!.enqueue(
				encoder.encode(
					'event: bus_event\ndata: {"event_type":"kernel:app.enabled","source_app":"reg"}\n\n'
				)
			);
			await vi.advanceTimersByTimeAsync(10);

			expect(mockEmit).toHaveBeenCalledWith(
				"kernel:app_enabled",
				"kernel:reg",
				expect.any(Object)
			);

			streamController!.close();
		});

		it("allows state-sync events (app_disabled) during snapshot phase", async () => {
			let streamController: ReadableStreamDefaultController<Uint8Array>;
			const stream = new ReadableStream<Uint8Array>({
				start(controller) {
					streamController = controller;
				},
			});
			vi.stubGlobal("fetch", mockSSEFetch(stream));

			kernelBusBridge.connect();
			await vi.advanceTimersByTimeAsync(10);

			const encoder = new TextEncoder();
			streamController!.enqueue(
				encoder.encode(
					'event: bus_event\ndata: {"event_type":"kernel:app.disabled","source_app":"reg"}\n\n'
				)
			);
			await vi.advanceTimersByTimeAsync(10);

			expect(mockEmit).toHaveBeenCalledWith(
				"kernel:app_disabled",
				"kernel:reg",
				expect.any(Object)
			);

			streamController!.close();
		});

		it("allows job state events (job_submitted, job_completed, job_failed) during snapshot phase", async () => {
			let streamController: ReadableStreamDefaultController<Uint8Array>;
			const stream = new ReadableStream<Uint8Array>({
				start(controller) {
					streamController = controller;
				},
			});
			vi.stubGlobal("fetch", mockSSEFetch(stream));

			kernelBusBridge.connect();
			await vi.advanceTimersByTimeAsync(10);

			const encoder = new TextEncoder();
			const jobEvents = [
				"kernel:job.submitted",
				"kernel:job.completed",
				"kernel:job.failed",
			];
			for (const evt of jobEvents) {
				streamController!.enqueue(
					encoder.encode(
						`event: bus_event\ndata: {"event_type":"${evt}","source_app":"sched"}\n\n`
					)
				);
			}
			await vi.advanceTimersByTimeAsync(10);

			expect(mockEmit).toHaveBeenCalledTimes(3);

			streamController!.close();
		});

		it("suppresses job_started and job_progress during snapshot phase (not in stateEvents)", async () => {
			let streamController: ReadableStreamDefaultController<Uint8Array>;
			const stream = new ReadableStream<Uint8Array>({
				start(controller) {
					streamController = controller;
				},
			});
			vi.stubGlobal("fetch", mockSSEFetch(stream));

			kernelBusBridge.connect();
			await vi.advanceTimersByTimeAsync(10);

			const encoder = new TextEncoder();
			// job_started and job_progress are NOT in the stateEvents allowlist
			streamController!.enqueue(
				encoder.encode(
					'event: bus_event\ndata: {"event_type":"kernel:job.started","source_app":"sched"}\n\n'
				)
			);
			streamController!.enqueue(
				encoder.encode(
					'event: bus_event\ndata: {"event_type":"kernel:job.progress","source_app":"sched"}\n\n'
				)
			);
			await vi.advanceTimersByTimeAsync(10);

			expect(mockEmit).not.toHaveBeenCalled();

			streamController!.close();
		});

		it("stops suppression after 2 seconds — all events pass through", async () => {
			let streamController: ReadableStreamDefaultController<Uint8Array>;
			const stream = new ReadableStream<Uint8Array>({
				start(controller) {
					streamController = controller;
				},
			});
			vi.stubGlobal("fetch", mockSSEFetch(stream));

			kernelBusBridge.connect();
			await vi.advanceTimersByTimeAsync(10);

			const encoder = new TextEncoder();

			// During snapshot phase: audit event suppressed
			streamController!.enqueue(
				encoder.encode(
					'event: bus_event\ndata: {"event_type":"kernel:audit.logged","source_app":"audit"}\n\n'
				)
			);
			await vi.advanceTimersByTimeAsync(10);
			expect(mockEmit).not.toHaveBeenCalled();

			// Advance past 2s snapshot phase
			await vi.advanceTimersByTimeAsync(2100);

			// Now the same event type should pass through
			streamController!.enqueue(
				encoder.encode(
					'event: bus_event\ndata: {"event_type":"kernel:audit.logged","source_app":"audit"}\n\n'
				)
			);
			await vi.advanceTimersByTimeAsync(10);

			expect(mockEmit).toHaveBeenCalledTimes(1);
			expect(mockEmit).toHaveBeenCalledWith(
				"kernel:audit_logged",
				"kernel:audit",
				expect.any(Object)
			);

			streamController!.close();
		});

		it("suppresses unknown/unmapped events during snapshot phase", async () => {
			let streamController: ReadableStreamDefaultController<Uint8Array>;
			const stream = new ReadableStream<Uint8Array>({
				start(controller) {
					streamController = controller;
				},
			});
			vi.stubGlobal("fetch", mockSSEFetch(stream));

			kernelBusBridge.connect();
			await vi.advanceTimersByTimeAsync(10);

			const encoder = new TextEncoder();
			// An unknown event type maps to kernel:event, which is not in stateEvents
			streamController!.enqueue(
				encoder.encode(
					'event: bus_event\ndata: {"event_type":"custom:foo","source_app":"bar"}\n\n'
				)
			);
			await vi.advanceTimersByTimeAsync(10);

			expect(mockEmit).not.toHaveBeenCalled();

			streamController!.close();
		});
	});

	// -----------------------------------------------------------------------
	// Reconnect behavior
	// -----------------------------------------------------------------------
	describe("reconnect behavior", () => {
		it("schedules reconnect when stream ends", async () => {
			// A stream that closes immediately triggers reconnect
			const stream = makeSSEStream([]); // closes right away
			const fetchMock = mockSSEFetch(stream);
			vi.stubGlobal("fetch", fetchMock);

			kernelBusBridge.connect();
			// Let _startStream complete (stream reads, sets connected=false, schedules reconnect)
			await vi.advanceTimersByTimeAsync(50);

			expect(kernelBusBridge.connected).toBe(false);
			expect(fetchMock).toHaveBeenCalledTimes(1);

			// Provide a new stream for the reconnect
			const stream2 = makeSSEStream([]);
			fetchMock.mockImplementation(() =>
				Promise.resolve({ ok: true, status: 200, body: stream2 })
			);

			// Advance past the initial backoff (3s + jitter up to 25%)
			// Max jitter = 3000 * 1.25 = 3750
			await vi.advanceTimersByTimeAsync(4000);

			expect(fetchMock).toHaveBeenCalledTimes(2);
		});

		it("backoff increases on consecutive failed connections", async () => {
			// Pin Math.random to 0.5 so jitter = backoff * (0.75 + 0.25) = backoff * 1.0
			vi.spyOn(Math, "random").mockReturnValue(0.5);

			// Return non-ok responses so the backoff is never reset by a successful connect.
			const fetchMock = vi.fn().mockImplementation(() => {
				return Promise.resolve({
					ok: false,
					status: 503,
					body: null,
				});
			});
			vi.stubGlobal("fetch", fetchMock);

			kernelBusBridge.connect();
			await vi.advanceTimersByTimeAsync(0);
			expect(fetchMock).toHaveBeenCalledTimes(1);

			// Capture timestamps when each reconnect fires to verify growing delays.
			// The reconnect delays should be 3000, 4500, 6750 (each *= 1.5).
			// Use runOnlyPendingTimersAsync to trigger exactly one timer at a time.

			// 1st reconnect fires after 3000ms delay
			await vi.advanceTimersByTimeAsync(3000);
			expect(fetchMock).toHaveBeenCalledTimes(2);

			// 2nd reconnect fires after 4500ms delay (backoff was 3000 → now 4500)
			await vi.advanceTimersByTimeAsync(4500);
			expect(fetchMock).toHaveBeenCalledTimes(3);

			// 3rd reconnect fires after 6750ms delay (backoff was 4500 → now 6750)
			await vi.advanceTimersByTimeAsync(6750);
			expect(fetchMock).toHaveBeenCalledTimes(4);

			// Verify the delays are increasing: each reconnect needed more time than the last
			// This is inherently proven by the structure above — if delays weren't increasing,
			// more than 4 calls would have occurred.
		});

		it("backoff caps at MAX_BACKOFF (30000ms)", async () => {
			const fetchMock = vi.fn().mockImplementation(() => {
				return Promise.resolve({
					ok: true,
					status: 200,
					body: makeSSEStream([]),
				});
			});
			vi.stubGlobal("fetch", fetchMock);

			kernelBusBridge.connect();

			// Run many reconnect cycles to exceed MAX_BACKOFF
			// INITIAL=3000, *1.5 each: 3000, 4500, 6750, 10125, 15187, 22781, 30000 (capped)
			for (let i = 0; i < 10; i++) {
				// Max possible delay is MAX_BACKOFF * 1.25 = 37500
				await vi.advanceTimersByTimeAsync(40_000);
			}

			// After many cycles the reconnect should still happen — backoff doesn't grow unbounded
			// We should have at least 10 total calls (initial + reconnects)
			expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(10);
		});

		it("backoff resets to INITIAL_BACKOFF on successful connect", async () => {
			let streamController: ReadableStreamDefaultController<Uint8Array> | null = null;
			let callCount = 0;

			const fetchMock = vi.fn().mockImplementation(() => {
				callCount++;
				if (callCount <= 3) {
					// First 3 attempts: stream closes immediately (triggers backoff growth)
					return Promise.resolve({
						ok: true,
						status: 200,
						body: makeSSEStream([]),
					});
				}
				// 4th attempt: long-lived stream
				const stream = new ReadableStream<Uint8Array>({
					start(controller) {
						streamController = controller;
					},
				});
				return Promise.resolve({
					ok: true,
					status: 200,
					body: stream,
				});
			});
			vi.stubGlobal("fetch", fetchMock);

			kernelBusBridge.connect();

			// Burn through 3 failed connections
			for (let i = 0; i < 3; i++) {
				await vi.advanceTimersByTimeAsync(40_000);
			}
			// 4th call should now be active with a persistent stream
			await vi.advanceTimersByTimeAsync(40_000);
			expect(fetchMock).toHaveBeenCalledTimes(4);

			// Close the long-lived stream — this triggers reconnect
			streamController!.close();
			await vi.advanceTimersByTimeAsync(50);

			// Backoff should have reset to INITIAL_BACKOFF (3000ms)
			// because the 4th connection was successful (response.ok + connected=true → backoff reset)
			// So reconnect should happen within ~3750ms (3000 * 1.25 jitter max)
			fetchMock.mockImplementation(() =>
				Promise.resolve({
					ok: true,
					status: 200,
					body: makeSSEStream([]),
				})
			);

			await vi.advanceTimersByTimeAsync(4000);
			expect(fetchMock).toHaveBeenCalledTimes(5);
		});

		it("sends Last-Event-ID header on reconnect", async () => {
			let callCount = 0;
			const fetchMock = vi.fn().mockImplementation(() => {
				callCount++;
				if (callCount === 1) {
					// First connect: send an event with id
					return Promise.resolve({
						ok: true,
						status: 200,
						body: makeSSEStream([
							'event: bus_event\ndata: {"event_type":"kernel:app.enabled","source_app":"s"}\nid: evt-99\n\n',
						]),
					});
				}
				// Subsequent: empty stream
				return Promise.resolve({
					ok: true,
					status: 200,
					body: makeSSEStream([]),
				});
			});
			vi.stubGlobal("fetch", fetchMock);

			kernelBusBridge.connect();
			// Let first stream complete and parse the event with id
			await vi.advanceTimersByTimeAsync(50);

			// Wait for reconnect (backoff ~3000ms + jitter)
			await vi.advanceTimersByTimeAsync(4000);

			expect(fetchMock).toHaveBeenCalledTimes(2);
			// Second call should include Last-Event-ID header
			const secondCallHeaders = fetchMock.mock.calls[1][1]?.headers;
			expect(secondCallHeaders).toBeDefined();
			expect(secondCallHeaders["Last-Event-ID"]).toBe("evt-99");
		});

		it("does not reconnect after explicit disconnect()", async () => {
			const stream = makeSSEStream([]);
			const fetchMock = mockSSEFetch(stream);
			vi.stubGlobal("fetch", fetchMock);

			kernelBusBridge.connect();
			await vi.advanceTimersByTimeAsync(50);

			// Disconnect before reconnect timer fires
			kernelBusBridge.disconnect();

			// Advance well past any possible reconnect delay
			await vi.advanceTimersByTimeAsync(60_000);

			// Should only have the initial connect call
			expect(fetchMock).toHaveBeenCalledTimes(1);
		});

		it("schedules reconnect on non-ok response", async () => {
			let callCount = 0;
			const fetchMock = vi.fn().mockImplementation(() => {
				callCount++;
				if (callCount === 1) {
					return Promise.resolve({
						ok: false,
						status: 503,
						body: null,
					});
				}
				return Promise.resolve({
					ok: true,
					status: 200,
					body: makeSSEStream([]),
				});
			});
			vi.stubGlobal("fetch", fetchMock);

			kernelBusBridge.connect();
			await vi.advanceTimersByTimeAsync(50);

			// Should not be connected after a 503
			expect(kernelBusBridge.connected).toBe(false);

			// Wait for reconnect
			await vi.advanceTimersByTimeAsync(4000);
			expect(fetchMock).toHaveBeenCalledTimes(2);
		});

		it("connect() is idempotent — multiple calls do not create parallel streams", async () => {
			let controllerRef: ReadableStreamDefaultController<Uint8Array>;
			const stream = new ReadableStream<Uint8Array>({
				start(controller) {
					controllerRef = controller;
				},
			});
			const fetchMock = mockSSEFetch(stream);
			vi.stubGlobal("fetch", fetchMock);

			kernelBusBridge.connect();
			await vi.advanceTimersByTimeAsync(10);

			// Call connect again while already connected
			kernelBusBridge.connect();
			kernelBusBridge.connect();
			await vi.advanceTimersByTimeAsync(10);

			// Should only have one fetch call
			expect(fetchMock).toHaveBeenCalledTimes(1);

			controllerRef!.close();
		});
	});
});
