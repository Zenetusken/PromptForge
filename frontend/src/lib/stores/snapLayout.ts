/**
 * Snap Layout System — zone detection, layout catalog, geometry resolution.
 *
 * Provides Windows 11 / Ubuntu-style snap zones with 7 preset layouts.
 * Corner zones take priority over edge zones during detection.
 */

import type { WindowGeometry, WindowEntry } from './windowManager.svelte';

// ── Zone & Slot Types ──

export type SnapZoneId =
	| 'left'
	| 'right'
	| 'top'
	| 'top-left'
	| 'top-right'
	| 'bottom-left'
	| 'bottom-right';

export type SnapSlotId =
	| 'full'
	| 'left'
	| 'right'
	| 'top'
	| 'bottom'
	| 'top-left'
	| 'top-right'
	| 'bottom-left'
	| 'bottom-right';

export interface SnapZone {
	id: SnapZoneId;
	geometry: WindowGeometry;
}

// ── Layout Types ──

export interface LayoutSlot {
	id: SnapSlotId;
	/** Fractional position/size (0–1) */
	x: number;
	y: number;
	width: number;
	height: number;
}

export interface SnapLayout {
	id: string;
	label: string;
	slots: LayoutSlot[];
}

// ── Snap Group Types ──

export interface SnapGroupSlot {
	slotId: SnapSlotId;
	windowId: string;
	geometry: WindowGeometry;
}

export interface SnapGroup {
	id: string;
	layoutId: string;
	slots: SnapGroupSlot[];
	locked: boolean;
}

// ── Constants ──

/** Height of the bottom taskbar in pixels. Single source of truth. */
export const TASKBAR_HEIGHT = 40;

// ── Viewport Helper ──

/**
 * Get the usable viewport size (excluding taskbar).
 * Centralizes the repeated `window.innerWidth` / `window.innerHeight - TASKBAR_HEIGHT` pattern.
 */
export function getViewportSize(): { vw: number; vh: number } {
	const vw = typeof window !== 'undefined' ? window.innerWidth : 1280;
	const vh = typeof window !== 'undefined' ? window.innerHeight - TASKBAR_HEIGHT : 680;
	return { vw, vh };
}

// ── Edge Threshold ──

const EDGE_THRESHOLD = 20;
const TOP_MAXIMIZE_THRESHOLD = 8;

// ── Zone Detection ──

/**
 * Detect which snap zone the cursor is in based on screen coordinates.
 * Corners take priority over edges. Returns null if not in any zone.
 *
 * @param clientX - Mouse X coordinate
 * @param clientY - Mouse Y coordinate
 * @param viewportWidth - Optional viewport width override (defaults to window.innerWidth)
 * @param viewportHeight - Optional viewport height override (defaults to window.innerHeight - 40 for taskbar)
 */
export function computeSnapZone(
	clientX: number,
	clientY: number,
	viewportWidth?: number,
	viewportHeight?: number,
): SnapZone | null {
	const vw = viewportWidth ?? (typeof window !== 'undefined' ? window.innerWidth : 1280);
	const vh = viewportHeight ?? (typeof window !== 'undefined' ? window.innerHeight - TASKBAR_HEIGHT : 680);

	const nearLeft = clientX <= EDGE_THRESHOLD;
	const nearRight = clientX >= vw - EDGE_THRESHOLD;
	const nearTop = clientY <= EDGE_THRESHOLD;
	const nearBottom = clientY >= vh - EDGE_THRESHOLD;

	// Corners first (priority over edges)
	if (nearLeft && nearTop) {
		return { id: 'top-left', geometry: resolveZoneGeometry('top-left', vw, vh) };
	}
	if (nearRight && nearTop) {
		return { id: 'top-right', geometry: resolveZoneGeometry('top-right', vw, vh) };
	}
	if (nearLeft && nearBottom) {
		return { id: 'bottom-left', geometry: resolveZoneGeometry('bottom-left', vw, vh) };
	}
	if (nearRight && nearBottom) {
		return { id: 'bottom-right', geometry: resolveZoneGeometry('bottom-right', vw, vh) };
	}

	// Edges
	if (nearLeft) {
		return { id: 'left', geometry: resolveZoneGeometry('left', vw, vh) };
	}
	if (nearRight) {
		return { id: 'right', geometry: resolveZoneGeometry('right', vw, vh) };
	}

	// Top-center = maximize
	if (clientY <= TOP_MAXIMIZE_THRESHOLD) {
		return { id: 'top', geometry: { x: 0, y: 0, width: vw, height: vh } };
	}

	return null;
}

/**
 * Resolve a zone ID to pixel geometry.
 */
