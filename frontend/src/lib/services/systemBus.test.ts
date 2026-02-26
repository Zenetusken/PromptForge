import { describe, it, expect, beforeEach, vi } from 'vitest';
import { systemBus, type BusEvent, type BusEventType } from './systemBus.svelte';

describe('SystemBus', () => {
	beforeEach(() => {
		systemBus.reset();
	});

	describe('emit', () => {
		it('creates an event with correct fields', () => {
			const handler = vi.fn();
			systemBus.on('forge:started', handler);

			systemBus.emit('forge:started', 'test', { pid: 1 });

			expect(handler).toHaveBeenCalledOnce();
			const event: BusEvent = handler.mock.calls[0][0];
			expect(event.type).toBe('forge:started');
			expect(event.source).toBe('test');
			expect(event.payload).toEqual({ pid: 1 });
			expect(event.timestamp).toBeGreaterThan(0);
			expect(event.id).toMatch(/^evt_\d+$/);
		});

		it('uses empty payload when none provided', () => {
			const handler = vi.fn();
			systemBus.on('forge:completed', handler);

			systemBus.emit('forge:completed', 'test');

			expect(handler.mock.calls[0][0].payload).toEqual({});
		});

		it('fires all handlers for the event type', () => {
			const h1 = vi.fn();
			const h2 = vi.fn();
			systemBus.on('forge:started', h1);
			systemBus.on('forge:started', h2);

			systemBus.emit('forge:started', 'test');

			expect(h1).toHaveBeenCalledOnce();
			expect(h2).toHaveBeenCalledOnce();
		});

		it('does not fire handlers for other event types', () => {
			const handler = vi.fn();
			systemBus.on('forge:completed', handler);

			systemBus.emit('forge:started', 'test');

			expect(handler).not.toHaveBeenCalled();
		});

		it('continues calling handlers if one throws', () => {
			const h1 = vi.fn(() => { throw new Error('boom'); });
			const h2 = vi.fn();
			systemBus.on('forge:started', h1);
			systemBus.on('forge:started', h2);

			systemBus.emit('forge:started', 'test');

			expect(h1).toHaveBeenCalledOnce();
			expect(h2).toHaveBeenCalledOnce();
		});
	});

	describe('on', () => {
		it('returns an unsubscribe function', () => {
			const handler = vi.fn();
			const unsub = systemBus.on('forge:started', handler);

			systemBus.emit('forge:started', 'test');
			expect(handler).toHaveBeenCalledOnce();

			unsub();

			systemBus.emit('forge:started', 'test');
			expect(handler).toHaveBeenCalledOnce(); // no additional call
		});

		it('supports wildcard subscription', () => {
			const handler = vi.fn();
			systemBus.on('*', handler);

			systemBus.emit('forge:started', 'a');
			systemBus.emit('forge:completed', 'b');
			systemBus.emit('clipboard:copied', 'c');

			expect(handler).toHaveBeenCalledTimes(3);
			expect(handler.mock.calls[0][0].type).toBe('forge:started');
			expect(handler.mock.calls[1][0].type).toBe('forge:completed');
			expect(handler.mock.calls[2][0].type).toBe('clipboard:copied');
		});

		it('wildcard handler can be unsubscribed', () => {
			const handler = vi.fn();
			const unsub = systemBus.on('*', handler);

			systemBus.emit('forge:started', 'test');
			expect(handler).toHaveBeenCalledOnce();

			unsub();
			systemBus.emit('forge:started', 'test');
			expect(handler).toHaveBeenCalledOnce();
		});

		it('both type-specific and wildcard handlers fire', () => {
			const specific = vi.fn();
			const wildcard = vi.fn();
			systemBus.on('forge:started', specific);
			systemBus.on('*', wildcard);

			systemBus.emit('forge:started', 'test');

			expect(specific).toHaveBeenCalledOnce();
			expect(wildcard).toHaveBeenCalledOnce();
		});
	});

	describe('once', () => {
		it('fires handler only once', () => {
			const handler = vi.fn();
			systemBus.once('forge:started', handler);

			systemBus.emit('forge:started', 'test');
			systemBus.emit('forge:started', 'test');

			expect(handler).toHaveBeenCalledOnce();
		});

		it('returns unsubscribe that prevents the handler from firing', () => {
			const handler = vi.fn();
			const unsub = systemBus.once('forge:started', handler);

			unsub();
			systemBus.emit('forge:started', 'test');

			expect(handler).not.toHaveBeenCalled();
		});

		it('works with wildcard', () => {
			const handler = vi.fn();
			systemBus.once('*', handler);

			systemBus.emit('forge:started', 'a');
			systemBus.emit('forge:completed', 'b');

			expect(handler).toHaveBeenCalledOnce();
			expect(handler.mock.calls[0][0].type).toBe('forge:started');
		});
	});

	describe('recentEvents', () => {
		it('records emitted events', () => {
			systemBus.emit('forge:started', 'test', { n: 1 });
			systemBus.emit('forge:completed', 'test', { n: 2 });

			expect(systemBus.recentEvents).toHaveLength(2);
			// Most recent first
			expect(systemBus.recentEvents[0].type).toBe('forge:completed');
			expect(systemBus.recentEvents[1].type).toBe('forge:started');
		});

		it('caps at 50 entries', () => {
			for (let i = 0; i < 60; i++) {
				systemBus.emit('forge:started', 'test', { i });
			}
			expect(systemBus.recentEvents).toHaveLength(50);
			// Most recent is first
			expect(systemBus.recentEvents[0].payload.i).toBe(59);
		});
	});

	describe('reset', () => {
		it('clears all handlers and recent events', () => {
			const handler = vi.fn();
			systemBus.on('forge:started', handler);
			systemBus.emit('forge:started', 'test');

			systemBus.reset();

			expect(systemBus.recentEvents).toHaveLength(0);
			expect(systemBus.handlerCount).toBe(0);

			systemBus.emit('forge:started', 'test');
			expect(handler).toHaveBeenCalledOnce(); // no additional call
		});
	});

	describe('handlerCount', () => {
		it('counts type-specific and wildcard handlers', () => {
			systemBus.on('forge:started', () => {});
			systemBus.on('forge:started', () => {});
			systemBus.on('forge:completed', () => {});
			systemBus.on('*', () => {});

			expect(systemBus.handlerCount).toBe(4);
		});

		it('decrements on unsubscribe', () => {
			const unsub = systemBus.on('forge:started', () => {});
			expect(systemBus.handlerCount).toBe(1);
			unsub();
			expect(systemBus.handlerCount).toBe(0);
		});
	});

	describe('event IDs', () => {
		it('generates monotonically increasing IDs', () => {
			systemBus.emit('forge:started', 'a');
			systemBus.emit('forge:completed', 'b');

			const ids = systemBus.recentEvents.map(e => e.id);
			// Most recent first, so id[0] > id[1]
			const nums = ids.map(id => parseInt(id.replace('evt_', '')));
			expect(nums[0]).toBeGreaterThan(nums[1]);
		});
	});
});
