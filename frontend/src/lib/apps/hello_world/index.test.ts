import { describe, it, expect, vi } from "vitest";
import { HelloWorldApp } from "./index";

// Mock kernel dependencies
vi.mock("$lib/api/client", () => ({
	API_BASE: "http://localhost:8000",
}));

describe("HelloWorldApp", () => {
	it("has correct manifest id", () => {
		const app = new HelloWorldApp();
		expect(app.manifest.id).toBe("hello-world");
	});

	it("has correct manifest name", () => {
		const app = new HelloWorldApp();
		expect(app.manifest.name).toBe("Hello World");
	});

	it("uses sparkles icon consistently", () => {
		const app = new HelloWorldApp();
		expect(app.manifest.icon).toBe("sparkles");
		expect(app.manifest.windows[0].icon).toBe("sparkles");
		expect(app.manifest.desktop_icons[0].icon).toBe("sparkles");
		expect(app.manifest.commands[0].icon).toBe("sparkles");
	});

	it("declares 1 window", () => {
		const app = new HelloWorldApp();
		expect(app.manifest.windows).toHaveLength(1);
		expect(app.manifest.windows[0].id).toBe("hello-world");
	});

	it("declares 1 command", () => {
		const app = new HelloWorldApp();
		expect(app.manifest.commands).toHaveLength(1);
		expect(app.manifest.commands[0].id).toBe("hello-world:greet");
	});

	it("declares desktop icon with openWindow action", () => {
		const app = new HelloWorldApp();
		expect(app.manifest.desktop_icons).toHaveLength(1);
		expect(app.manifest.desktop_icons[0].action).toBe("openWindow:hello-world");
	});

	it("declares start menu entry", () => {
		const app = new HelloWorldApp();
		expect(app.manifest.start_menu).toBeDefined();
		expect(app.manifest.start_menu!.section).toBe("Apps");
	});

	it("init registers commands with kernel", () => {
		const app = new HelloWorldApp();
		const registeredCommands: unknown[] = [];
		const unregisteredIds: string[] = [];

		const mockKernel = {
			bus: { on: vi.fn(), emit: vi.fn() },
			windowManager: {
				openWindow: vi.fn(),
				closeWindow: vi.fn(),
				focusWindow: vi.fn(),
				minimizeWindow: vi.fn(),
				openIDE: vi.fn(),
				ideSpawned: false,
				ideVisible: false,
				activeWindowId: null,
			},
			commandPalette: {
				register: vi.fn(),
				registerAll: vi.fn((cmds: unknown[]) =>
					registeredCommands.push(...cmds),
				),
				unregister: vi.fn((id: string) => unregisteredIds.push(id)),
			},
			processScheduler: { maxConcurrent: 2, spawn: vi.fn(), complete: vi.fn(), fail: vi.fn(), updateProgress: vi.fn(), cancel: vi.fn() },
			settings: { accentColor: "neon-cyan", enableAnimations: true },
			clipboard: { copy: vi.fn() },
			appSettings: { load: vi.fn(), save: vi.fn(), reset: vi.fn(), get: vi.fn(() => ({})), isLoading: vi.fn(() => false) },
			storage: {},
		};

		app.init(mockKernel as any);
		expect(registeredCommands.length).toBeGreaterThan(0);

		app.destroy();
		expect(unregisteredIds.length).toBeGreaterThan(0);
	});
});
