/**
 * PromptForge app — implements AppFrontend for the kernel shell.
 *
 * Registers windows, commands, desktop icons, and file handlers with the kernel.
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
		{
			id: "audit-log",
			title: "Audit Log",
			icon: "shield",
			component: "AuditLogWindow",
			persistent: true,
		},
		{
			id: "app-manager",
			title: "App Manager",
			icon: "box",
			component: "AppManagerWindow",
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
		{ id: "ide-open", label: "Open Forge IDE", category: "window", shortcut: "/", icon: "terminal" },
		{ id: "ide-minimize", label: "Toggle Minimize IDE", category: "window", shortcut: "Ctrl+M", icon: "minus" },
		{ id: "tab-new", label: "New Tab", category: "forge", shortcut: "Ctrl+N", icon: "plus" },
		{ id: "tab-close", label: "Close Tab", category: "forge", shortcut: "Ctrl+W", icon: "x" },
		{ id: "window-projects", label: "Open Projects", category: "window", shortcut: "", icon: "folder" },
		{ id: "window-history", label: "Open History", category: "window", shortcut: "", icon: "clock" },
		{ id: "window-control-panel", label: "Open Control Panel", category: "settings", shortcut: "", icon: "settings" },
		{ id: "window-task-manager", label: "Open Task Manager", category: "window", shortcut: "Ctrl+Shift+Esc", icon: "cpu" },
		{ id: "window-batch-processor", label: "Open Batch Processor", category: "forge", shortcut: "", icon: "layers" },
		{ id: "window-strategy-workshop", label: "Open Strategy Workshop", category: "forge", shortcut: "", icon: "bar-chart" },
		{ id: "window-template-library", label: "Open Template Library", category: "forge", shortcut: "", icon: "file-text" },
		{ id: "window-terminal", label: "Open Terminal", category: "window", shortcut: "Ctrl+`", icon: "terminal" },
		{ id: "window-network-monitor", label: "Open Network Monitor", category: "window", shortcut: "", icon: "activity" },
		{ id: "window-display-settings", label: "Display Settings", category: "settings", shortcut: "", icon: "monitor" },
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
		pinned: ["ide", "workspace-manager"],
		section: "Tools",
	},
	desktop_icons: [
		{ id: "sys-forge-ide", label: "Forge IDE", icon: "terminal", action: "openWindow:ide", color: "cyan" },
		{ id: "sys-projects", label: "Projects", icon: "folder", action: "openWindow:projects", color: "yellow", type: "folder" },
		{ id: "sys-history", label: "History", icon: "folder", action: "openWindow:history", color: "blue", type: "folder" },
		{ id: "sys-control-panel", label: "Control Panel", icon: "settings", action: "openWindow:control-panel", color: "purple" },
		{ id: "sys-task-manager", label: "Task Manager", icon: "cpu", action: "openWindow:task-manager", color: "green" },
		{ id: "sys-batch-processor", label: "Batch Processor", icon: "layers", action: "openWindow:batch-processor", color: "orange" },
		{ id: "sys-strategy-workshop", label: "Strategy Workshop", icon: "bar-chart", action: "openWindow:strategy-workshop", color: "indigo" },
		{ id: "sys-template-library", label: "Template Library", icon: "file-text", action: "openWindow:template-library", color: "teal" },
		{ id: "sys-terminal", label: "Terminal", icon: "terminal", action: "openWindow:terminal", color: "cyan" },
		{ id: "sys-network-monitor", label: "Network Monitor", icon: "activity", action: "openWindow:network-monitor", color: "green" },
		{ id: "sys-workspace-hub", label: "Workspace Hub", icon: "git-branch", action: "openWindow:workspace-manager", color: "green" },
		{ id: "sys-audit-log", label: "Audit Log", icon: "shield", action: "openWindow:audit-log", color: "red" },
		{ id: "sys-app-manager", label: "App Manager", icon: "box", action: "openWindow:app-manager", color: "indigo" },
	],
	extension_slots: [
		{ id: "review-actions", label: "Review Actions", max_extensions: 5 },
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
	AuditLogWindow: () => import("$lib/components/AuditLogWindow.svelte"),
	AppManagerWindow: () => import("$lib/components/AppManagerWindow.svelte"),
};

/**
 * Close the active forge tab. Exported so +layout.svelte's keyboard handler
 * can reuse the same logic without duplication.
 */