export function resolveZoneGeometry(zone: SnapZoneId, vw: number, vh: number): WindowGeometry {
	const halfW = Math.floor(vw / 2);
	const halfH = Math.floor(vh / 2);

	switch (zone) {
		case 'left':
			return { x: 0, y: 0, width: halfW, height: vh };
		case 'right':
			return { x: halfW, y: 0, width: vw - halfW, height: vh };
		case 'top':
			return { x: 0, y: 0, width: vw, height: vh };
		case 'top-left':
			return { x: 0, y: 0, width: halfW, height: halfH };
		case 'top-right':
			return { x: halfW, y: 0, width: vw - halfW, height: halfH };
		case 'bottom-left':
			return { x: 0, y: halfH, width: halfW, height: vh - halfH };
		case 'bottom-right':
			return { x: halfW, y: halfH, width: vw - halfW, height: vh - halfH };
	}
}

// ── Zone → Layout Inference ──

/** Map a snap zone to the most likely layout and slot. */
export function inferLayoutFromZone(zone: SnapZoneId): { layoutId: string; slotId: SnapSlotId } {
	switch (zone) {
		case 'left':
			return { layoutId: '2-even', slotId: 'left' };
		case 'right':
			return { layoutId: '2-even', slotId: 'right' };
		case 'top':
			return { layoutId: '1-full', slotId: 'full' };
		case 'top-left':
			return { layoutId: '4-grid', slotId: 'top-left' };
		case 'top-right':
			return { layoutId: '4-grid', slotId: 'top-right' };
		case 'bottom-left':
			return { layoutId: '4-grid', slotId: 'bottom-left' };
		case 'bottom-right':
			return { layoutId: '4-grid', slotId: 'bottom-right' };
	}
}

// ── Layout Catalog (7 Presets) ──

export const SNAP_LAYOUTS: SnapLayout[] = [
	{
		id: '1-full',
		label: 'Full Screen',
		slots: [{ id: 'full', x: 0, y: 0, width: 1, height: 1 }],
	},
	{
		id: '2-even',
		label: 'Left / Right',
		slots: [
			{ id: 'left', x: 0, y: 0, width: 0.5, height: 1 },
			{ id: 'right', x: 0.5, y: 0, width: 0.5, height: 1 },
		],
	},
	{
		id: '2-wide',
		label: '60 / 40',
		slots: [
			{ id: 'left', x: 0, y: 0, width: 0.6, height: 1 },
			{ id: 'right', x: 0.6, y: 0, width: 0.4, height: 1 },
		],
	},
	{
		id: '2-stack',
		label: 'Top / Bottom',
		slots: [
			{ id: 'top', x: 0, y: 0, width: 1, height: 0.5 },
			{ id: 'bottom', x: 0, y: 0.5, width: 1, height: 0.5 },
		],
	},
	{
		id: '3-left-focus',
		label: 'Left + Right Stack',
		slots: [
			{ id: 'left', x: 0, y: 0, width: 0.5, height: 1 },
			{ id: 'top-right', x: 0.5, y: 0, width: 0.5, height: 0.5 },
			{ id: 'bottom-right', x: 0.5, y: 0.5, width: 0.5, height: 0.5 },
		],
	},
	{
		id: '3-right-focus',
		label: 'Left Stack + Right',
		slots: [
			{ id: 'top-left', x: 0, y: 0, width: 0.5, height: 0.5 },
			{ id: 'bottom-left', x: 0, y: 0.5, width: 0.5, height: 0.5 },
			{ id: 'right', x: 0.5, y: 0, width: 0.5, height: 1 },
		],
	},
	{
		id: '4-grid',
		label: 'Quad Grid',
		slots: [
			{ id: 'top-left', x: 0, y: 0, width: 0.5, height: 0.5 },
			{ id: 'top-right', x: 0.5, y: 0, width: 0.5, height: 0.5 },
			{ id: 'bottom-left', x: 0, y: 0.5, width: 0.5, height: 0.5 },
			{ id: 'bottom-right', x: 0.5, y: 0.5, width: 0.5, height: 0.5 },
		],
	},
];

/**
 * Resolve a fractional layout slot to pixel geometry.
 */
export function resolveSlotGeometry(slot: LayoutSlot, vw: number, vh: number): WindowGeometry {
	return {
		x: Math.round(slot.x * vw),
		y: Math.round(slot.y * vh),
		width: Math.round(slot.width * vw),
		height: Math.round(slot.height * vh),
	};
}

/**
 * Get a layout by ID.
 */
export function getLayout(layoutId: string): SnapLayout | undefined {
	return SNAP_LAYOUTS.find((l) => l.id === layoutId);
}

/**
 * Get the remaining (unfilled) slots for a layout given already-filled slot IDs.
 */
export function getEmptySlots(layoutId: string, filledSlotIds: SnapSlotId[]): LayoutSlot[] {
	const layout = getLayout(layoutId);
	if (!layout) return [];
	return layout.slots.filter((s) => !filledSlotIds.includes(s.id));
}

