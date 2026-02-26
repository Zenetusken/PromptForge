import { windowManager } from '$lib/stores/windowManager.svelte';
import { TASKBAR_HEIGHT } from '$lib/stores/snapLayout';
import { TYPE_SORT_ORDER } from '$lib/utils/fileTypes';

// ── Grid Geometry ──
export const CELL_WIDTH = 76; // 72px icon + 4px gap
export const CELL_HEIGHT = 84; // 80px icon + 4px gap
export const GRID_PADDING = 12;
export { TASKBAR_HEIGHT };
export const RECYCLE_BIN_ID = 'sys-recycle-bin';

/**
 * Compute the max row index (0-based) that fits above the taskbar.
 * Icon top = row * CELL_HEIGHT + GRID_PADDING, so only one padding
 * is needed (for the top offset). No bottom padding reservation.
 */
export function getMaxRow(): number {
	if (typeof window === 'undefined') return 6;
	const availableHeight = window.innerHeight - TASKBAR_HEIGHT - GRID_PADDING;
	return Math.max(0, Math.floor(availableHeight / CELL_HEIGHT) - 1);
}

/**
 * Compute the max column index (0-based) that fits within the viewport.
 * Icon left = col * CELL_WIDTH + GRID_PADDING, so only one padding
 * is needed (for the left offset). No right padding reservation.
 */
export function getMaxCol(): number {
	if (typeof window === 'undefined') return 12;
	const availableWidth = window.innerWidth - GRID_PADDING;
	return Math.max(0, Math.floor(availableWidth / CELL_WIDTH) - 1);
}

const STORAGE_KEY = 'pf_desktop';

// ── Types ──

export type IconType = 'system' | 'folder' | 'file';

export interface GridPosition {
	col: number;
	row: number;
}

export interface ContextAction {
	id: string;
	label: string;
	icon?: string;
	separator?: boolean;
	danger?: boolean;
}

export interface DesktopIconDef {
	id: string;
	label: string;
	icon: string;
	color: string;
	type: IconType;
	extension?: string;
	position: GridPosition;
	contextActions: ContextAction[];
}

export interface RecycleBinItem {
	id: string;
	sourceType: 'optimization' | 'project' | 'folder' | 'file';
	sourceId: string;
	name: string;
	trashedAt: number;
	iconDef?: DesktopIconDef;
}

export interface DragState {
	iconId: string;
	startPosition: GridPosition;
	ghostCol: number;
	ghostRow: number;
	offsetX: number;
	offsetY: number;
	hasMoved: boolean;
}

export interface ContextMenuState {
	open: boolean;
	x: number;
	y: number;
	targetIconId: string | null;
	actions: ContextAction[];
}

export interface ConfirmDialogState {
	open: boolean;
	title: string;
	message: string;
	confirmLabel: string;
	onConfirm: () => void;
}

// ── File prompt texts (keyed by shortcut-* IDs for backward compat) ──

const SHORTCUT_PROMPTS: Record<string, string> = {
	'shortcut-code-review':
		'Review this Python function for correctness, performance issues, and adherence to best practices. Suggest specific refactors with code examples and explain the reasoning behind each change.',
	'shortcut-marketing-email':
		'Write a compelling product launch email for a B2B SaaS audience. Include a subject line, preview text, hero section, three benefit-driven paragraphs, social proof, and a clear call-to-action.',
	'shortcut-technical-docs':
		'Create comprehensive API documentation for a REST endpoint including description, authentication requirements, request/response schemas with examples, error codes, and rate limiting details.',
	'shortcut-error-messages':
		'Design user-friendly error messages for a web application covering validation failures, network errors, authentication issues, and permission denials. Each message should explain what went wrong and how to fix it.',
};

// ── Default Icon Definitions ──