export async function closeActiveTab(): Promise<void> {
	const [{ forgeMachine }, { forgeSession }, { optimizationState }, { restoreTabState }] =
		await Promise.all([
			import("$lib/stores/forgeMachine.svelte"),
			import("$lib/stores/forgeSession.svelte"),
			import("$lib/stores/optimization.svelte"),
			import("$lib/stores/tabCoherence"),
		]);

	const { windowManager } = await import("$lib/stores/windowManager.svelte");
	if (!windowManager.ideVisible || forgeMachine.mode === 'forging') return;

	if (forgeSession.tabs.length <= 1) {
		optimizationState.resetForge();
		forgeMachine.reset();
		forgeSession.reset();
	} else {
		const idx = forgeSession.tabs.findIndex((t: { id: string }) => t.id === forgeSession.activeTabId);
		forgeSession.tabs = forgeSession.tabs.filter((t: { id: string }) => t.id !== forgeSession.activeTabId);
		const nextTab = forgeSession.tabs[Math.max(0, idx - 1)];
		forgeSession.activeTabId = nextTab.id;
		restoreTabState(nextTab);
	}
}

/** Helper: open a manifest-declared window via windowManager. */
function openWindowCmd(windowManager: KernelAPI['windowManager'], windowId: string) {
	const win = manifest.windows.find((w) => w.id === windowId);
	if (win) {
		windowManager.openWindow({ id: win.id, title: win.title, icon: win.icon });
	}
}

export class PromptForgeApp implements AppFrontend {
	readonly manifest = manifest;
	private _cleanup: (() => void)[] = [];

	init(kernel: KernelAPI): void {
		const { commandPalette, windowManager } = kernel;

		// Lazy-load forge stores to avoid circular deps at module scope
		const getForgeStores = () =>
			Promise.all([
				import("$lib/stores/forgeMachine.svelte"),
				import("$lib/stores/forgeSession.svelte"),
				import("$lib/stores/optimization.svelte"),
				import("$lib/stores/tabCoherence"),
			]);

		// Cache the resolved stores after first load
		let _stores: Awaited<ReturnType<typeof getForgeStores>> | null = null;
		const stores = async () => {
			if (!_stores) _stores = await getForgeStores();
			return _stores;
		};

		// Execute function map — keyed by manifest command ID.
		// Only non-trivial commands need entries; window-* commands are auto-generated below.
		const executeMap: Record<string, { execute: () => void; available?: () => boolean }> = {
			'ide-open': {
				execute: () => {
					windowManager.openIDE();
					stores().then(([, { forgeSession }]) => forgeSession.focusTextarea());
				},
			},
			'ide-minimize': {
				execute: () => {
					if (windowManager.ideSpawned) {
						if (windowManager.ideVisible) windowManager.minimizeWindow('ide');
						else windowManager.focusWindow('ide');
					}
				},
				available: () => windowManager.ideSpawned,
			},
			'tab-new': {
				execute: () => {
					stores().then(([{ forgeMachine }, { forgeSession }, , { saveActiveTabState, restoreTabState }]) => {
						if (forgeMachine.mode === 'forging') return;
						saveActiveTabState();
						const tab = forgeSession.createTab();
						if (tab) { restoreTabState(tab); forgeSession.activate(); }
					});
				},
			},
			'tab-close': {
				execute: () => { closeActiveTab(); },
				available: () => windowManager.ideVisible,
			},
		};

		// Auto-generate execute functions for window-* commands from manifest windows.
		// Pattern: "window-{windowId}" → open the corresponding window.
		for (const cmd of manifest.commands) {
			if (cmd.id.startsWith('window-') && !executeMap[cmd.id]) {
				const windowId = cmd.id.slice('window-'.length);
				executeMap[cmd.id] = {
					execute: () => openWindowCmd(windowManager, windowId),
				};
			}
		}

		// Build full command objects by merging manifest metadata + execute functions
		const commands = manifest.commands
			.filter((cmd) => executeMap[cmd.id])
			.map((cmd) => ({
				id: cmd.id,
				label: cmd.label,
				category: cmd.category,
				...(cmd.shortcut ? { shortcut: cmd.shortcut } : {}),
				...(cmd.icon ? { icon: cmd.icon } : {}),
				...executeMap[cmd.id],
			}));

		commandPalette.registerAll(commands);

		// Track registered command IDs for cleanup
		const commandIds = commands.map(c => c.id);
		this._cleanup.push(() => {
			for (const id of commandIds) commandPalette.unregister(id);
		});
	}

	destroy(): void {
		for (const fn of this._cleanup) fn();
		this._cleanup = [];
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

	async openFile(descriptor: GenericFileDescriptor): Promise<void> {
		const { openDocument } = await import("$lib/utils/documentOpener");
		const { createPromptDescriptor, createArtifactDescriptor } = await import("$lib/utils/fileDescriptor");

		if (descriptor.extension === '.md' || descriptor.kind === 'prompt') {
			openDocument(createPromptDescriptor(descriptor.id, descriptor.metadata?.projectId as string ?? '', descriptor.name));
		} else if (descriptor.extension === '.forge' || descriptor.kind === 'artifact') {
			openDocument(createArtifactDescriptor(descriptor.id, descriptor.name));
		}
	}
}

/** Singleton instance. */
export const promptForgeApp = new PromptForgeApp();
