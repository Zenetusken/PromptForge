/**
 * PromptForge app — implements AppFrontend for the kernel shell.
 *
 * Registers windows, commands, and file handlers with the kernel.
 */

import type {
	AnyComponent,
	AppFrontend,
	AppManifestFrontend,
	GenericFileDescriptor,
	KernelAPI,
} from "$lib/kernel/types";

const manifest: AppManifestFrontend = {
	id: "promptforge",
	version: "0.2.0",
	name: "PromptForge",
	icon: "zap",
	accent_color: "neon-purple",
	windows: [
		{
			id: "ide",
			title: "Forge IDE",
			icon: "terminal",
			component: "ForgeIDEWorkspace",
			persistent: true,
		},
		{
			id: "projects",
			title: "Projects",
			icon: "folder",
			component: "ProjectsWindow",
			persistent: true,
		},
		{
			id: "history",
			title: "History",
			icon: "clock",
			component: "HistoryWindow",
			persistent: true,
		},
		{
			id: "control-panel",
			title: "Control Panel",
			icon: "settings",
			component: "ControlPanelWindow",
			persistent: true,
		},
		{
			id: "task-manager",
			title: "Task Manager",
			icon: "cpu",
			component: "TaskManagerWindow",
			persistent: true,
		},
		{
			id: "batch-processor",
			title: "Batch Processor",
			icon: "layers",
			component: "BatchProcessorWindow",
			persistent: true,
		},
		{
			id: "strategy-workshop",
			title: "Strategy Workshop",
			icon: "bar-chart",
			component: "StrategyWorkshopWindow",
			persistent: true,
		},
		{
			id: "template-library",
			title: "Template Library",
			icon: "file-text",
			component: "TemplateLibraryWindow",
			persistent: true,
		},
		{
			id: "terminal",
			title: "Terminal",
			icon: "terminal",
			component: "TerminalWindow",
			persistent: true,
		},
		{
			id: "network-monitor",
			title: "Network Monitor",
			icon: "activity",
			component: "NetworkMonitorWindow",
			persistent: true,
		},
		{
			id: "recycle-bin",
			title: "Recycle Bin",
			icon: "trash-2",
			component: "RecycleBinWindow",
			persistent: true,
		},
		{
			id: "workspace-manager",
			title: "Workspace Hub",
			icon: "git-branch",
			component: "WorkspaceWindow",
			persistent: true,
		},
		{
			id: "display-settings",
			title: "Display Settings",
			icon: "monitor",
			component: "DisplaySettingsWindow",
			persistent: true,
		},
	],
	file_types: [
		{
			extension: ".forge",
			label: "Forge Result",
			icon: "zap",
			color: "purple",
			artifact_kind: "forge-result",
		},
		{
			extension: ".scan",
			label: "Analysis",
			icon: "search",
			color: "cyan",
			artifact_kind: "analysis",
		},
		{
			extension: ".val",
			label: "Validation",
			icon: "check-circle",
			color: "green",
			artifact_kind: "validation",
		},
		{
			extension: ".strat",
			label: "Strategy",
			icon: "compass",
			color: "yellow",
			artifact_kind: "strategy",
		},
		{
			extension: ".md",
			label: "Prompt",
			icon: "file-text",
			color: "blue",
			artifact_kind: "prompt",
		},
		{
			extension: ".tmpl",
			label: "Template",
			icon: "book-open",
			color: "teal",
			artifact_kind: "template",
		},
		{
			extension: ".app",
			label: "Application",
			icon: "box",
			color: "indigo",
			artifact_kind: "application",
		},
		{
			extension: ".lnk",
			label: "Shortcut",
			icon: "external-link",
			color: "dim",
			artifact_kind: "shortcut",
		},
	],
	commands: [
		{
			id: "promptforge:new-forge",
			label: "New Forge",
			category: "forge",
			shortcut: "/",
			icon: "zap",
		},
		{
			id: "promptforge:open-history",
			label: "Open History",
			category: "navigation",
			shortcut: "Ctrl+H",
			icon: "clock",
		},
		{
			id: "promptforge:open-projects",
			label: "Open Projects",
			category: "navigation",
			shortcut: "Ctrl+P",
			icon: "folder",
		},
	],
	bus_events: [
		"forge:started",
		"forge:completed",
		"forge:failed",
		"forge:cancelled",
		"forge:progress",
	],
	process_types: [
		{
			id: "forge",
			label: "Forge Pipeline",
			icon: "zap",
			stages: ["analyze", "strategy", "optimize", "validate"],
		},
	],
	start_menu: {
		pinned: ["ide", "projects", "history"],
		section: "Tools",
	},
	desktop_icons: [
		{
			id: "promptforge-ide",
			label: "Forge IDE",
			icon: "terminal",
			action: "openWindow:ide",
		},
	],
};

/** Dynamic component loader — maps component names to import paths. */
const COMPONENT_MAP: Record<
	string,
	() => Promise<{ default: AnyComponent }>
> = {
	ForgeIDEWorkspace: () => import("$lib/components/ForgeIDEWorkspace.svelte"),
	ProjectsWindow: () => import("$lib/components/ProjectsWindow.svelte"),
	HistoryWindow: () => import("$lib/components/HistoryWindow.svelte"),
	ControlPanelWindow: () =>
		import("$lib/components/ControlPanelWindow.svelte"),
	TaskManagerWindow: () => import("$lib/components/TaskManagerWindow.svelte"),
	BatchProcessorWindow: () =>
		import("$lib/components/BatchProcessorWindow.svelte"),
	StrategyWorkshopWindow: () =>
		import("$lib/components/StrategyWorkshopWindow.svelte"),
	TemplateLibraryWindow: () =>
		import("$lib/components/TemplateLibraryWindow.svelte"),
	TerminalWindow: () => import("$lib/components/TerminalWindow.svelte"),
	NetworkMonitorWindow: () =>
		import("$lib/components/NetworkMonitorWindow.svelte"),
	RecycleBinWindow: () => import("$lib/components/RecycleBinWindow.svelte"),
	WorkspaceWindow: () => import("$lib/components/WorkspaceWindow.svelte"),
	DisplaySettingsWindow: () =>
		import("$lib/components/DisplaySettingsWindow.svelte"),
	FolderWindow: () => import("$lib/components/FolderWindow.svelte"),
};

export class PromptForgeApp implements AppFrontend {
	readonly manifest = manifest;

	init(_kernel: KernelAPI): void {
		// App-specific initialization (bus subscriptions, etc.)
		// Currently handled by +layout.svelte during transition
	}

	destroy(): void {
		// Cleanup
	}

	async getComponent(name: string): Promise<{ default: AnyComponent }> {
		const loader = COMPONENT_MAP[name];
		if (!loader) {
			throw new Error(
				`PromptForge: unknown component ${name}. Available: ${Object.keys(COMPONENT_MAP).join(", ")}`,
			);
		}
		return loader();
	}

	async openFile(_descriptor: GenericFileDescriptor): Promise<void> {
		// Delegate to the existing documentOpener
		// Will be wired up when we migrate stores
	}
}

/** Singleton instance. */
export const promptForgeApp = new PromptForgeApp();