const SYSTEM_CONTEXT_ACTIONS: Record<string, ContextAction[]> = {
	'sys-forge-ide': [
		{ id: 'open', label: 'Open', icon: 'terminal' },
		{ id: 'new-tab', label: 'New Tab', icon: 'plus' },
		{ id: 'minimize', label: 'Minimize', icon: 'minimize-2' },
	],
	'sys-projects': [
		{ id: 'open', label: 'Open', icon: 'folder' },
		{ id: 'new-project', label: 'New Project', icon: 'plus' },
		{ id: 'rename', label: 'Rename', icon: 'edit', separator: true },
		{ id: 'delete', label: 'Delete', icon: 'trash-2', danger: true },
	],
	'sys-history': [
		{ id: 'open', label: 'Open', icon: 'clock' },
		{ id: 'clear-history', label: 'Clear History', icon: 'trash-2', separator: true, danger: true },
		{ id: 'rename', label: 'Rename', icon: 'edit', separator: true },
		{ id: 'delete', label: 'Delete', icon: 'trash-2', danger: true },
	],
	'sys-control-panel': [
		{ id: 'open', label: 'Open', icon: 'settings' },
	],
	'sys-task-manager': [
		{ id: 'open', label: 'Open', icon: 'cpu' },
	],
	'sys-batch-processor': [
		{ id: 'open', label: 'Open', icon: 'layers' },
	],
	'sys-strategy-workshop': [
		{ id: 'open', label: 'Open', icon: 'bar-chart' },
	],
	'sys-template-library': [
		{ id: 'open', label: 'Open', icon: 'file-text' },
	],
	'sys-terminal': [
		{ id: 'open', label: 'Open', icon: 'terminal' },
	],
	'sys-network-monitor': [
		{ id: 'open', label: 'Open', icon: 'activity' },
	],
	'sys-workspace-hub': [
		{ id: 'open', label: 'Open', icon: 'git-branch' },
	],
	'sys-recycle-bin': [
		{ id: 'open-bin', label: 'Open', icon: 'trash-2' },
		{ id: 'empty-bin', label: 'Empty Recycle Bin', icon: 'trash-2', separator: true, danger: true },
	],
};

const FILE_CONTEXT_ACTIONS: ContextAction[] = [
	{ id: 'open', label: 'Open', icon: 'terminal' },
	{ id: 'rename', label: 'Rename', icon: 'edit' },
	{ id: 'delete', label: 'Delete', icon: 'trash-2', separator: true, danger: true },
];

const DESKTOP_CONTEXT_ACTIONS: ContextAction[] = [
	{ id: 'new-forge', label: 'New Forge', icon: 'bolt' },
	{ id: 'new-project', label: 'New Project', icon: 'folder' },
	{ id: 'sort-by-name', label: 'Sort by Name', icon: 'layers', separator: true },
	{ id: 'sort-by-type', label: 'Sort by Type', icon: 'sliders' },
	{ id: 'display-settings', label: 'Display Settings...', icon: 'monitor', separator: true },
	{ id: 'refresh-desktop', label: 'Refresh Desktop', icon: 'refresh', separator: true },
];

