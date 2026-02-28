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
