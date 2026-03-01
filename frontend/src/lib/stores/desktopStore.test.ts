import { describe, it, expect, beforeEach } from 'vitest';

// Mock sessionStorage
const storage = new Map<string, string>();
const mockStorage = {
	getItem: (key: string) => storage.get(key) ?? null,
	setItem: (key: string, value: string) => storage.set(key, value),
	removeItem: (key: string) => storage.delete(key),
};
Object.defineProperty(globalThis, 'sessionStorage', { value: mockStorage, writable: true });

// Mock localStorage (desktop store now persists here)
const localStore = new Map<string, string>();
const mockLocalStorage = {
	getItem: (key: string) => localStore.get(key) ?? null,
	setItem: (key: string, value: string) => localStore.set(key, value),
	removeItem: (key: string) => localStore.delete(key),
};
Object.defineProperty(globalThis, 'localStorage', { value: mockLocalStorage, writable: true });

// Mock crypto.randomUUID
let uuidCounter = 0;
Object.defineProperty(globalThis, 'crypto', {
	value: {
		randomUUID: () => `test-uuid-${++uuidCounter}`,
	},
	writable: true,
});

import { desktopStore, CELL_WIDTH, CELL_HEIGHT, GRID_PADDING, getMaxRow, getMaxCol, TASKBAR_HEIGHT } from './desktopStore.svelte';
import { windowManager } from './windowManager.svelte';
import { appRegistry } from '$lib/kernel/services/appRegistry.svelte';
import { promptForgeApp } from '$lib/apps/promptforge';
import { helloWorldApp } from '$lib/apps/hello_world';
import { textForgeApp } from '$lib/apps/textforge';

