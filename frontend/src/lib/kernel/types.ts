/**
 * Kernel type definitions for the app platform.
 */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type AnyComponent = import("svelte").Component<any, any, any>;

/** App manifest parsed from manifest.json (frontend portion). */
export interface AppManifestFrontend {
	id: string;
	version: string;
	name: string;
	icon: string;
	accent_color: string;
	windows: WindowDef[];
	file_types: FileTypeDef[];
	commands: CommandDef[];
	bus_events: string[];
	process_types: ProcessTypeDef[];
	start_menu?: StartMenuDef;
	desktop_icons: DesktopIconDef[];
	settings?: SettingsDef;
}

export interface WindowDef {
	id: string;
	title: string;
	icon: string;
	component: string;
	persistent: boolean;
}

export interface FileTypeDef {
	extension: string;
	label: string;
	icon: string;
	color: string;
	artifact_kind: string;
}

export interface CommandDef {
	id: string;
	label: string;
	category: string;
	shortcut: string;
	icon: string;
}

export interface ProcessTypeDef {
	id: string;
	label: string;
	icon: string;
	stages: string[];
}

export interface StartMenuDef {
	pinned: string[];
	section: string;
}

export interface DesktopIconDef {
	id: string;
	label: string;
	icon: string;
	action: string;
	color?: string;
	/** 'system' icons can't be trashed; 'folder' icons can. Defaults to 'system'. */
	type?: string;
}

export interface SettingsDef {
	schema: Record<string, { type: string; default: unknown }>;
	component: string;
}

/** Frontend app interface — apps implement this to integrate with the shell. */
export interface AppFrontend {
	readonly manifest: AppManifestFrontend;
	init(kernel: KernelAPI): void;
	destroy(): void;
	getComponent(name: string): Promise<{ default: AnyComponent }>;
	openFile?(descriptor: GenericFileDescriptor): Promise<void>;
	getSettingsComponent?(): Promise<{ default: AnyComponent }>;
}

/** Generic file descriptor with app routing. */
export interface GenericFileDescriptor {
	kind: string;
	id: string;
	appId: string;
	name: string;
	extension: string;
	metadata?: Record<string, unknown>;
}

/** Window registration in the app registry. */
export interface WindowRegistration {
	windowId: string;
	appId: string;
	title: string;
	icon: string;
	persistent: boolean;
	componentName: string;
	loadComponent: () => Promise<{ default: AnyComponent }>;
}

/** Bus event passed to handlers. */
export interface KernelBusEvent {
	type: string;
	source: string;
	payload: Record<string, unknown>;
	timestamp: number;
	id: string;
}

/** System bus interface exposed to apps. */
export interface KernelBus {
	on(eventType: string, handler: (event: KernelBusEvent) => void): () => void;
	emit(type: string, source: string, payload?: Record<string, unknown>): void;
}

/** Window open options. */
export interface WindowOpenOptions {
	id: string;
	title: string;
	icon: string;
	data?: Record<string, unknown>;
}

/** Window manager interface exposed to apps. */
export interface KernelWindowManager {
	openWindow(opts: WindowOpenOptions): void;
	closeWindow(id: string): void;
	focusWindow(id: string): void;
	minimizeWindow(id: string): void;
	openIDE(): void;
	readonly ideSpawned: boolean;
	readonly ideVisible: boolean;
	readonly activeWindowId: string | null;
}

/** Command registration for the command palette. */
export interface KernelCommand {
	id: string;
	label: string;
	category: string;
	shortcut?: string;
	icon?: string;
	execute: () => void;
	available?: () => boolean;
}

/** Command palette interface exposed to apps. */
export interface KernelCommandPalette {
	register(command: KernelCommand): void;
	registerAll(commands: KernelCommand[]): void;
	unregister(id: string): void;
}

/** Process scheduler interface exposed to apps. */
export interface KernelProcessScheduler {
	readonly maxConcurrent: number;
}

/** Settings interface exposed to apps. */
export interface KernelSettings {
	readonly accentColor: string;
	readonly enableAnimations: boolean;
}

/** Clipboard interface exposed to apps. */
export interface KernelClipboard {
	copy(text: string, label?: string): void;
}

/** Kernel API provided to apps during init. */
export interface KernelAPI {
	readonly bus: KernelBus;
	readonly windowManager: KernelWindowManager;
	readonly commandPalette: KernelCommandPalette;
	readonly processScheduler: KernelProcessScheduler;
	readonly settings: KernelSettings;
	readonly clipboard: KernelClipboard;
}
