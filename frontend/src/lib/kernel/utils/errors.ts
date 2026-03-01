/**
 * Kernel service error handling — shared across VFS, Storage, Settings clients.
 *
 * Extracts structured error details from backend JSON responses and provides
 * discriminated error types for 403 (forbidden), 422 (validation), 429 (quota),
 * and 503 (app disabled).
 */

export class KernelError extends Error {
	readonly status: number;
	readonly detail: string;

	constructor(status: number, detail: string, operation: string) {
		super(`${operation}: ${detail}`);
		this.name = "KernelError";
		this.status = status;
		this.detail = detail;
	}

	get isDisabled(): boolean {
		return this.status === 503;
	}

	get isQuotaExceeded(): boolean {
		return this.status === 429;
	}

	get isValidationError(): boolean {
		return this.status === 422;
	}

	get isForbidden(): boolean {
		return this.status === 403;
	}

	get isNotFound(): boolean {
		return this.status === 404;
	}
}

/**
 * Check a fetch response and throw a KernelError with extracted detail on failure.
 *
 * Usage:
 * ```ts
 * const res = await fetch(...);
 * await throwIfNotOk(res, "create folder");
 * return res.json();
 * ```
 */
export async function throwIfNotOk(res: Response, operation: string): Promise<void> {
	if (res.ok) return;

	let detail = `HTTP ${res.status}`;
	try {
		const body = await res.json();
		if (body.detail) detail = String(body.detail);
	} catch {
		// Response wasn't JSON — use status text
		detail = res.statusText || detail;
	}

	throw new KernelError(res.status, detail, operation);
}
