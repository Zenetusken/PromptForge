import { describe, it, expect, beforeEach, vi } from "vitest";

// We need to test AppRegistryState in isolation. Since it uses Svelte 5 runes
// ($state), we must import it in a test environment that supports them.
import { appRegistry } from "./appRegistry.svelte";

import type {
	AnyComponent,
	AppFrontend,
	AppManifestFrontend,
	GenericFileDescriptor,
	KernelAPI,
} from "$lib/kernel/types";

/** Helper to create a minimal mock app. */
function createMockApp(
	manifest: AppManifestFrontend,
	components: Record<string, unknown> = {},
): AppFrontend {
	return {
		manifest,
		init: vi.fn(),
		destroy: vi.fn(),
		async getComponent(name: string) {
			return {
				default: (components[name] ?? (() => {})) as AnyComponent,
			};
		},
	};
}

function makeManifest(
	overrides: Partial<AppManifestFrontend> = {},
): AppManifestFrontend {
	return {
		id: "test-app",
		version: "1.0.0",
		name: "Test App",
		icon: "zap",
		accent_color: "neon-cyan",
		windows: [],
		file_types: [],
		commands: [],
		bus_events: [],
		process_types: [],
		desktop_icons: [],
		...overrides,
	};
}

describe("AppRegistry - Extensions", () => {
	beforeEach(() => {
		appRegistry.destroyAll();
	});

	it("registers extension slots from host app manifest", () => {
		const host = createMockApp(
			makeManifest({
				id: "host",
				extension_slots: [
					{ id: "actions", label: "Actions", max_extensions: 5 },
				],
			}),
		);

		appRegistry.register(host);

		const slots = appRegistry.allExtensionSlots;
		expect(slots).toHaveLength(1);
		expect(slots[0].id).toBe("actions");
		expect(slots[0].appId).toBe("host");
	});

	it("registers extensions from guest app and resolves them by slot ID", () => {
		const FakeComponent = () => {};

		// Register host first (declares the slot)
		const host = createMockApp(
			makeManifest({
				id: "host",
				extension_slots: [
					{ id: "actions", label: "Actions", max_extensions: 5 },
				],
			}),
		);

		// Register guest (declares extension)
		const guest = createMockApp(
			makeManifest({
				id: "guest",
				extensions: [
					{
						slot: "host:actions",
						component: "MyAction",
						priority: 10,
						label: "Do Something",
					},
				],
			}),
			{ MyAction: FakeComponent },
		);

		appRegistry.register(host);
		appRegistry.register(guest);

		const extensions = appRegistry.getExtensions("host:actions");
		expect(extensions).toHaveLength(1);
		expect(extensions[0].appId).toBe("guest");
		expect(extensions[0].component).toBe("MyAction");
		expect(extensions[0].label).toBe("Do Something");
		expect(extensions[0].priority).toBe(10);
	});

	it("sorts extensions by priority (descending)", () => {
		const host = createMockApp(
			makeManifest({
				id: "host",
				extension_slots: [
					{ id: "panel", label: "Panel", max_extensions: 10 },
				],
			}),
		);

		const guestA = createMockApp(
			makeManifest({
				id: "guest-a",
				extensions: [
					{
						slot: "host:panel",
						component: "LowPrio",
						priority: 1,
						label: "Low",
					},
				],
			}),
		);

		const guestB = createMockApp(
			makeManifest({
				id: "guest-b",
				extensions: [
					{
						slot: "host:panel",
						component: "HighPrio",
						priority: 100,
						label: "High",
					},
				],
			}),
		);

		appRegistry.register(host);
		appRegistry.register(guestA);
		appRegistry.register(guestB);

		const extensions = appRegistry.getExtensions("host:panel");
		expect(extensions).toHaveLength(2);
		expect(extensions[0].label).toBe("High");
		expect(extensions[1].label).toBe("Low");
	});

	it("enforces max_extensions limit", () => {
		const host = createMockApp(
			makeManifest({
				id: "host",
				extension_slots: [
					{ id: "limited", label: "Limited", max_extensions: 1 },
				],
			}),
		);

		const guestA = createMockApp(
			makeManifest({
				id: "guest-a",
				extensions: [
					{
						slot: "host:limited",
						component: "First",
						priority: 10,
						label: "First",
					},
				],
			}),
		);

		const guestB = createMockApp(
			makeManifest({
				id: "guest-b",
				extensions: [
					{
						slot: "host:limited",
						component: "Second",
						priority: 20,
						label: "Second",
					},
				],
			}),
		);

		appRegistry.register(host);
		appRegistry.register(guestA);
		appRegistry.register(guestB);

		// Only 1 should be registered (the first one, since limit checked at registration time)
		const extensions = appRegistry.getExtensions("host:limited");
		expect(extensions).toHaveLength(1);
		expect(extensions[0].label).toBe("First");
	});

	it("returns empty array for unknown slot IDs", () => {
		const extensions = appRegistry.getExtensions("nonexistent:slot");
		expect(extensions).toEqual([]);
	});

	it("extensions can target slots not yet registered (late binding)", () => {
		// Register guest first (before host)
		const guest = createMockApp(
			makeManifest({
				id: "guest",
				extensions: [
					{
						slot: "host:actions",
						component: "Action",
						priority: 5,
						label: "Action",
					},
				],
			}),
		);

		appRegistry.register(guest);

		// Extension is registered but slot doesn't exist yet
		const extensionsBefore = appRegistry.getExtensions("host:actions");
		expect(extensionsBefore).toHaveLength(1);

		// Now register host
		const host = createMockApp(
			makeManifest({
				id: "host",
				extension_slots: [
					{ id: "actions", label: "Actions", max_extensions: 5 },
				],
			}),
		);
		appRegistry.register(host);

		const extensionsAfter = appRegistry.getExtensions("host:actions");
		expect(extensionsAfter).toHaveLength(1);
	});

	it("loadComponent caches the promise", async () => {
		const FakeComp = () => {};
		const host = createMockApp(
			makeManifest({
				id: "host",
				extension_slots: [
					{ id: "test", label: "Test", max_extensions: 5 },
				],
			}),
		);
		const guest = createMockApp(
			makeManifest({
				id: "guest",
				extensions: [
					{
						slot: "host:test",
						component: "Cached",
						priority: 1,
						label: "Cached",
					},
				],
			}),
			{ Cached: FakeComp },
		);

		appRegistry.register(host);
		appRegistry.register(guest);

		const ext = appRegistry.getExtensions("host:test")[0];
		const p1 = ext.loadComponent();
		const p2 = ext.loadComponent();
		expect(p1).toBe(p2); // Same promise (cached)

		const mod = await p1;
		expect(mod.default).toBe(FakeComp);
	});

	it("destroyAll clears extension index", () => {
		const host = createMockApp(
			makeManifest({
				id: "host",
				extension_slots: [
					{ id: "test", label: "Test", max_extensions: 5 },
				],
			}),
		);
		appRegistry.register(host);
		expect(appRegistry.allExtensionSlots).toHaveLength(1);

		appRegistry.destroyAll();
		expect(appRegistry.allExtensionSlots).toHaveLength(0);
		expect(appRegistry.getExtensions("host:test")).toEqual([]);
	});
});