function createDefaultIcons(): DesktopIconDef[] {
	return [
		{
			id: 'sys-forge-ide',
			label: 'Forge IDE',
			icon: 'terminal',
			color: 'cyan',
			type: 'system',
			position: { col: 0, row: 0 },
			contextActions: SYSTEM_CONTEXT_ACTIONS['sys-forge-ide'],
		},
		{
			id: 'sys-projects',
			label: 'Projects',
			icon: 'folder',
			color: 'yellow',
			type: 'folder',
			position: { col: 0, row: 0 },
			contextActions: SYSTEM_CONTEXT_ACTIONS['sys-projects'],
		},
		{
			id: 'sys-history',
			label: 'History',
			icon: 'folder',
			color: 'blue',
			type: 'folder',
			position: { col: 0, row: 0 },
			contextActions: SYSTEM_CONTEXT_ACTIONS['sys-history'],
		},
		{
			id: 'sys-control-panel',
			label: 'Control Panel',
			icon: 'settings',
			color: 'purple',
			type: 'system',
			position: { col: 0, row: 0 },
			contextActions: SYSTEM_CONTEXT_ACTIONS['sys-control-panel'],
		},
		{
			id: 'sys-task-manager',
			label: 'Task Manager',
			icon: 'cpu',
			color: 'green',
			type: 'system',
			position: { col: 0, row: 0 },
			contextActions: SYSTEM_CONTEXT_ACTIONS['sys-task-manager'],
		},
		{
			id: 'sys-batch-processor',
			label: 'Batch Processor',
			icon: 'layers',
			color: 'orange',
			type: 'system',
			position: { col: 0, row: 0 },
			contextActions: SYSTEM_CONTEXT_ACTIONS['sys-batch-processor'],
		},
		{
			id: 'sys-strategy-workshop',
			label: 'Strategy Workshop',
			icon: 'bar-chart',
			color: 'indigo',
			type: 'system',
			position: { col: 0, row: 0 },
			contextActions: SYSTEM_CONTEXT_ACTIONS['sys-strategy-workshop'],
		},
		{
			id: 'sys-template-library',
			label: 'Template Library',
			icon: 'file-text',
			color: 'teal',
			type: 'system',
			position: { col: 0, row: 0 },
			contextActions: SYSTEM_CONTEXT_ACTIONS['sys-template-library'],
		},
		{
			id: 'sys-terminal',
			label: 'Terminal',
			icon: 'terminal',
			color: 'cyan',
			type: 'system',
			position: { col: 0, row: 0 },
			contextActions: SYSTEM_CONTEXT_ACTIONS['sys-terminal'],
		},
		{
			id: 'sys-network-monitor',
			label: 'Network Monitor',
			icon: 'activity',
			color: 'green',
			type: 'system',
			position: { col: 0, row: 0 },
			contextActions: SYSTEM_CONTEXT_ACTIONS['sys-network-monitor'],
		},
		{
			id: 'sys-workspace-hub',
			label: 'Workspace Hub',
			icon: 'git-branch',
			color: 'green',
			type: 'system',
			position: { col: 0, row: 0 },
			contextActions: SYSTEM_CONTEXT_ACTIONS['sys-workspace-hub'],
		},
		{
			id: RECYCLE_BIN_ID,
			label: 'Recycle Bin',
			icon: 'trash-2',
			color: 'red',
			type: 'system',
			position: { col: 0, row: 0 },
			contextActions: SYSTEM_CONTEXT_ACTIONS[RECYCLE_BIN_ID],
		},
		{
			id: 'shortcut-code-review',
			label: 'Code Review.md',
			icon: 'file-text',
			color: 'cyan',
			type: 'file',
			extension: '.md',
			position: { col: 0, row: 0 },
			contextActions: FILE_CONTEXT_ACTIONS,
		},
		{
			id: 'shortcut-marketing-email',
			label: 'Marketing Email.md',
			icon: 'file-text',
			color: 'purple',
			type: 'file',
			extension: '.md',
			position: { col: 0, row: 0 },
			contextActions: FILE_CONTEXT_ACTIONS,
		},
		{
			id: 'shortcut-technical-docs',
			label: 'Technical Docs.md',
			icon: 'file-text',
			color: 'green',
			type: 'file',
			extension: '.md',
			position: { col: 0, row: 0 },
			contextActions: FILE_CONTEXT_ACTIONS,
		},
		{
			id: 'shortcut-error-messages',
			label: 'Error Messages.md',
			icon: 'file-text',
			color: 'red',
			type: 'file',
			extension: '.md',
			position: { col: 0, row: 0 },
			contextActions: FILE_CONTEXT_ACTIONS,
		},
	];
}

// ── Persistence ──

interface PersistedDesktop {
	iconPositions: Record<string, GridPosition>;
	removedShortcuts: string[];
	recycleBin: RecycleBinItem[];
	customLabels: Record<string, string>;
}

function loadPersisted(): PersistedDesktop | null {
	if (typeof window === 'undefined') return null;
	try {
		// Try localStorage first (new location)
		let raw = localStorage.getItem(STORAGE_KEY);
		if (!raw) {
			// Migrate from sessionStorage (old location)
			raw = sessionStorage.getItem(STORAGE_KEY);
			if (raw) {
				localStorage.setItem(STORAGE_KEY, raw);
				sessionStorage.removeItem(STORAGE_KEY);
			}
		}
		if (!raw) return null;
		return JSON.parse(raw) as PersistedDesktop;
	} catch {
		return null;
	}
}

