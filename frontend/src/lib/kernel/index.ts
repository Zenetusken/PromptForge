/**
 * Kernel public API — re-exports all kernel stores, services, and types.
 */

// Types
export type {
	AnyComponent,
	AppFrontend,
	AppManifestFrontend,
	KernelAPI,
	WindowRegistration,
	GenericFileDescriptor,
	WindowDef,
	FileTypeDef,
	CommandDef,
	ProcessTypeDef,
	StartMenuDef,
	DesktopIconDef,
	SettingsDef,
} from "./types";

// Services
export { appRegistry } from "./services/appRegistry.svelte";
export { appSettings } from "./services/appSettings.svelte";
export { appStorage } from "./services/appStorage";
export { vfs } from "./services/vfs";

// Errors
export { KernelError, throwIfNotOk } from "./utils/errors";