/**
 * Neon palette colors for snap group visual indicators.
 * Cycles through based on group ID hash.
 */
const GROUP_COLORS = [
	'var(--color-neon-cyan)',
	'var(--color-neon-purple)',
	'var(--color-neon-green)',
	'var(--color-neon-yellow)',
	'var(--color-neon-orange)',
	'var(--color-neon-blue)',
	'var(--color-neon-pink)',
	'var(--color-neon-teal)',
	'var(--color-neon-indigo)',
	'var(--color-neon-red)',
];

/**
 * Get a consistent color for a snap group based on its ID.
 */
export function getGroupColor(groupId: string): string {
	let hash = 0;
	for (let i = 0; i < groupId.length; i++) {
		hash = ((hash << 5) - hash + groupId.charCodeAt(i)) | 0;
	}
	return GROUP_COLORS[Math.abs(hash) % GROUP_COLORS.length];
}

// ── Magnetic Edge Snapping ──

/** Proximity threshold (px) for window-to-window magnetic edge snapping. */
export const EDGE_SNAP_THRESHOLD = 12;

export interface EdgeSnapResult {
	x: number;
	y: number;
	snappedEdges: { horizontal: 'left' | 'right' | null; vertical: 'top' | 'bottom' | null };
}

export interface ResizeEdgeSnapResult extends EdgeSnapResult {
	width: number;
	height: number;
}

/**
 * Filter windows to those eligible as snap targets.
 * Excludes the dragged window, minimized/maximized windows, and windows without geometry.
 */
export function getSnapCandidateWindows(allWindows: WindowEntry[], excludeId: string): WindowEntry[] {
	return allWindows.filter(
		(w) => w.id !== excludeId && w.state === 'normal' && w.geometry != null,
	);
}

/**
 * Check whether two ranges [a1, a2) and [b1, b2) overlap by at least 1px.
 */
function rangesOverlap(a1: number, a2: number, b1: number, b2: number): boolean {
	return a1 < b2 && b1 < a2;
}

/**
 * Compute magnetic edge snap for a dragged window.
 *
 * Checks 4 edge relationships per axis against each candidate:
 * - Adjacent (priority): right↔left, left↔right / bottom↔top, top↔bottom
 * - Alignment: left↔left, right↔right / top↔top, bottom↔bottom
 *
 * Only checks horizontal edges when there's vertical overlap, and vice versa.
 * Picks the closest match per axis independently.
 */
export function computeEdgeSnap(
	draggedGeo: WindowGeometry,
	otherWindows: WindowEntry[],
	threshold: number = EDGE_SNAP_THRESHOLD,
): EdgeSnapResult {
	let bestDx = Infinity;
	let snapX = draggedGeo.x;
	let hEdge: 'left' | 'right' | null = null;

	let bestDy = Infinity;
	let snapY = draggedGeo.y;
	let vEdge: 'top' | 'bottom' | null = null;

	const dRight = draggedGeo.x + draggedGeo.width;
	const dBottom = draggedGeo.y + draggedGeo.height;

	for (const w of otherWindows) {
		const g = w.geometry!;
		const oRight = g.x + g.width;
		const oBottom = g.y + g.height;

		// Horizontal edge checks — require vertical overlap
		const hasVerticalOverlap = rangesOverlap(draggedGeo.y, dBottom, g.y, oBottom);
		if (hasVerticalOverlap) {
			// Adjacent: dragged right edge → other left edge
			const d1 = Math.abs(dRight - g.x);
			if (d1 < threshold && d1 < bestDx) {
				bestDx = d1;
				snapX = g.x - draggedGeo.width;
				hEdge = 'right';
			}
			// Adjacent: dragged left edge → other right edge
			const d2 = Math.abs(draggedGeo.x - oRight);
			if (d2 < threshold && d2 < bestDx) {
				bestDx = d2;
				snapX = oRight;
				hEdge = 'left';
			}
			// Alignment: left↔left
			const d3 = Math.abs(draggedGeo.x - g.x);
			if (d3 < threshold && d3 < bestDx) {
				bestDx = d3;
				snapX = g.x;
				hEdge = 'left';
			}
			// Alignment: right↔right
			const d4 = Math.abs(dRight - oRight);
			if (d4 < threshold && d4 < bestDx) {
				bestDx = d4;
				snapX = oRight - draggedGeo.width;
				hEdge = 'right';
			}
		}

		// Vertical edge checks — require horizontal overlap
		const hasHorizontalOverlap = rangesOverlap(draggedGeo.x, dRight, g.x, oRight);
		if (hasHorizontalOverlap) {
			// Adjacent: dragged bottom edge → other top edge
			const d5 = Math.abs(dBottom - g.y);
			if (d5 < threshold && d5 < bestDy) {
				bestDy = d5;
				snapY = g.y - draggedGeo.height;
				vEdge = 'bottom';
			}
			// Adjacent: dragged top edge → other bottom edge
			const d6 = Math.abs(draggedGeo.y - oBottom);
			if (d6 < threshold && d6 < bestDy) {
				bestDy = d6;
				snapY = oBottom;
				vEdge = 'top';
			}
			// Alignment: top↔top
			const d7 = Math.abs(draggedGeo.y - g.y);
			if (d7 < threshold && d7 < bestDy) {
				bestDy = d7;
				snapY = g.y;
				vEdge = 'top';
			}
			// Alignment: bottom↔bottom
			const d8 = Math.abs(dBottom - oBottom);
			if (d8 < threshold && d8 < bestDy) {
				bestDy = d8;
				snapY = oBottom - draggedGeo.height;
				vEdge = 'bottom';
			}
		}
	}

	return { x: snapX, y: snapY, snappedEdges: { horizontal: hEdge, vertical: vEdge } };
}