// ── Store ──

class DesktopStoreState {
	icons: DesktopIconDef[] = $state([]);
	selectedIconId: string | null = $state(null);
	dragState: DragState | null = $state(null);
	recycleBin: RecycleBinItem[] = $state([]);
	contextMenu: ContextMenuState = $state({
		open: false,
		x: 0,
		y: 0,
		targetIconId: null,
		actions: [],
	});
	confirmDialog: ConfirmDialogState = $state({
		open: false,
		title: '',
		message: '',
		confirmLabel: 'Confirm',
		onConfirm: () => {},
	});
	requestRename: string | null = $state(null);

	// ── Derived ──

	selectedIcon: DesktopIconDef | undefined = $derived(
		this.icons.find((i) => i.id === this.selectedIconId)
	);

	isDragging: boolean = $derived(this.dragState !== null && this.dragState.hasMoved);

	binItemCount: number = $derived(this.recycleBin.length);

	binIsEmpty: boolean = $derived(this.recycleBin.length === 0);

	gridFull: boolean = $derived.by(() => {
		const totalCells = (getMaxRow() + 1) * (getMaxCol() + 1);
		return this.icons.length >= totalCells;
	});

	occupiedCells: Map<string, string> = $derived.by(() => {
		const map = new Map<string, string>();
		for (const icon of this.icons) {
			map.set(`${icon.position.col},${icon.position.row}`, icon.id);
		}
		return map;
	});

	constructor() {
		this._initFromPersistence();
	}

	private _initFromPersistence() {
		const defaults = createDefaultIcons();
		const saved = loadPersisted();

		if (saved) {
			// Filter out removed non-system icons (persisted key is 'removedShortcuts' for compat)
			const activeIcons = defaults.filter(
				(icon) => icon.type === 'system' || !saved.removedShortcuts.includes(icon.id)
			);
			// Patch positions from persistence, clamping to current screen bounds
			const maxRow = getMaxRow();
			const maxCol = getMaxCol();
			for (const icon of activeIcons) {
				if (saved.iconPositions[icon.id]) {
					const pos = saved.iconPositions[icon.id];
					icon.position = {
						col: Math.min(pos.col, maxCol),
						row: Math.min(pos.row, maxRow),
					};
				}
			}
			// Resolve any overlaps created by clamping
			this._dedupPositions(activeIcons);
			// Patch custom labels from persistence
			if (saved.customLabels) {
				for (const icon of activeIcons) {
					if (saved.customLabels[icon.id]) {
						icon.label = saved.customLabels[icon.id];
					}
				}
			}
			this.icons = activeIcons;
			this.recycleBin = saved.recycleBin;
		} else {
			this.icons = defaults;
			this._autoLayout(this.icons);
		}
	}

	// ── Selection ──

	selectIcon(id: string) {
		this.selectedIconId = id;
	}

	deselectAll() {
		this.selectedIconId = null;
	}

	// ── Drag ──

	startDrag(iconId: string, offsetX: number, offsetY: number) {
		// Discard stale drag without committing ghost position
		if (this.dragState) this.dragState = null;
		const icon = this.icons.find((i) => i.id === iconId);
		if (!icon) return;
		this.dragState = {
			iconId,
			startPosition: { ...icon.position },
			ghostCol: icon.position.col,
			ghostRow: icon.position.row,
			offsetX,
			offsetY,
			hasMoved: false,
		};
	}

