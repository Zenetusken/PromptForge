/**
 * Hello World app — minimal example of an AppFrontend implementation.
 */

import type {
	AnyComponent,
	AppFrontend,
	AppManifestFrontend,
	KernelAPI,
} from "$lib/kernel/types";

const manifest: AppManifestFrontend = {
	id: "hello-world",
	version: "0.1.0",
	name: "Hello World",
	icon: "sparkles",
	accent_color: "neon-green",
	windows: [
		{
			id: "hello-world",
			title: "Hello World",
			icon: "sparkles",
			component: "HelloWorldWindow",
			persistent: false,
		},
	],
	file_types: [],
	commands: [
		{
			id: "hello-world:greet",
			label: "Say Hello",
			category: "apps",
			shortcut: "",
			icon: "sparkles",
		},
	],
	bus_events: [],
	process_types: [],
	start_menu: {
		pinned: ["hello-world"],
		section: "Apps",
	},
	desktop_icons: [
		{
			id: "hello-world",
			label: "Hello World",
			icon: "sparkles",
			action: "openWindow:hello-world",
			color: "green",
		},
	],
};

const COMPONENT_MAP: Record<
	string,
	() => Promise<{ default: AnyComponent }>
> = {
	HelloWorldWindow: () =>
		import("$lib/apps/hello_world/HelloWorldWindow.svelte"),
};

export class HelloWorldApp implements AppFrontend {
	readonly manifest = manifest;
	private _cleanup: (() => void)[] = [];

	init(kernel: KernelAPI): void {
		// Build commands from manifest metadata + execute functions
		const executeMap: Record<string, { execute: () => void }> = {
			"hello-world:greet": {
				execute: () => kernel.windowManager.openWindow({
					id: "hello-world",
					title: "Hello World",
					icon: "sparkles",
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

		const commandIds = commands.map(c => c.id);
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
			throw new Error(`HelloWorld: unknown component ${name}`);
		}
		return loader();
	}
}

export const helloWorldApp = new HelloWorldApp();
