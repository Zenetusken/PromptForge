/**
 * TextForge app — text transformation powered by LLM.
 *
 * Exercises all kernel APIs: process scheduler, app settings, storage,
 * bus events, command palette, window manager.
 */

import type {
	AnyComponent,
	AppFrontend,
	AppManifestFrontend,
	GenericFileDescriptor,
	KernelAPI,
} from "$lib/kernel/types";

const manifest: AppManifestFrontend = {
	id: "textforge",
	version: "0.1.0",
	name: "TextForge",
	icon: "zap",
	accent_color: "neon-orange",
	windows: [
		{
			id: "textforge",
			title: "TextForge",
			icon: "zap",
			component: "TextForgeWindow",
			persistent: true,
		},
		{
			id: "textforge-history",
			title: "Transform History",
			icon: "clock",
			component: "TextForgeHistoryWindow",
			persistent: true,
		},
	],
	file_types: [
		{
			extension: ".txf",
			label: "Transform Result",
			icon: "zap",
			color: "neon-orange",
			artifact_kind: "transform",
		},
	],
	commands: [
		{
			id: "textforge:open",
			label: "Open TextForge",
			category: "apps",
			shortcut: "",
			icon: "zap",
		},
		{
			id: "textforge:history",
			label: "Transform History",
			category: "apps",
			shortcut: "",
			icon: "clock",
		},
	],
	bus_events: [
		"transform:started",
		"transform:completed",
		"transform:failed",
	],
	process_types: [
		{
			id: "transform",
			label: "Transform",
			icon: "zap",
			stages: ["analyze", "transform", "validate"],
		},
	],
	start_menu: {
		pinned: ["textforge"],
		section: "Apps",
	},
	desktop_icons: [
		{
			id: "textforge-icon",
			label: "TextForge",
			icon: "zap",
			action: "openWindow:textforge",
			color: "neon-orange",
			type: "system",
		},
	],
	settings: {
		schema: {
			defaultTransform: { type: "string", default: "summarize" },
			outputFormat: { type: "string", default: "plain" },
			preserveFormatting: { type: "boolean", default: true },
		},
		component: "TextForgeSettings",
	},
	extensions: [
		{
			slot: "promptforge:review-actions",
			component: "SimplifyAction",
			priority: 10,
			label: "Simplify with TextForge",
		},
	],
};

const COMPONENT_MAP: Record<
	string,
	() => Promise<{ default: AnyComponent }>
> = {
	TextForgeWindow: () =>
		import("$lib/apps/textforge/TextForgeWindow.svelte"),
	TextForgeHistoryWindow: () =>
		import("$lib/apps/textforge/TextForgeHistoryWindow.svelte"),
	TextForgeSettings: () =>
		import("$lib/apps/textforge/TextForgeSettings.svelte"),
	SimplifyAction: () =>
		import("$lib/apps/textforge/SimplifyAction.svelte"),
};

export class TextForgeApp implements AppFrontend {
	readonly manifest = manifest;
	private _cleanup: (() => void)[] = [];

	init(kernel: KernelAPI): void {
		const executeMap: Record<string, { execute: () => void }> = {
			"textforge:open": {
				execute: () =>
					kernel.windowManager.openWindow({
						id: "textforge",
						title: "TextForge",
						icon: "zap",
					}),
			},
			"textforge:history": {
				execute: () =>
					kernel.windowManager.openWindow({
						id: "textforge-history",
						title: "Transform History",
						icon: "clock",
					}),
			},
		};

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

		kernel.commandPalette.registerAll(commands);

		const commandIds = commands.map((c) => c.id);
		this._cleanup.push(() => {
			for (const id of commandIds) kernel.commandPalette.unregister(id);
		});
	}

	destroy(): void {
		for (const fn of this._cleanup) fn();
		this._cleanup = [];
	}

	async getComponent(name: string): Promise<{ default: AnyComponent }> {
		const loader = COMPONENT_MAP[name];
		if (!loader) {
			throw new Error(`TextForge: unknown component ${name}`);
		}
		return loader();
	}

	async getSettingsComponent(): Promise<{ default: AnyComponent }> {
		return import("$lib/apps/textforge/TextForgeSettings.svelte");
	}

	async openFile(descriptor: GenericFileDescriptor): Promise<void> {
		if (descriptor.extension === ".txf") {
			const { windowManager } = await import(
				"$lib/stores/windowManager.svelte"
			);
			windowManager.openWindow({
				id: "textforge",
				title: "TextForge",
				icon: "zap",
			});
		}
	}
}

export const textForgeApp = new TextForgeApp();