	updateDragGhost(clientX: number, clientY: number, surfaceRect: DOMRect) {
		if (!this.dragState) return;

		const relX = clientX - surfaceRect.left - this.dragState.offsetX + GRID_PADDING;
		const relY = clientY - surfaceRect.top - this.dragState.offsetY + GRID_PADDING;

		const col = Math.min(getMaxCol(), Math.max(0, Math.round(relX / CELL_WIDTH)));
		const row = Math.min(getMaxRow(), Math.max(0, Math.round(relY / CELL_HEIGHT)));

		// 5px movement threshold before entering drag mode
		if (!this.dragState.hasMoved) {
			const startPx = {
				x: this.dragState.startPosition.col * CELL_WIDTH + GRID_PADDING,
				y: this.dragState.startPosition.row * CELL_HEIGHT + GRID_PADDING,
			};
			const dx = (clientX - surfaceRect.left) - startPx.x - this.dragState.offsetX;
			const dy = (clientY - surfaceRect.top) - startPx.y - this.dragState.offsetY;
			if (Math.sqrt(dx * dx + dy * dy) < 5) return;
			this.dragState.hasMoved = true;
		}

		this.dragState.ghostCol = col;
		this.dragState.ghostRow = row;
	}

	endDrag() {
		if (!this.dragState) return;

		if (this.dragState.hasMoved) {
			const { iconId, ghostCol, ghostRow } = this.dragState;
			const cellKey = `${ghostCol},${ghostRow}`;
			const occupant = this.occupiedCells.get(cellKey);

			if (!occupant || occupant === iconId) {
				// Move to new position
				const icon = this.icons.find((i) => i.id === iconId);
				if (icon) {
					icon.position = { col: ghostCol, row: ghostRow };
				}
			}
			// If occupied by another icon, snap back (position unchanged)
		}

		this.dragState = null;
		this._persist();
	}

	// ── Context Menu ──

	openContextMenu(x: number, y: number, iconId: string | null) {
		if (iconId) {
			const icon = this.icons.find((i) => i.id === iconId);
			if (icon) {
				// Selection is handled by the component (DesktopIcon calls onselect before oncontextmenu)
				this.contextMenu = {
					open: true,
					x,
					y,
					targetIconId: iconId,
					actions: icon.contextActions,
				};
			}
		} else {
			this.deselectAll();
			this.contextMenu = {
				open: true,
				x,
				y,
				targetIconId: null,
				actions: DESKTOP_CONTEXT_ACTIONS,
			};
		}
	}

	closeContextMenu() {
		this.contextMenu = {
			...this.contextMenu,
			open: false,
		};
	}

	/** Execute an action on a specific icon (for double-click, programmatic dispatch). */
	executeIconAction(iconId: string, actionId: string) {
		this._dispatchAction(iconId, actionId);
	}

	executeContextAction(actionId: string) {
		const { targetIconId } = this.contextMenu;
		this.closeContextMenu();
		this._dispatchAction(targetIconId, actionId);
	}