/**
 * Compute magnetic edge snap for a resize operation.
 *
 * Only snaps edges that are actively being resized (e.g., 'e' direction only checks right edge).
 * Uses explicit best-distance tracking per axis so the closest candidate always wins.
 * Distance comparisons use original (pre-snap) edge positions; overlap checks use current
 * geometry so cross-axis snaps (diagonal resize) account for prior axis adjustments.
 */
export function computeResizeEdgeSnap(
	geo: WindowGeometry,
	resizeDir: string,
	otherWindows: WindowEntry[],
	threshold: number = EDGE_SNAP_THRESHOLD,
): ResizeEdgeSnapResult {
	let { x, y, width, height } = geo;
	let hEdge: 'left' | 'right' | null = null;
	let vEdge: 'top' | 'bottom' | null = null;
	let bestDx = Infinity;
	let bestDy = Infinity;

	// Original edge positions — fixed reference for all distance comparisons.
	// The non-resized edge on each axis is the anchor (e.g., left edge is fixed during east resize).
	const origRight = geo.x + geo.width;
	const origBottom = geo.y + geo.height;

	for (const w of otherWindows) {
		const g = w.geometry!;
		const oRight = g.x + g.width;
		const oBottom = g.y + g.height;

		// East edge (right side being resized) — left edge is anchor
		if (resizeDir.includes('e')) {
			if (rangesOverlap(y, y + height, g.y, oBottom)) {
				const d1 = Math.abs(origRight - g.x);
				if (d1 < threshold && d1 < bestDx) {
					bestDx = d1;
					width = g.x - x;
					hEdge = 'right';
				}
				const d2 = Math.abs(origRight - oRight);
				if (d2 < threshold && d2 < bestDx) {
					bestDx = d2;
					width = oRight - x;
					hEdge = 'right';
				}
			}
		}

		// West edge (left side being resized) — right edge is anchor
		if (resizeDir.includes('w')) {
			if (rangesOverlap(y, y + height, g.y, oBottom)) {
				const d1 = Math.abs(geo.x - oRight);
				if (d1 < threshold && d1 < bestDx) {
					bestDx = d1;
					width = origRight - oRight;
					x = oRight;
					hEdge = 'left';
				}
				const d2 = Math.abs(geo.x - g.x);
				if (d2 < threshold && d2 < bestDx) {
					bestDx = d2;
					width = origRight - g.x;
					x = g.x;
					hEdge = 'left';
				}
			}
		}

		// South edge (bottom being resized) — top edge is anchor
		if (resizeDir.includes('s')) {
			if (rangesOverlap(x, x + width, g.x, oRight)) {
				const d1 = Math.abs(origBottom - g.y);
				if (d1 < threshold && d1 < bestDy) {
					bestDy = d1;
					height = g.y - y;
					vEdge = 'bottom';
				}
				const d2 = Math.abs(origBottom - oBottom);
				if (d2 < threshold && d2 < bestDy) {
					bestDy = d2;
					height = oBottom - y;
					vEdge = 'bottom';
				}
			}
		}

		// North edge (top being resized) — bottom edge is anchor
		if (resizeDir.includes('n')) {
			if (rangesOverlap(x, x + width, g.x, oRight)) {
				const d1 = Math.abs(geo.y - oBottom);
				if (d1 < threshold && d1 < bestDy) {
					bestDy = d1;
					height = origBottom - oBottom;
					y = oBottom;
					vEdge = 'top';
				}
				const d2 = Math.abs(geo.y - g.y);
				if (d2 < threshold && d2 < bestDy) {
					bestDy = d2;
					height = origBottom - g.y;
					y = g.y;
					vEdge = 'top';
				}
			}
		}
	}

	return { x, y, width, height, snappedEdges: { horizontal: hEdge, vertical: vEdge } };
}
