/**
 * Frontend App Registry — discovers, loads, and manages app lifecycle.
 *
 * Apps register themselves here and the kernel shell uses the registry
 * to render windows, register commands, and route file opens.
 */

import type {
	AnyComponent,
	AppFrontend,
	AppManifestFrontend,
	KernelAPI,
	WindowRegistration,
} from "$lib/kernel/types";

interface AppRecord {
	manifest: AppManifestFrontend;
	instance: AppFrontend;
	windows: WindowRegistration[];
	initialized: boolean;
}

class AppRegistryState {
	/** App records stored as $state array — guaranteed reactive on .push(). */
	private _records = $state<AppRecord[]>([]);
	private _kernel: KernelAPI | null = null;

	/** Register an app with the kernel. Idempotent — skips if already registered. */
	register(app: AppFrontend): void {
		const { manifest } = app;

		if (this._records.some((r) => r.manifest.id === manifest.id)) return;

		// Build window registrations with component caching.
		// Each window's loadComponent() caches its promise so {#await} doesn't
		// restart when the block re-evaluates.
		const windows: WindowRegistration[] = manifest.windows.map((w) => {
			let cached: Promise<{ default: AnyComponent }> | null = null;
			return {
				windowId: w.id,
				appId: manifest.id,
				title: w.title,
				icon: w.icon,
				persistent: w.persistent,
				componentName: w.component,
				loadComponent: () => {
					if (!cached) cached = app.getComponent(w.component);
					return cached;
				},
			};
		});

		const record: AppRecord = { manifest, instance: app, windows, initialized: false };
		this._records.push(record);

		// Initialize app with kernel API if available
		if (this._kernel) {
			record.initialized = true;
			app.init(this._kernel);
		}
	}

	/** Set the kernel API reference (called once during shell boot). */
	setKernel(kernel: KernelAPI): void {
		this._kernel = kernel;
		// Init any already-registered apps (skip already-initialized ones)
		for (const record of this._records) {
			if (!record.initialized) {
				record.initialized = true;
				record.instance.init(kernel);
			}
		}
	}

	/** Get an app by ID. */
	get(appId: string): AppRecord | undefined {
		return this._records.find((r) => r.manifest.id === appId);
	}

	/** Get all registered apps. */
	get all(): AppRecord[] {
		return this._records;
	}

	/** Get all window registrations across all apps. */
	get allWindows(): WindowRegistration[] {
		return this._records.flatMap((a) => a.windows);
	}

	/** Get window registration by window ID. */
	getWindow(windowId: string): WindowRegistration | undefined {
		for (const record of this._records) {
			const win = record.windows.find((w) => w.windowId === windowId);
			if (win) return win;
		}
		return undefined;
	}

	/** Get all file types from all apps. */
	get allFileTypes() {
		return this._records.flatMap((a) => a.manifest.file_types);
	}

	/** Get all desktop icons from all apps. */
	get allDesktopIcons() {
		return this._records.flatMap((a) => a.manifest.desktop_icons);
	}

	/** Get all start menu entries from all apps. */
	get allStartMenuEntries() {
		return this._records
			.filter((a) => a.manifest.start_menu)
			.map((a) => ({
				appId: a.manifest.id,
				...a.manifest.start_menu!,
				windows: a.windows,
			}));
	}

	/** Destroy all apps (cleanup). */
	destroyAll(): void {
		for (const record of this._records) {
			record.instance.destroy();
			record.initialized = false;
		}
		this._records = [];
		this._kernel = null;
	}
}

export const appRegistry = new AppRegistryState();