	private _dispatchAction(targetIconId: string | null, actionId: string) {
		switch (actionId) {
			case 'open': {
				if (targetIconId === 'sys-forge-ide') {
					this._openForgeIDE();
				} else if (targetIconId === 'sys-projects') {
					windowManager.openProjectsWindow();
				} else if (targetIconId === 'sys-history') {
					windowManager.openHistoryWindow();
				} else if (targetIconId === 'sys-control-panel') {
					windowManager.openWindow({ id: 'control-panel', title: 'Control Panel', icon: 'settings' });
				} else if (targetIconId === 'sys-task-manager') {
					windowManager.openWindow({ id: 'task-manager', title: 'Task Manager', icon: 'cpu' });
				} else if (targetIconId === 'sys-batch-processor') {
					windowManager.openWindow({ id: 'batch-processor', title: 'Batch Processor', icon: 'layers' });
				} else if (targetIconId === 'sys-strategy-workshop') {
					windowManager.openWindow({ id: 'strategy-workshop', title: 'Strategy Workshop', icon: 'bar-chart' });
				} else if (targetIconId === 'sys-template-library') {
					windowManager.openWindow({ id: 'template-library', title: 'Template Library', icon: 'file-text' });
				} else if (targetIconId === 'sys-terminal') {
					windowManager.openWindow({ id: 'terminal', title: 'Terminal', icon: 'terminal' });
				} else if (targetIconId === 'sys-network-monitor') {
					windowManager.openNetworkMonitor();
				} else if (targetIconId === 'sys-workspace-hub') {
					windowManager.openWorkspaceHub();
				} else if (targetIconId?.startsWith('shortcut-')) {
					this._openShortcut(targetIconId);
				}
				break;
			}
			case 'open-bin': {
				this._openRecycleBin();
				break;
			}
			case 'new-tab': {
				this._newForgeTab();
				break;
			}
			case 'minimize': {
				windowManager.minimizeWindow('ide');
				break;
			}
			case 'new-forge': {
				this._newForge();
				break;
			}
			case 'new-project': {
				windowManager.openProjectsWindow();
				break;
			}
			case 'clear-history': {
				this.confirmDialog = {
					open: true,
					title: 'Clear All History',
					message: 'This will permanently delete all optimization history. This cannot be undone.',
					confirmLabel: 'Clear All',
					onConfirm: async () => {
						const { clearAllHistory } = await import('$lib/api/client');
						const { historyState } = await import('$lib/stores/history.svelte');
						await clearAllHistory();
						historyState.loadHistory();
						this.confirmDialog.open = false;
					},
				};
				break;
			}
			case 'rename': {
				if (targetIconId) this.requestRename = targetIconId;
				break;
			}
			case 'delete': {
				if (targetIconId) {
					this.trashIcon(targetIconId);
				}
				break;
			}
			case 'empty-bin': {
				this.confirmDialog = {
					open: true,
					title: 'Empty Recycle Bin',
					message: `Permanently delete ${this.recycleBin.length} item${this.recycleBin.length === 1 ? '' : 's'}? This cannot be undone.`,
					confirmLabel: 'Empty Bin',
					onConfirm: () => {
						this.emptyRecycleBin();
						this.confirmDialog.open = false;
					},
				};
				break;
			}
			case 'sort-by-name': {
				this.sortIcons('name');
				break;
			}
			case 'sort-by-type': {
				this.sortIcons('type');
				break;
			}
			case 'display-settings': {
				windowManager.openDisplaySettings();
				break;
			}
			case 'refresh-desktop': {
				this.resetDesktop();
				break;
			}
		}
	}

	// ── Rename ──

	renameIcon(id: string, newLabel: string) {
		const trimmed = newLabel.trim();
		if (!trimmed) return;
		const icon = this.icons.find((i) => i.id === id);
		if (!icon || icon.type === 'system') return;
		icon.label = trimmed;
		for (const item of this.recycleBin) {
			if (item.sourceId === id && item.iconDef) {
				item.iconDef.label = trimmed;
			}
		}
		this._persist();
	}

	// ── Recycle Bin ──

	trashIcon(id: string) {
		if (this.dragState?.iconId === id) this.dragState = null;
		const icon = this.icons.find((i) => i.id === id);
		if (!icon || icon.type === 'system') return;

		const binItem: RecycleBinItem = {
			id: crypto.randomUUID(),
			sourceType: icon.type as 'folder' | 'file',
			sourceId: id,
			name: icon.label,
			trashedAt: Date.now(),
			iconDef: { ...icon, position: { ...icon.position }, contextActions: [...icon.contextActions] },
		};

		this.recycleBin.push(binItem);
		this.icons = this.icons.filter((i) => i.id !== id);
		if (this.selectedIconId === id) {
			this.selectedIconId = null;
		}
		this._persist();
	}

	/** Restore a bin item to the desktop. Returns true if placed off-screen (grid full). */
	restoreItem(binItemId: string): boolean {
		const item = this.recycleBin.find((i) => i.id === binItemId);
		if (!item) return false;

		let placedOffScreen = false;
		if ((item.sourceType === 'folder' || item.sourceType === 'file') && item.iconDef) {
			const position = this._findEmptyCell();
			placedOffScreen = position.col > getMaxCol() || position.row > getMaxRow();
			const restored: DesktopIconDef = {
				...item.iconDef,
				position,
				contextActions: item.iconDef.contextActions,
			};
			this.icons.push(restored);
		}

		this.recycleBin = this.recycleBin.filter((i) => i.id !== binItemId);
		this._persist();
		return placedOffScreen;
	}

