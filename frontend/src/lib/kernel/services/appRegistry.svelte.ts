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
	ExtensionSlotDef,
	KernelAPI,
	WindowRegistration,
} from "$lib/kernel/types";

interface AppRecord {
	manifest: AppManifestFrontend;
	instance: AppFrontend;
	windows: WindowRegistration[];
	initialized: boolean;
}

/** Resolved extension entry with a component loader. */
export interface ResolvedExtension {
	slotId: string;
	appId: string;
	component: string;
	priority: number;
	label: string;
	loadComponent: () => Promise<{ default: AnyComponent }>;
}

class AppRegistryState {
	/** App records stored as $state array — guaranteed reactive on .push(). */
	private _records = $state<AppRecord[]>([]);
	private _kernel: KernelAPI | null = null;

	/** Extension slot definitions indexed by full slot ID ("{appId}:{slotId}"). */
	private _slots = new Map<string, ExtensionSlotDef & { appId: string }>();
	/** Extensions indexed by slot ID. */
	private _extensions = new Map<string, ResolvedExtension[]>();

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

		// Index extension slots declared by this app
		for (const slot of manifest.extension_slots ?? []) {
			const fullId = `${manifest.id}:${slot.id}`;
			this._slots.set(fullId, { ...slot, appId: manifest.id });
			if (!this._extensions.has(fullId)) {
				this._extensions.set(fullId, []);
			}
		}

		// Index extension contributions from this app
		for (const ext of manifest.extensions ?? []) {
			let cached: Promise<{ default: AnyComponent }> | null = null;
			const resolved: ResolvedExtension = {
				slotId: ext.slot,
				appId: manifest.id,
				component: ext.component,
				priority: ext.priority,
				label: ext.label,
				loadComponent: () => {
					if (!cached) cached = app.getComponent(ext.component);
					return cached;
				},
			};

			const existing = this._extensions.get(ext.slot) ?? [];
			// Enforce max_extensions limit
			const slotDef = this._slots.get(ext.slot);
			if (slotDef && existing.length >= slotDef.max_extensions) continue;

			existing.push(resolved);
			// Sort by priority descending (higher priority first)
			existing.sort((a, b) => b.priority - a.priority);
			this._extensions.set(ext.slot, existing);
		}

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

	/** Get all process types from all apps. */
	get allProcessTypes() {
		return this._records.flatMap((a) =>
			a.manifest.process_types.map((pt) => ({ ...pt, appId: a.manifest.id })),
		);
	}

	/** Get apps that declare settings. */
	get appsWithSettings() {
		return this._records
			.filter((a) => a.manifest.settings)
			.map((a) => ({
				appId: a.manifest.id,
				name: a.manifest.name,
				icon: a.manifest.icon,
				settings: a.manifest.settings!,
				instance: a.instance,
			}));
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

	/** Get all resolved extensions for a slot, sorted by priority (descending). */
	getExtensions(slotId: string): ResolvedExtension[] {
		return this._extensions.get(slotId) ?? [];
	}

	/** Get all declared extension slots across all apps. */
	get allExtensionSlots() {
		return [...this._slots.values()];
	}

	/** Destroy all apps (cleanup). */
	destroyAll(): void {
		for (const record of this._records) {
			record.instance.destroy();
			record.initialized = false;
		}
		this._records.length = 0;
		this._slots.clear();
		this._extensions.clear();
		this._kernel = null;
	}
}

export const appRegistry = new AppRegistryState();