describe('DesktopStore', () => {
	beforeEach(() => {
		storage.clear();
		localStore.clear();
		uuidCounter = 0;
		// Register apps so desktop icons are sourced from the registry
		if (!appRegistry.get('promptforge')) {
			appRegistry.register(promptForgeApp);
		}
		if (!appRegistry.get('hello-world')) {
			appRegistry.register(helloWorldApp);
		}
		if (!appRegistry.get('textforge')) {
			appRegistry.register(textForgeApp);
		}
		desktopStore.resetDesktop();
		desktopStore.recycleBin = [];
		desktopStore.closeContextMenu();
		desktopStore.confirmDialog.open = false;
	});

	describe('initial state', () => {
		it('starts with 12 system + 2 folder + 4 file icons (registry-driven)', () => {
			expect(desktopStore.icons).toHaveLength(18);
			const systemIcons = desktopStore.icons.filter((i) => i.type === 'system');
			const folderIcons = desktopStore.icons.filter((i) => i.type === 'folder');
			const fileIcons = desktopStore.icons.filter((i) => i.type === 'file');
			expect(systemIcons).toHaveLength(12); // 9 PF system + 1 HW + 1 TF + 1 Recycle Bin
			expect(folderIcons).toHaveLength(2);
			expect(fileIcons).toHaveLength(4);
		});

		it('has correct system icon IDs', () => {
			const ids = desktopStore.icons.filter((i) => i.type === 'system').map((i) => i.id);
			expect(ids).toContain('sys-forge-ide');
			expect(ids).toContain('sys-recycle-bin');
			expect(ids).toContain('hello-world'); // from HelloWorld app
			expect(ids).toContain('textforge-icon'); // from TextForge app
			expect(ids).not.toContain('sys-projects'); // these are 'folder' type
			expect(ids).not.toContain('sys-history');
		});

		it('has correct folder icon IDs and types', () => {
			const projects = desktopStore.icons.find((i) => i.id === 'sys-projects');
			const history = desktopStore.icons.find((i) => i.id === 'sys-history');
			expect(projects?.type).toBe('folder');
			expect(history?.type).toBe('folder');
		});

		it('has correct file icon types and extensions', () => {
			const fileIcons = desktopStore.icons.filter((i) => i.type === 'file');
			for (const icon of fileIcons) {
				expect(icon.extension).toBe('.lnk');
				expect(icon.icon).toBe('file-text');
			}
		});

		it('has .lnk in file icon labels', () => {
			expect(desktopStore.icons.find((i) => i.id === 'shortcut-code-review')?.label).toBe('Code Review.lnk');
			expect(desktopStore.icons.find((i) => i.id === 'shortcut-marketing-email')?.label).toBe('Marketing Email.lnk');
			expect(desktopStore.icons.find((i) => i.id === 'shortcut-technical-docs')?.label).toBe('Technical Docs.lnk');
			expect(desktopStore.icons.find((i) => i.id === 'shortcut-error-messages')?.label).toBe('Error Messages.lnk');
		});

		it('has correct default positions', () => {
			const ide = desktopStore.icons.find((i) => i.id === 'sys-forge-ide');
			expect(ide?.position).toEqual({ col: 0, row: 0 });

			const projects = desktopStore.icons.find((i) => i.id === 'sys-projects');
			expect(projects?.position).toEqual({ col: 0, row: 1 });

			const history = desktopStore.icons.find((i) => i.id === 'sys-history');
			expect(history?.position).toEqual({ col: 0, row: 2 });
		});

		it('starts with no selection', () => {
			expect(desktopStore.selectedIconId).toBeNull();
			expect(desktopStore.selectedIcon).toBeUndefined();
		});

		it('starts with empty recycle bin', () => {
			expect(desktopStore.binIsEmpty).toBe(true);
			expect(desktopStore.binItemCount).toBe(0);
		});

		it('starts with closed context menu', () => {
			expect(desktopStore.contextMenu.open).toBe(false);
		});

		it('starts with not dragging', () => {
			expect(desktopStore.isDragging).toBe(false);
			expect(desktopStore.dragState).toBeNull();
		});
	});

	describe('getMaxRow', () => {
		it('computes max row from window.innerHeight', () => {
			const expected = Math.floor((window.innerHeight - TASKBAR_HEIGHT - GRID_PADDING * 2) / CELL_HEIGHT) - 1;
			expect(getMaxRow()).toBe(expected);
		});

		it('recycle bin default position respects max row', () => {
			const bin = desktopStore.icons.find((i) => i.id === 'sys-recycle-bin');
			expect(bin?.position.row).toBeLessThanOrEqual(getMaxRow());
		});

		it('no icon exceeds max row after sort', () => {
			desktopStore.sortIcons('name');
			for (const icon of desktopStore.icons) {
				expect(icon.position.row).toBeLessThanOrEqual(getMaxRow());
			}
		});
	});

	describe('selectIcon / deselectAll', () => {
		it('selects an icon by ID', () => {
			desktopStore.selectIcon('sys-forge-ide');
			expect(desktopStore.selectedIconId).toBe('sys-forge-ide');
			expect(desktopStore.selectedIcon?.id).toBe('sys-forge-ide');
		});

		it('deselects all', () => {
			desktopStore.selectIcon('sys-forge-ide');
			desktopStore.deselectAll();
			expect(desktopStore.selectedIconId).toBeNull();
			expect(desktopStore.selectedIcon).toBeUndefined();
		});

		it('changes selection when selecting a different icon', () => {
			desktopStore.selectIcon('sys-forge-ide');
			desktopStore.selectIcon('sys-projects');
			expect(desktopStore.selectedIconId).toBe('sys-projects');
		});
	});

	describe('drag lifecycle', () => {
		it('starts drag on an icon', () => {
			desktopStore.startDrag('sys-forge-ide', 10, 10);
			expect(desktopStore.dragState).not.toBeNull();
			expect(desktopStore.dragState?.iconId).toBe('sys-forge-ide');
			expect(desktopStore.dragState?.hasMoved).toBe(false);
			// Not yet dragging (no movement)
			expect(desktopStore.isDragging).toBe(false);
		});

		it('updates ghost position after movement threshold', () => {
			desktopStore.startDrag('sys-forge-ide', 0, 0);
			const surfaceRect = { left: 0, top: 0, width: 800, height: 600 } as DOMRect;

			// Move enough to exceed 5px threshold
			desktopStore.updateDragGhost(100, 100, surfaceRect);
			expect(desktopStore.isDragging).toBe(true);
			expect(desktopStore.dragState?.ghostCol).toBeGreaterThan(0);
		});

		it('does not enter drag mode below 5px threshold', () => {
			desktopStore.startDrag('sys-forge-ide', 0, 0);
			const surfaceRect = { left: 0, top: 0, width: 800, height: 600 } as DOMRect;

			// Move less than 5px from start
			desktopStore.updateDragGhost(GRID_PADDING + 2, GRID_PADDING + 2, surfaceRect);
			expect(desktopStore.isDragging).toBe(false);
		});

		it('endDrag snaps to empty cell', () => {
			desktopStore.startDrag('sys-forge-ide', 0, 0);
			const surfaceRect = { left: 0, top: 0, width: 800, height: 600 } as DOMRect;

			// Move to col 3, row 0 (should be empty)
			desktopStore.updateDragGhost(3 * CELL_WIDTH + GRID_PADDING, GRID_PADDING, surfaceRect);
			desktopStore.endDrag();

			const ide = desktopStore.icons.find((i) => i.id === 'sys-forge-ide');
			expect(ide?.position.col).toBe(3);
			expect(desktopStore.dragState).toBeNull();
		});

		it('endDrag snaps back if cell is occupied', () => {
			// sys-projects is at (0, 1)
			desktopStore.startDrag('sys-forge-ide', 0, 0);
			// Manually set ghost to occupied position
			desktopStore.dragState!.hasMoved = true;
			desktopStore.dragState!.ghostCol = 0;
			desktopStore.dragState!.ghostRow = 1;
			desktopStore.endDrag();

			const ide = desktopStore.icons.find((i) => i.id === 'sys-forge-ide');
			// Should stay at original position
			expect(ide?.position).toEqual({ col: 0, row: 0 });
		});

		it('endDrag with no movement does nothing', () => {
			desktopStore.startDrag('sys-forge-ide', 0, 0);
			desktopStore.endDrag();

			const ide = desktopStore.icons.find((i) => i.id === 'sys-forge-ide');
			expect(ide?.position).toEqual({ col: 0, row: 0 });
		});
	});

	describe('context menu', () => {
		it('opens context menu for an icon with icon-specific actions', () => {
			desktopStore.openContextMenu(100, 200, 'sys-forge-ide');
			expect(desktopStore.contextMenu.open).toBe(true);
			expect(desktopStore.contextMenu.x).toBe(100);
			expect(desktopStore.contextMenu.y).toBe(200);
			expect(desktopStore.contextMenu.targetIconId).toBe('sys-forge-ide');
			expect(desktopStore.contextMenu.actions.length).toBeGreaterThan(0);
			expect(desktopStore.contextMenu.actions[0].id).toBe('open');
		});

		it('opens context menu for desktop with desktop actions', () => {
			desktopStore.openContextMenu(100, 200, null);
			expect(desktopStore.contextMenu.open).toBe(true);
			expect(desktopStore.contextMenu.targetIconId).toBeNull();
			expect(desktopStore.contextMenu.actions.some((a) => a.id === 'new-forge')).toBe(true);
		});

		it('selects icon when opening context menu on it', () => {
			// Component (DesktopIcon) calls selectIcon before openContextMenu
			desktopStore.selectIcon('sys-projects');
			desktopStore.openContextMenu(100, 200, 'sys-projects');
			expect(desktopStore.selectedIconId).toBe('sys-projects');
		});

		it('deselects all when opening context menu on desktop', () => {
			desktopStore.selectIcon('sys-forge-ide');
			desktopStore.openContextMenu(100, 200, null);
			expect(desktopStore.selectedIconId).toBeNull();
		});

		it('closes context menu', () => {
			desktopStore.openContextMenu(100, 200, 'sys-forge-ide');
			desktopStore.closeContextMenu();
			expect(desktopStore.contextMenu.open).toBe(false);
		});

		it('file icons have Delete action', () => {
			desktopStore.openContextMenu(100, 200, 'shortcut-code-review');
			const deleteAction = desktopStore.contextMenu.actions.find((a) => a.id === 'delete');
			expect(deleteAction).toBeDefined();
			expect(deleteAction?.danger).toBe(true);
		});

		it('folder icons have Delete action', () => {
			desktopStore.openContextMenu(100, 200, 'sys-projects');
			const deleteAction = desktopStore.contextMenu.actions.find((a) => a.id === 'delete');
			expect(deleteAction).toBeDefined();
			expect(deleteAction?.danger).toBe(true);
		});

		it('folder icons have Rename action', () => {
			desktopStore.openContextMenu(100, 200, 'sys-projects');
			const renameAction = desktopStore.contextMenu.actions.find((a) => a.id === 'rename');
			expect(renameAction).toBeDefined();
		});

		it('system icons do not have Delete action', () => {
			desktopStore.openContextMenu(100, 200, 'sys-forge-ide');
			const deleteAction = desktopStore.contextMenu.actions.find((a) => a.id === 'delete');
			expect(deleteAction).toBeUndefined();
		});

		it('system icons do not have Rename action', () => {
			desktopStore.openContextMenu(100, 200, 'sys-forge-ide');
			const renameAction = desktopStore.contextMenu.actions.find((a) => a.id === 'rename');
			expect(renameAction).toBeUndefined();
		});
	});

	describe('recycle bin', () => {
		it('trashIcon removes file icon and adds to bin with file sourceType', () => {
			desktopStore.trashIcon('shortcut-code-review');
			expect(desktopStore.icons.find((i) => i.id === 'shortcut-code-review')).toBeUndefined();
			expect(desktopStore.binItemCount).toBe(1);
			expect(desktopStore.binIsEmpty).toBe(false);
			expect(desktopStore.recycleBin[0].sourceType).toBe('file');
			expect(desktopStore.recycleBin[0].name).toBe('Code Review.lnk');
		});

		it('trashIcon removes folder icon and adds to bin with folder sourceType', () => {
			desktopStore.trashIcon('sys-projects');
			expect(desktopStore.icons.find((i) => i.id === 'sys-projects')).toBeUndefined();
			expect(desktopStore.binItemCount).toBe(1);
			expect(desktopStore.recycleBin[0].sourceType).toBe('folder');
			expect(desktopStore.recycleBin[0].name).toBe('Projects');
		});

		it('trashIcon is no-op for system icons', () => {
			desktopStore.trashIcon('sys-forge-ide');
			expect(desktopStore.icons.find((i) => i.id === 'sys-forge-ide')).toBeDefined();
			expect(desktopStore.binItemCount).toBe(0);
		});

		it('trashIcon deselects the trashed icon', () => {
			desktopStore.selectIcon('shortcut-code-review');
			desktopStore.trashIcon('shortcut-code-review');
			expect(desktopStore.selectedIconId).toBeNull();
		});

		it('restoreItem puts file icon back', () => {
			desktopStore.trashIcon('shortcut-code-review');
			const binItemId = desktopStore.recycleBin[0].id;

			desktopStore.restoreItem(binItemId);
			expect(desktopStore.recycleBin).toHaveLength(0);
			const restored = desktopStore.icons.find((i) => i.id === 'shortcut-code-review');
			expect(restored).toBeDefined();
			expect(restored?.label).toBe('Code Review.lnk');
		});

		it('restoreItem puts folder icon back', () => {
			desktopStore.trashIcon('sys-projects');
			const binItemId = desktopStore.recycleBin[0].id;

			desktopStore.restoreItem(binItemId);
			expect(desktopStore.recycleBin).toHaveLength(0);
			const restored = desktopStore.icons.find((i) => i.id === 'sys-projects');
			expect(restored).toBeDefined();
			expect(restored?.type).toBe('folder');
		});

		it('permanentlyDeleteItem removes from bin', () => {
			desktopStore.trashIcon('shortcut-code-review');
			const binItemId = desktopStore.recycleBin[0].id;

			desktopStore.permanentlyDeleteItem(binItemId);
			expect(desktopStore.recycleBin).toHaveLength(0);
			// Not restored to desktop
			expect(desktopStore.icons.find((i) => i.id === 'shortcut-code-review')).toBeUndefined();
		});

		it('emptyRecycleBin clears all items', () => {
			desktopStore.trashIcon('shortcut-code-review');
			desktopStore.trashIcon('shortcut-marketing-email');
			expect(desktopStore.binItemCount).toBe(2);

			desktopStore.emptyRecycleBin();
			expect(desktopStore.binItemCount).toBe(0);
			expect(desktopStore.binIsEmpty).toBe(true);
		});

		it('stores iconDef for file restore', () => {
			desktopStore.trashIcon('shortcut-code-review');
			expect(desktopStore.recycleBin[0].iconDef).toBeDefined();
			expect(desktopStore.recycleBin[0].iconDef?.id).toBe('shortcut-code-review');
			expect(desktopStore.recycleBin[0].iconDef?.icon).toBe('file-text');
		});
	});

	describe('sort', () => {
		it('sorts by name alphabetically', () => {
			desktopStore.sortIcons('name');
			const labels = desktopStore.icons.map((i) => i.label);
			const sorted = [...labels].sort((a, b) => a.localeCompare(b));
			expect(labels).toEqual(sorted);
		});

		it('sorts by type: system → folder → file', () => {
			desktopStore.sortIcons('type');
			const types = desktopStore.icons.map((i) => i.type);
			const systemCount = types.filter((t) => t === 'system').length;
			const folderCount = types.filter((t) => t === 'folder').length;
			// System icons first
			for (let i = 0; i < systemCount; i++) {
				expect(types[i]).toBe('system');
			}
			// Then folder icons
			for (let i = systemCount; i < systemCount + folderCount; i++) {
				expect(types[i]).toBe('folder');
			}
			// Then file icons
			for (let i = systemCount + folderCount; i < types.length; i++) {
				expect(types[i]).toBe('file');
			}
		});

		it('reassigns positions in column-first order', () => {
			desktopStore.sortIcons('name');
			// First icon should be at (0, 0)
			expect(desktopStore.icons[0].position).toEqual({ col: 0, row: 0 });
			// Second at (0, 1), etc.
			expect(desktopStore.icons[1].position).toEqual({ col: 0, row: 1 });
		});
	});

	describe('occupiedCells', () => {
		it('maps all icon positions', () => {
			expect(desktopStore.occupiedCells.size).toBe(18);
			expect(desktopStore.occupiedCells.get('0,0')).toBe('sys-forge-ide');
			expect(desktopStore.occupiedCells.get('0,1')).toBe('sys-projects');
		});
	});

	describe('persistence', () => {
		it('persists icon positions after drag', () => {
			desktopStore.startDrag('sys-forge-ide', 0, 0);
			desktopStore.dragState!.hasMoved = true;
			desktopStore.dragState!.ghostCol = 3;
			desktopStore.dragState!.ghostRow = 0;
			desktopStore.endDrag();

			const saved = localStore.get('pf_desktop');
			expect(saved).toBeTruthy();
			const parsed = JSON.parse(saved!);
			expect(parsed.iconPositions['sys-forge-ide']).toEqual({ col: 3, row: 0 });
		});

		it('persists removed non-system icons', () => {
			desktopStore.trashIcon('shortcut-code-review');
			const saved = JSON.parse(localStore.get('pf_desktop')!);
			expect(saved.removedShortcuts).toContain('shortcut-code-review');
		});

		it('persists removed folder icons', () => {
			desktopStore.trashIcon('sys-projects');
			const saved = JSON.parse(localStore.get('pf_desktop')!);
			expect(saved.removedShortcuts).toContain('sys-projects');
		});

		it('persists recycle bin items', () => {
			desktopStore.trashIcon('shortcut-code-review');
			const saved = JSON.parse(localStore.get('pf_desktop')!);
			expect(saved.recycleBin).toHaveLength(1);
			expect(saved.recycleBin[0].name).toBe('Code Review.lnk');
		});
	});

	describe('resetDesktop', () => {
		it('restores all default icons', () => {
			desktopStore.trashIcon('shortcut-code-review');
			desktopStore.trashIcon('shortcut-marketing-email');
			expect(desktopStore.icons).toHaveLength(16);

			desktopStore.resetDesktop();
			expect(desktopStore.icons).toHaveLength(18);
		});

		it('clears selection and drag state', () => {
			desktopStore.selectIcon('sys-forge-ide');
			desktopStore.resetDesktop();
			expect(desktopStore.selectedIconId).toBeNull();
			expect(desktopStore.dragState).toBeNull();
		});
	});

	describe('renameIcon', () => {
		it('updates label on file icon', () => {
			desktopStore.renameIcon('shortcut-code-review', 'My Reviews');
			const icon = desktopStore.icons.find((i) => i.id === 'shortcut-code-review');
			expect(icon?.label).toBe('My Reviews');
		});

		it('updates label on folder icon', () => {
			desktopStore.renameIcon('sys-projects', 'My Files');
			const icon = desktopStore.icons.find((i) => i.id === 'sys-projects');
			expect(icon?.label).toBe('My Files');
		});

		it('trims whitespace from new label', () => {
			desktopStore.renameIcon('shortcut-code-review', '  Trimmed  ');
			const icon = desktopStore.icons.find((i) => i.id === 'shortcut-code-review');
			expect(icon?.label).toBe('Trimmed');
		});

		it('rejects empty string', () => {
			desktopStore.renameIcon('shortcut-code-review', '');
			const icon = desktopStore.icons.find((i) => i.id === 'shortcut-code-review');
			expect(icon?.label).toBe('Code Review.lnk');
		});

		it('rejects whitespace-only string', () => {
			desktopStore.renameIcon('shortcut-code-review', '   ');
			const icon = desktopStore.icons.find((i) => i.id === 'shortcut-code-review');
			expect(icon?.label).toBe('Code Review.lnk');
		});

		it('is no-op for system icons', () => {
			desktopStore.renameIcon('sys-forge-ide', 'Hacked');
			const icon = desktopStore.icons.find((i) => i.id === 'sys-forge-ide');
			expect(icon?.label).toBe('Forge IDE');
		});

		it('is no-op for non-existent icon', () => {
			expect(() => desktopStore.renameIcon('nonexistent', 'Test')).not.toThrow();
		});

		it('persists custom label to localStorage', () => {
			desktopStore.renameIcon('shortcut-code-review', 'My Reviews');
			const saved = JSON.parse(localStore.get('pf_desktop')!);
			expect(saved.customLabels['shortcut-code-review']).toBe('My Reviews');
		});

		it('does not persist unchanged labels', () => {
			desktopStore.renameIcon('shortcut-code-review', 'Code Review.lnk');
			const saved = JSON.parse(localStore.get('pf_desktop')!);
			expect(saved.customLabels['shortcut-code-review']).toBeUndefined();
		});

		it('trashing a renamed icon preserves the custom label in bin', () => {
			desktopStore.renameIcon('shortcut-code-review', 'Renamed');
			desktopStore.trashIcon('shortcut-code-review');
			const binItem = desktopStore.recycleBin.find((i) => i.sourceId === 'shortcut-code-review');
			expect(binItem?.iconDef?.label).toBe('Renamed');
			expect(binItem?.name).toBe('Renamed');
		});
	});

	describe('customLabels persistence round-trip', () => {
		it('custom labels survive _initFromPersistence round-trip', () => {
			desktopStore.renameIcon('shortcut-code-review', 'Custom Name');
			// Simulate reload by calling resetDesktop then manually re-init
			// We verify the persisted data contains the custom label
			const saved = JSON.parse(localStore.get('pf_desktop')!);
			expect(saved.customLabels['shortcut-code-review']).toBe('Custom Name');
		});

		it('resetDesktop clears custom labels', () => {
			desktopStore.renameIcon('shortcut-code-review', 'Custom Name');
			desktopStore.resetDesktop();
			const icon = desktopStore.icons.find((i) => i.id === 'shortcut-code-review');
			expect(icon?.label).toBe('Code Review.lnk');
			// Verify persistence too
			const saved = JSON.parse(localStore.get('pf_desktop')!);
			expect(saved.customLabels).toEqual({});
		});
	});

	describe('requestRename', () => {
		it('starts as null', () => {
			expect(desktopStore.requestRename).toBeNull();
		});

		it('is set by rename context action dispatch on file icon', () => {
			desktopStore.openContextMenu(100, 200, 'shortcut-code-review');
			desktopStore.executeContextAction('rename');
			expect(desktopStore.requestRename).toBe('shortcut-code-review');
		});

		it('is set by rename context action dispatch on folder icon', () => {
			desktopStore.openContextMenu(100, 200, 'sys-projects');
			desktopStore.executeContextAction('rename');
			expect(desktopStore.requestRename).toBe('sys-projects');
		});
	});

	describe('file and folder context actions', () => {
		it('file icons include Rename action', () => {
			desktopStore.openContextMenu(100, 200, 'shortcut-code-review');
			const renameAction = desktopStore.contextMenu.actions.find((a) => a.id === 'rename');
			expect(renameAction).toBeDefined();
			expect(renameAction?.label).toBe('Rename');
		});

		it('folder icons include Rename action', () => {
			desktopStore.openContextMenu(100, 200, 'sys-projects');
			const renameAction = desktopStore.contextMenu.actions.find((a) => a.id === 'rename');
			expect(renameAction).toBeDefined();
		});

		it('system icons do not have Rename action', () => {
			desktopStore.openContextMenu(100, 200, 'sys-forge-ide');
			const renameAction = desktopStore.contextMenu.actions.find((a) => a.id === 'rename');
			expect(renameAction).toBeUndefined();
		});
	});

	describe('executeContextAction', () => {
		it('closes context menu after executing action', () => {
			desktopStore.openContextMenu(100, 200, null);
			desktopStore.executeContextAction('sort-by-name');
			expect(desktopStore.contextMenu.open).toBe(false);
		});

		it('delete action trashes file icon', () => {
			desktopStore.openContextMenu(100, 200, 'shortcut-code-review');
			desktopStore.executeContextAction('delete');
			expect(desktopStore.icons.find((i) => i.id === 'shortcut-code-review')).toBeUndefined();
			expect(desktopStore.binItemCount).toBe(1);
		});

		it('delete action trashes folder icon', () => {
			desktopStore.openContextMenu(100, 200, 'sys-projects');
			desktopStore.executeContextAction('delete');
			expect(desktopStore.icons.find((i) => i.id === 'sys-projects')).toBeUndefined();
			expect(desktopStore.binItemCount).toBe(1);
			expect(desktopStore.recycleBin[0].sourceType).toBe('folder');
		});

		it('empty-bin action opens confirm dialog', () => {
			desktopStore.trashIcon('shortcut-code-review');
			desktopStore.openContextMenu(100, 200, 'sys-recycle-bin');
			desktopStore.executeContextAction('empty-bin');
			expect(desktopStore.confirmDialog.open).toBe(true);
			expect(desktopStore.confirmDialog.title).toBe('Empty Recycle Bin');
		});

		it('sort-by-name sorts icons', () => {
			desktopStore.openContextMenu(100, 200, null);
			desktopStore.executeContextAction('sort-by-name');
			const labels = desktopStore.icons.map((i) => i.label);
			const sorted = [...labels].sort((a, b) => a.localeCompare(b));
			expect(labels).toEqual(sorted);
		});

		it('refresh-desktop resets', () => {
			desktopStore.trashIcon('shortcut-code-review');
			desktopStore.openContextMenu(100, 200, null);
			desktopStore.executeContextAction('refresh-desktop');
			expect(desktopStore.icons).toHaveLength(18);
		});
	});

	describe('getMaxCol', () => {
		it('computes max column from window.innerWidth', () => {
			const expected = Math.floor((window.innerWidth - GRID_PADDING * 2) / CELL_WIDTH) - 1;
			expect(getMaxCol()).toBe(expected);
		});

		it('returns >= 0', () => {
			expect(getMaxCol()).toBeGreaterThanOrEqual(0);
		});
	});

	describe('drag column clamping', () => {
		it('clamps column to getMaxCol during drag', () => {
			desktopStore.startDrag('sys-forge-ide', 0, 0);
			const surfaceRect = { left: 0, top: 0, width: 800, height: 600 } as DOMRect;
			// Move far to the right (beyond viewport)
			desktopStore.updateDragGhost(5000, GRID_PADDING, surfaceRect);
			expect(desktopStore.dragState?.ghostCol).toBeLessThanOrEqual(getMaxCol());
		});

		it('clamps row to getMaxRow during drag', () => {
			desktopStore.startDrag('sys-forge-ide', 0, 0);
			const surfaceRect = { left: 0, top: 0, width: 800, height: 600 } as DOMRect;
			// Move far down (beyond viewport)
			desktopStore.updateDragGhost(GRID_PADDING, 5000, surfaceRect);
			expect(desktopStore.dragState?.ghostRow).toBeLessThanOrEqual(getMaxRow());
		});
	});

	describe('double-drag guard', () => {
		it('startDrag cancels previous drag without committing', () => {
			// Start drag on IDE and move it
			desktopStore.startDrag('sys-forge-ide', 0, 0);
			desktopStore.dragState!.hasMoved = true;
			desktopStore.dragState!.ghostCol = 5;
			desktopStore.dragState!.ghostRow = 0;

			// Start another drag on projects (should discard the IDE drag)
			desktopStore.startDrag('sys-projects', 0, 0);

			// IDE should NOT have moved to (5, 0)
			const ide = desktopStore.icons.find((i) => i.id === 'sys-forge-ide');
			expect(ide?.position).toEqual({ col: 0, row: 0 });

			// New drag should be active on projects
			expect(desktopStore.dragState?.iconId).toBe('sys-projects');
		});
	});

	describe('drag cancellation on sort/trash', () => {
		it('sortIcons cancels active drag', () => {
			desktopStore.startDrag('sys-forge-ide', 0, 0);
			desktopStore.dragState!.hasMoved = true;
			desktopStore.sortIcons('name');
			expect(desktopStore.dragState).toBeNull();
		});

		it('trashIcon cancels drag of trashed icon', () => {
			desktopStore.startDrag('shortcut-code-review', 0, 0);
			desktopStore.trashIcon('shortcut-code-review');
			expect(desktopStore.dragState).toBeNull();
		});

		it('trashIcon does NOT cancel drag of another icon', () => {
			desktopStore.startDrag('sys-forge-ide', 0, 0);
			desktopStore.trashIcon('shortcut-code-review');
			expect(desktopStore.dragState).not.toBeNull();
			expect(desktopStore.dragState?.iconId).toBe('sys-forge-ide');
		});
	});

	describe('_findEmptyCell bounds', () => {
		it('restore places icon within grid bounds', () => {
			desktopStore.trashIcon('shortcut-code-review');
			const binItemId = desktopStore.recycleBin[0].id;
			desktopStore.restoreItem(binItemId);

			const restored = desktopStore.icons.find((i) => i.id === 'shortcut-code-review');
			expect(restored).toBeDefined();
			expect(restored!.position.row).toBeLessThanOrEqual(getMaxRow());
			expect(restored!.position.col).toBeLessThanOrEqual(getMaxCol());
		});

		it('restore does not create overlaps', () => {
			desktopStore.trashIcon('shortcut-code-review');
			const binItemId = desktopStore.recycleBin[0].id;
			desktopStore.restoreItem(binItemId);

			const positions = desktopStore.icons.map((i) => `${i.position.col},${i.position.row}`);
			const unique = new Set(positions);
			expect(unique.size).toBe(positions.length);
		});
	});

	describe('persistence dedup on load', () => {
		it('deduplicates icons clamped to same position via reclamp', () => {
			// Place two icons at different far-right positions that will both clamp to maxCol
			const iconA = desktopStore.icons.find((i) => i.id === 'sys-forge-ide')!;
			const iconB = desktopStore.icons.find((i) => i.id === 'sys-projects')!;
			iconA.position = { col: 999, row: 0 };
			iconB.position = { col: 888, row: 0 };

			desktopStore.reclampPositions();

			// Both clamped to (maxCol, 0) — dedup should resolve the collision
			const allPos = desktopStore.icons.map((i) => `${i.position.col},${i.position.row}`);
			expect(new Set(allPos).size).toBe(allPos.length);
		});
	});

	describe('reclampPositions', () => {
		it('clamps out-of-bounds icons', () => {
			const icon = desktopStore.icons.find((i) => i.id === 'sys-forge-ide')!;
			icon.position = { col: 999, row: 999 };

			desktopStore.reclampPositions();

			expect(icon.position.col).toBeLessThanOrEqual(getMaxCol());
			expect(icon.position.row).toBeLessThanOrEqual(getMaxRow());
		});

		it('does not change in-bounds icons', () => {
			const before = desktopStore.icons.map((i) => ({
				id: i.id,
				col: i.position.col,
				row: i.position.row,
			}));

			desktopStore.reclampPositions();

			const after = desktopStore.icons.map((i) => ({
				id: i.id,
				col: i.position.col,
				row: i.position.row,
			}));
			expect(after).toEqual(before);
		});

		it('deduplicates after clamping creates overlaps', () => {
			// Place two icons at different out-of-bounds cols, same row
			const iconA = desktopStore.icons.find((i) => i.id === 'sys-forge-ide')!;
			const iconB = desktopStore.icons.find((i) => i.id === 'sys-projects')!;
			iconA.position = { col: 999, row: 0 };
			iconB.position = { col: 888, row: 0 };

			desktopStore.reclampPositions();

			// Both clamped to maxCol, should be deduped
			const positions = desktopStore.icons.map((i) => `${i.position.col},${i.position.row}`);
			expect(new Set(positions).size).toBe(positions.length);
		});

		it('persists after changes', () => {
			const icon = desktopStore.icons.find((i) => i.id === 'sys-forge-ide')!;
			icon.position = { col: 999, row: 0 };

			desktopStore.reclampPositions();

			const saved = JSON.parse(localStore.get('pf_desktop')!);
			expect(saved.iconPositions['sys-forge-ide'].col).toBeLessThanOrEqual(getMaxCol());
		});

		it('does not persist when nothing changes', () => {
			// Clear storage and reclamp (all icons in bounds)
			localStore.clear();
			desktopStore.reclampPositions();
			expect(mockLocalStorage.getItem('pf_desktop')).toBeNull();
		});
	});

	describe('gridFull', () => {
		it('is false with default 8 icons and normal viewport', () => {
			expect(desktopStore.gridFull).toBe(false);
		});

		it('is true when icon count equals total grid cells', () => {
			// Total cells = (maxRow + 1) * (maxCol + 1)
			const totalCells = (getMaxRow() + 1) * (getMaxCol() + 1);
			// We have 8 icons. Add enough fake icons to fill the grid.
			const needed = totalCells - desktopStore.icons.length;
			for (let i = 0; i < needed; i++) {
				desktopStore.icons.push({
					id: `fill-${i}`,
					label: `Fill ${i}`,
					icon: 'file-text',
					color: 'cyan',
					type: 'file',
					position: { col: Math.floor(i / (getMaxRow() + 1)) + 1, row: i % (getMaxRow() + 1) },
					contextActions: [],
				});
			}
			expect(desktopStore.gridFull).toBe(true);
		});
	});

	describe('restoreItem return value', () => {
		it('returns false when grid has space', () => {
			desktopStore.trashIcon('shortcut-code-review');
			const binItemId = desktopStore.recycleBin[0].id;
			const offScreen = desktopStore.restoreItem(binItemId);
			expect(offScreen).toBe(false);
		});

		it('returns true when grid is full', () => {
			// Fill every empty cell in the grid
			const maxRow = getMaxRow();
			const maxCol = getMaxCol();
			let fillIdx = 0;
			for (let col = 0; col <= maxCol; col++) {
				for (let row = 0; row <= maxRow; row++) {
					if (!desktopStore.occupiedCells.has(`${col},${row}`)) {
						desktopStore.icons.push({
							id: `fill-${fillIdx}`,
							label: `Fill ${fillIdx}`,
							icon: 'file-text',
							color: 'cyan',
							type: 'file',
							position: { col, row },
							contextActions: [],
						});
						fillIdx++;
					}
				}
			}
			// Add a synthetic bin item to restore onto the full grid
			desktopStore.recycleBin.push({
				id: 'bin-test',
				sourceType: 'file',
				sourceId: 'test-file',
				name: 'Test',
				trashedAt: Date.now(),
				iconDef: {
					id: 'test-file',
					label: 'Test',
					icon: 'file-text',
					color: 'cyan',
					type: 'file',
					position: { col: 0, row: 0 },
					contextActions: [],
				},
			});
			const offScreen = desktopStore.restoreItem('bin-test');
			expect(offScreen).toBe(true);
		});
	});

	describe('sort column bounds', () => {
		it('no icon exceeds maxRow after sort', () => {
			desktopStore.sortIcons('name');
			for (const icon of desktopStore.icons) {
				expect(icon.position.row).toBeLessThanOrEqual(getMaxRow());
			}
		});
	});

	describe('auto-layout', () => {
		it('resetDesktop places Recycle Bin at bottom-left', () => {
			desktopStore.resetDesktop();
			const bin = desktopStore.icons.find((i) => i.id === 'sys-recycle-bin');
			expect(bin?.position).toEqual({ col: 0, row: getMaxRow() });
		});

		it('resetDesktop places non-bin icons column-first skipping bin cell', () => {
			desktopStore.resetDesktop();
			const nonBin = desktopStore.icons.filter((i) => i.id !== 'sys-recycle-bin');
			const maxRow = getMaxRow();
			// Column-first fill: col 0 rows 0 to (maxRow-1) since bin is at (0, maxRow)
			// Then col 1 rows 0 to maxRow
			const col0Slots = maxRow; // rows 0 to maxRow-1 (bin occupies maxRow)
			for (let i = 0; i < Math.min(nonBin.length, col0Slots); i++) {
				expect(nonBin[i].position.col).toBe(0);
				expect(nonBin[i].position.row).toBe(i);
			}
			// Overflow icons go to col 1+
			for (let i = col0Slots; i < nonBin.length; i++) {
				expect(nonBin[i].position.col).toBeGreaterThanOrEqual(1);
			}
		});

		it('resetDesktop produces no overlapping positions', () => {
			desktopStore.resetDesktop();
			const positions = desktopStore.icons.map((i) => `${i.position.col},${i.position.row}`);
			expect(new Set(positions).size).toBe(positions.length);
		});

		it('all icons within grid bounds after resetDesktop', () => {
			desktopStore.resetDesktop();
			for (const icon of desktopStore.icons) {
				expect(icon.position.col).toBeLessThanOrEqual(getMaxCol());
				expect(icon.position.row).toBeLessThanOrEqual(getMaxRow());
			}
		});

		it('sortIcons places bin at bottom-left regardless of sort order', () => {
			desktopStore.sortIcons('name');
			const bin = desktopStore.icons.find((i) => i.id === 'sys-recycle-bin');
			expect(bin?.position).toEqual({ col: 0, row: getMaxRow() });
		});

		it('sortIcons produces no overlapping positions', () => {
			desktopStore.sortIcons('name');
			const positions = desktopStore.icons.map((i) => `${i.position.col},${i.position.row}`);
			expect(new Set(positions).size).toBe(positions.length);
		});

		it('sortIcons by type also places bin at bottom-left', () => {
			desktopStore.sortIcons('type');
			const bin = desktopStore.icons.find((i) => i.id === 'sys-recycle-bin');
			expect(bin?.position).toEqual({ col: 0, row: getMaxRow() });
		});

		it('first load (no persistence) produces valid layout', () => {
			// After resetDesktop (simulates first load), all 18 icons present (11 PF + 1 HW + 1 TF + 1 bin + 4 shortcuts)
			expect(desktopStore.icons).toHaveLength(18);
			const positions = desktopStore.icons.map((i) => `${i.position.col},${i.position.row}`);
			// All unique
			expect(new Set(positions).size).toBe(18);
			// All in bounds
			for (const icon of desktopStore.icons) {
				expect(icon.position.col).toBeLessThanOrEqual(getMaxCol());
				expect(icon.position.row).toBeLessThanOrEqual(getMaxRow());
			}
		});
	});

	describe('icon actions', () => {
		beforeEach(() => {
			// Close all windows before each test
			for (const w of [...windowManager.windows]) {
				windowManager.closeWindow(w.id);
			}
			windowManager.startMenuOpen = false;
		});

		it('open sys-projects opens a projects window', () => {
			desktopStore.executeIconAction('sys-projects', 'open');
			expect(windowManager.getWindow('projects')).toBeDefined();
			expect(windowManager.getWindow('projects')?.title).toBe('Projects');
		});

		it('open sys-history opens a history window', () => {
			desktopStore.executeIconAction('sys-history', 'open');
			expect(windowManager.getWindow('history')).toBeDefined();
			expect(windowManager.getWindow('history')?.title).toBe('History');
		});

		it('open sys-projects does NOT open start menu', () => {
			desktopStore.executeIconAction('sys-projects', 'open');
			expect(windowManager.startMenuOpen).toBe(false);
		});

		it('open sys-history does NOT open start menu', () => {
			desktopStore.executeIconAction('sys-history', 'open');
			expect(windowManager.startMenuOpen).toBe(false);
		});

		it('new-project opens projects window', () => {
			desktopStore.openContextMenu(100, 200, 'sys-projects');
			desktopStore.executeContextAction('new-project');
			expect(windowManager.getWindow('projects')).toBeDefined();
			expect(windowManager.startMenuOpen).toBe(false);
		});
	});

	describe('getDbNodeInfo', () => {
		it('returns project type for db-folder- prefixed IDs', () => {
			const result = desktopStore.getDbNodeInfo('db-folder-abc-123');
			expect(result).toEqual({ type: 'project', id: 'abc-123' });
		});

		it('returns prompt type for db-prompt- prefixed IDs', () => {
			const result = desktopStore.getDbNodeInfo('db-prompt-xyz-456');
			expect(result).toEqual({ type: 'prompt', id: 'xyz-456' });
		});

		it('returns null for system icons', () => {
			expect(desktopStore.getDbNodeInfo('sys-forge-ide')).toBeNull();
		});

		it('returns null for shortcut icons', () => {
			expect(desktopStore.getDbNodeInfo('shortcut-code-review')).toBeNull();
		});
	});

	describe('moveToDialog', () => {
		it('starts closed with null iconId', () => {
			expect(desktopStore.moveToDialog.open).toBe(false);
			expect(desktopStore.moveToDialog.iconId).toBeNull();
		});

		it('closeMoveToDialog resets state', () => {
			desktopStore.moveToDialog = { open: true, iconId: 'db-folder-test' };
			desktopStore.closeMoveToDialog();
			expect(desktopStore.moveToDialog.open).toBe(false);
			expect(desktopStore.moveToDialog.iconId).toBeNull();
		});

		it('move-to context action opens dialog for DB folder icons', () => {
			// Add a DB folder icon first
			desktopStore.syncDbFolders([{ id: 'folder-1', name: 'Test Folder', type: 'folder' } as any]);
			const iconId = 'db-folder-folder-1';
			desktopStore.openContextMenu(100, 200, iconId);
			desktopStore.executeContextAction('move-to');
			expect(desktopStore.moveToDialog.open).toBe(true);
			expect(desktopStore.moveToDialog.iconId).toBe(iconId);
		});

		it('move-to context action opens dialog for DB prompt icons', () => {
			desktopStore.syncDbPrompts([{ id: 'prompt-1', name: 'Test Prompt', type: 'prompt' } as any]);
			const iconId = 'db-prompt-prompt-1';
			desktopStore.openContextMenu(100, 200, iconId);
			desktopStore.executeContextAction('move-to');
			expect(desktopStore.moveToDialog.open).toBe(true);
			expect(desktopStore.moveToDialog.iconId).toBe(iconId);
		});
	});

	describe('DB icon context actions', () => {
		it('DB folder icons have move-to action', () => {
			desktopStore.syncDbFolders([{ id: 'f1', name: 'Folder', type: 'folder' } as any]);
			const icon = desktopStore.icons.find((i) => i.id === 'db-folder-f1');
			const actionIds = icon?.contextActions.map((a) => a.id);
			expect(actionIds).toContain('move-to');
			expect(actionIds).toContain('open');
			expect(actionIds).toContain('rename');
			expect(actionIds).toContain('delete');
		});

		it('DB prompt icons have move-to action', () => {
			desktopStore.syncDbPrompts([{ id: 'p1', name: 'Prompt', type: 'prompt' } as any]);
			const icon = desktopStore.icons.find((i) => i.id === 'db-prompt-p1');
			const actionIds = icon?.contextActions.map((a) => a.id);
			expect(actionIds).toContain('move-to');
			expect(actionIds).toContain('open');
			expect(actionIds).toContain('rename');
			expect(actionIds).toContain('delete');
		});
	});
});
