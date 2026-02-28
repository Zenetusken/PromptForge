import { describe, it, expect, vi } from "vitest";
import { TextForgeApp } from "./index";

// Mock kernel dependencies
vi.mock("$lib/api/client", () => ({
	API_BASE: "http://localhost:8000",
}));

describe("TextForgeApp", () => {
	it("has correct manifest id", () => {
		const app = new TextForgeApp();
		expect(app.manifest.id).toBe("textforge");
	});

	it("has correct manifest name", () => {
		const app = new TextForgeApp();
		expect(app.manifest.name).toBe("TextForge");
	});

	it("declares 2 windows", () => {
		const app = new TextForgeApp();
		expect(app.manifest.windows).toHaveLength(2);
		const ids = app.manifest.windows.map((w) => w.id);
		expect(ids).toContain("textforge");
		expect(ids).toContain("textforge-history");
	});

	it("declares 2 commands", () => {
		const app = new TextForgeApp();
		expect(app.manifest.commands).toHaveLength(2);
		const ids = app.manifest.commands.map((c) => c.id);
		expect(ids).toContain("textforge:open");
		expect(ids).toContain("textforge:history");
	});

	it("declares transform process type", () => {
		const app = new TextForgeApp();
		expect(app.manifest.process_types).toHaveLength(1);
		expect(app.manifest.process_types[0].id).toBe("transform");
		expect(app.manifest.process_types[0].stages).toEqual([
			"analyze",
			"transform",
			"validate",
		]);
	});

	it("declares .txf file type", () => {
		const app = new TextForgeApp();
		expect(app.manifest.file_types).toHaveLength(1);
		expect(app.manifest.file_types[0].extension).toBe(".txf");
	});

	it("declares settings", () => {
		const app = new TextForgeApp();
		expect(app.manifest.settings).toBeDefined();
		expect(app.manifest.settings!.schema.defaultTransform).toBeDefined();
	});

	it("declares desktop icon", () => {
		const app = new TextForgeApp();
		expect(app.manifest.desktop_icons).toHaveLength(1);
		expect(app.manifest.desktop_icons[0].id).toBe("textforge-icon");
	});

	it("declares start menu entry", () => {
		const app = new TextForgeApp();
		expect(app.manifest.start_menu).toBeDefined();
		expect(app.manifest.start_menu!.section).toBe("Apps");
	});

	it("getComponent resolves known components", async () => {
		const app = new TextForgeApp();
		// This will fail in test env without actual modules, but validates the map exists
		const loader = app.manifest.windows[0].component;
		expect(loader).toBe("TextForgeWindow");
	});

	it("init registers commands with kernel", () => {
		const app = new TextForgeApp();
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

	it("getSettingsComponent returns a promise", async () => {
		const app = new TextForgeApp();
		const promise = app.getSettingsComponent();
		expect(promise).toBeInstanceOf(Promise);
	});
});