	permanentlyDeleteItem(binItemId: string) {
		this.recycleBin = this.recycleBin.filter((i) => i.id !== binItemId);
		this._persist();
	}

	emptyRecycleBin() {
		this.recycleBin = [];
		this._persist();
	}

	// ── Sort ──

	sortIcons(by: 'name' | 'type') {
		if (this.dragState) this.dragState = null;
		const sorted = [...this.icons];
		if (by === 'name') {
			sorted.sort((a, b) => a.label.localeCompare(b.label));
		} else {
			sorted.sort((a, b) => {
				const typeA = TYPE_SORT_ORDER[a.type] ?? 99;
				const typeB = TYPE_SORT_ORDER[b.type] ?? 99;
				if (typeA !== typeB) return typeA - typeB;
				return a.label.localeCompare(b.label);
			});
		}

		this.icons = sorted;
		this._autoLayout(this.icons);
		this._persist();
	}

	// ── Reclamp (called on window resize) ──

	reclampPositions() {
		const maxRow = getMaxRow();
		const maxCol = getMaxCol();
		let changed = false;
		for (const icon of this.icons) {
			const cc = Math.min(icon.position.col, maxCol);
			const cr = Math.min(icon.position.row, maxRow);
			if (cc !== icon.position.col || cr !== icon.position.row) {
				icon.position = { col: cc, row: cr };
				changed = true;
			}
		}
		if (changed) {
			this._dedupPositions(this.icons);
			this._persist();
		}
	}

	// ── Reset ──

	resetDesktop() {
		this.icons = createDefaultIcons();
		this._autoLayout(this.icons);
		this.selectedIconId = null;
		this.dragState = null;
		this.requestRename = null;
		this._persist();
	}

	// ── Private helpers ──

	private _openForgeIDE() {
		// Lazy imports to avoid circular dependencies
		import('$lib/stores/forgeMachine.svelte').then(({ forgeMachine }) => {
			import('$lib/stores/forgeSession.svelte').then(({ forgeSession }) => {
				forgeMachine.restore();
				forgeSession.activate();
				windowManager.openIDE();
			});
		});
	}

	private _openShortcut(shortcutId: string) {
		const promptText = SHORTCUT_PROMPTS[shortcutId];
		if (!promptText) return;

		import('$lib/stores/forgeMachine.svelte').then(({ forgeMachine }) => {
			import('$lib/stores/forgeSession.svelte').then(({ forgeSession }) => {
				forgeMachine.restore();
				forgeSession.updateDraft({ text: promptText });
				forgeSession.activate();
				windowManager.openIDE();
				forgeSession.focusTextarea();
			});
		});
	}

	private _openRecycleBin() {
		windowManager.openWindow({
			id: 'recycle-bin',
			title: `Recycle Bin (${this.binItemCount})`,
			icon: 'trash-2',
		});
	}

	private _newForge() {
		Promise.all([
			import('$lib/stores/forgeMachine.svelte'),
			import('$lib/stores/forgeSession.svelte'),
			import('$lib/stores/tabCoherence'),
		]).then(([{ forgeMachine }, { forgeSession, createEmptyDraft }, { saveActiveTabState, restoreTabState }]) => {
			if (forgeMachine.mode === 'forging') return;
			saveActiveTabState();
			forgeMachine.restore();
			const tab = {
				id: crypto.randomUUID(),
				name: 'Untitled',
				draft: createEmptyDraft(),
				resultId: null as string | null,
				mode: 'compose' as const,
			};
			forgeSession.tabs.push(tab);
			forgeSession.activeTabId = tab.id;
			restoreTabState(tab);
			forgeSession.activate();
			windowManager.openIDE();
			forgeSession.focusTextarea();
		});
	}

	private _newForgeTab() {
		Promise.all([
			import('$lib/stores/forgeSession.svelte'),
			import('$lib/stores/tabCoherence'),
		]).then(([{ forgeSession, createEmptyDraft }, { saveActiveTabState, restoreTabState }]) => {
			saveActiveTabState();
			const tab = {
				id: crypto.randomUUID(),
				name: 'Untitled',
				draft: createEmptyDraft(),
				resultId: null as string | null,
				mode: 'compose' as const,
			};
			forgeSession.tabs.push(tab);
			forgeSession.activeTabId = tab.id;
			restoreTabState(tab);
			forgeSession.activate();
			windowManager.openIDE();
		});
	}

