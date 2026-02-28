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
	icon: "smile",
	accent_color: "neon-green",
	windows: [
		{
			id: "hello-world",
			title: "Hello World",
			icon: "smile",
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
			icon: "smile",
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
			icon: "smile",
			action: "openWindow:hello-world",
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

	init(_kernel: KernelAPI): void {}
	destroy(): void {}

	async getComponent(name: string): Promise<{ default: AnyComponent }> {
		const loader = COMPONENT_MAP[name];
		if (!loader) {
			throw new Error(`HelloWorld: unknown component ${name}`);
		}
		return loader();
	}
}

export const helloWorldApp = new HelloWorldApp();
