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

/** Kernel API provided to apps during init. */
export interface KernelAPI {
	readonly bus: unknown; // SystemBus
	readonly windowManager: unknown;
	readonly commandPalette: unknown;
	readonly processScheduler: unknown;
	readonly settings: unknown;
	readonly clipboard: unknown;
}
