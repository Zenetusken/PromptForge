import { describe, it, expect } from 'vitest';
import {
	safeString,
	safeNumber,
	safeArray,
	safeStringOrUndefined,
	safeNumberOrUndefined,
	safeArrayOrUndefined
} from './safe';

describe('safeString', () => {
	it('returns string values as-is', () => {
		expect(safeString('hello')).toBe('hello');
	});

	it('returns empty string for non-string types', () => {
		expect(safeString(42)).toBe('');
		expect(safeString(null)).toBe('');
		expect(safeString(undefined)).toBe('');
		expect(safeString(true)).toBe('');
		expect(safeString([])).toBe('');
	});

	it('returns custom fallback for non-string types', () => {
		expect(safeString(null, 'fallback')).toBe('fallback');
	});

	it('returns empty string value (not fallback)', () => {
		expect(safeString('', 'fallback')).toBe('');
	});
});

describe('safeNumber', () => {
	it('returns number values as-is', () => {
		expect(safeNumber(42)).toBe(42);
		expect(safeNumber(0)).toBe(0);
		expect(safeNumber(0.5)).toBe(0.5);
	});

	it('returns 0 for non-number types', () => {
		expect(safeNumber('42')).toBe(0);
		expect(safeNumber(null)).toBe(0);
		expect(safeNumber(undefined)).toBe(0);
		expect(safeNumber(true)).toBe(0);
	});

	it('returns custom fallback for non-number types', () => {
		expect(safeNumber(null, -1)).toBe(-1);
	});

	it('returns zero value (not fallback)', () => {
		expect(safeNumber(0, 99)).toBe(0);
	});
});

describe('safeArray', () => {
	it('returns array values as-is', () => {
		expect(safeArray(['a', 'b'])).toEqual(['a', 'b']);
	});

	it('returns empty array for non-array types', () => {
		expect(safeArray(null)).toEqual([]);
		expect(safeArray(undefined)).toEqual([]);
		expect(safeArray('string')).toEqual([]);
		expect(safeArray(42)).toEqual([]);
	});

	it('returns empty array value (not default)', () => {
		expect(safeArray([])).toEqual([]);
	});
});

describe('safeStringOrUndefined', () => {
	it('returns string values as-is', () => {
		expect(safeStringOrUndefined('hello')).toBe('hello');
	});

	it('returns undefined for non-string types', () => {
		expect(safeStringOrUndefined(42)).toBeUndefined();
		expect(safeStringOrUndefined(null)).toBeUndefined();
		expect(safeStringOrUndefined(undefined)).toBeUndefined();
		expect(safeStringOrUndefined(true)).toBeUndefined();
	});

	it('returns empty string (not undefined)', () => {
		expect(safeStringOrUndefined('')).toBe('');
	});
});

describe('safeNumberOrUndefined', () => {
	it('returns number values as-is', () => {
		expect(safeNumberOrUndefined(42)).toBe(42);
		expect(safeNumberOrUndefined(0.5)).toBe(0.5);
	});

	it('returns undefined for non-number types', () => {
		expect(safeNumberOrUndefined('42')).toBeUndefined();
		expect(safeNumberOrUndefined(null)).toBeUndefined();
		expect(safeNumberOrUndefined(undefined)).toBeUndefined();
	});

	it('returns zero (not undefined)', () => {
		expect(safeNumberOrUndefined(0)).toBe(0);
	});
});

describe('safeArrayOrUndefined', () => {
	it('returns array values as-is', () => {
		expect(safeArrayOrUndefined(['a'])).toEqual(['a']);
	});

	it('returns undefined for non-array types', () => {
		expect(safeArrayOrUndefined(null)).toBeUndefined();
		expect(safeArrayOrUndefined(undefined)).toBeUndefined();
		expect(safeArrayOrUndefined('string')).toBeUndefined();
	});

	it('returns empty array (not undefined)', () => {
		expect(safeArrayOrUndefined([])).toEqual([]);
	});
});
