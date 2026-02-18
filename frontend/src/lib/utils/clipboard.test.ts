// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { copyToClipboard } from './clipboard';

describe('copyToClipboard', () => {
	let appendChildSpy: any;
	let removeChildSpy: any;
	let execCommandSpy: any;

	beforeEach(() => {
		appendChildSpy = vi.spyOn(document.body, 'appendChild').mockReturnValue(null as any);
		removeChildSpy = vi.spyOn(document.body, 'removeChild').mockReturnValue(null as any);
		// jsdom does not implement execCommand, so we stub it onto document
		document.execCommand = vi.fn();
		execCommandSpy = vi.spyOn(document, 'execCommand');
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	it('returns true when execCommand succeeds', () => {
		execCommandSpy.mockReturnValue(true);
		expect(copyToClipboard('hello')).toBe(true);
	});

	it('creates and removes a textarea element', () => {
		execCommandSpy.mockReturnValue(true);
		copyToClipboard('test text');

		expect(appendChildSpy).toHaveBeenCalledOnce();
		const textarea = appendChildSpy.mock.calls[0][0];
		expect(textarea).toBeInstanceOf(HTMLTextAreaElement);
		expect(textarea.value).toBe('test text');
		expect(removeChildSpy).toHaveBeenCalledOnce();
	});

	it('positions textarea offscreen', () => {
		execCommandSpy.mockReturnValue(true);
		copyToClipboard('test');

		const textarea = appendChildSpy.mock.calls[0][0];
		expect(textarea.style.position).toBe('fixed');
		expect(textarea.style.left).toBe('-9999px');
	});

	it('falls back to clipboard API when execCommand fails', () => {
		execCommandSpy.mockReturnValue(false);
		const writeTextMock = vi.fn().mockResolvedValue(undefined);
		Object.defineProperty(navigator, 'clipboard', {
			value: { writeText: writeTextMock },
			writable: true,
			configurable: true
		});

		const result = copyToClipboard('fallback text');
		expect(result).toBe(true);
		expect(writeTextMock).toHaveBeenCalledWith('fallback text');
	});

	it('falls back to clipboard API when execCommand throws', () => {
		execCommandSpy.mockImplementation(() => {
			throw new Error('not allowed');
		});
		const writeTextMock = vi.fn().mockResolvedValue(undefined);
		Object.defineProperty(navigator, 'clipboard', {
			value: { writeText: writeTextMock },
			writable: true,
			configurable: true
		});

		const result = copyToClipboard('error text');
		expect(result).toBe(true);
		expect(writeTextMock).toHaveBeenCalledWith('error text');
	});

	it('returns true even when clipboard API is not available', () => {
		execCommandSpy.mockReturnValue(false);
		Object.defineProperty(navigator, 'clipboard', {
			value: undefined,
			writable: true,
			configurable: true
		});

		const result = copyToClipboard('no clipboard');
		expect(result).toBe(true);
	});
});