	private _dedupPositions(icons: DesktopIconDef[]) {
		const maxRow = getMaxRow();
		const maxCol = getMaxCol();
		const seen = new Map<string, true>();
		for (const icon of icons) {
			const key = `${icon.position.col},${icon.position.row}`;
			if (seen.has(key)) {
				let placed = false;
				for (let c = 0; c <= maxCol && !placed; c++) {
					for (let r = 0; r <= maxRow && !placed; r++) {
						const k = `${c},${r}`;
						if (!seen.has(k)) {
							icon.position = { col: c, row: r };
							placed = true;
						}
					}
				}
				if (!placed) icon.position = { col: maxCol + 1, row: 0 };
			}
			seen.set(`${icon.position.col},${icon.position.row}`, true);
		}
	}

	private _autoLayout(icons: DesktopIconDef[]): void {
		const maxRow = getMaxRow();
		const maxCol = getMaxCol();

		// Recycle Bin always goes to bottom-left (Windows convention)
		const binIcon = icons.find((i) => i.id === RECYCLE_BIN_ID);
		const others = icons.filter((i) => i.id !== RECYCLE_BIN_ID);

		if (binIcon) {
			binIcon.position = { col: 0, row: maxRow };
		}

		// Track occupied cells — reserve bin cell if bin exists
		const occupied = new Set<string>();
		if (binIcon) {
			occupied.add(`0,${maxRow}`);
		}

		// Column-first fill for all other icons, skipping reserved cell
		let col = 0;
		let row = 0;
		for (const icon of others) {
			// Advance past occupied cells (the reserved bin cell)
			while (occupied.has(`${col},${row}`)) {
				row++;
				if (row > maxRow) {
					row = 0;
					col++;
				}
				if (col > maxCol) break;
			}

			if (col > maxCol) {
				icon.position = { col: maxCol + 1, row: 0 };
			} else {
				icon.position = { col, row };
				occupied.add(`${col},${row}`);
				row++;
				if (row > maxRow) {
					row = 0;
					col++;
				}
			}
		}
	}

	private _findEmptyCell(): GridPosition {
		const maxRow = getMaxRow();
		const maxCol = getMaxCol();
		for (let col = 0; col <= maxCol; col++) {
			for (let row = 0; row <= maxRow; row++) {
				if (!this.occupiedCells.has(`${col},${row}`)) {
					return { col, row };
				}
			}
		}
		// Grid full — expand by one column rather than silently overlapping
		return { col: maxCol + 1, row: 0 };
	}

	private _persist() {
		if (typeof window === 'undefined') return;
		try {
			const positions: Record<string, GridPosition> = {};
			for (const icon of this.icons) {
				positions[icon.id] = { ...icon.position };
			}

			const defaults = createDefaultIcons();
			const defaultRemovableIds = defaults
				.filter((i) => i.type !== 'system')
				.map((i) => i.id);
			const currentRemovableIds = this.icons
				.filter((i) => i.type !== 'system')
				.map((i) => i.id);
			// Persisted key is 'removedShortcuts' for backward compat with existing sessions
			const removedShortcuts = defaultRemovableIds.filter(
				(id) => !currentRemovableIds.includes(id)
			);

			const defaultLabels = Object.fromEntries(defaults.map((i) => [i.id, i.label]));
			const customLabels: Record<string, string> = {};
			for (const icon of this.icons) {
				if (icon.label !== defaultLabels[icon.id]) {
					customLabels[icon.id] = icon.label;
				}
			}

			const state: PersistedDesktop = {
				iconPositions: positions,
				removedShortcuts,
				recycleBin: this.recycleBin.map((item) => ({ ...item })),
				customLabels,
			};
			localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
		} catch {
			// ignore
		}
	}
}

export const desktopStore = new DesktopStoreState();
