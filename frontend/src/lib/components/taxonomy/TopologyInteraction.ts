/**
 * Raycasting and interaction for the taxonomy 3D topology.
 *
 * Converts mouse events into scene queries (click → focus node,
 * Escape → ascend to parent, search → highlight + animate).
 */
import * as THREE from 'three';
import type { TopologyRenderer } from './TopologyRenderer';
import type { SceneNode } from './TopologyData';

export interface InteractionCallbacks {
  onNodeClick: (nodeId: string) => void;
  onNodeHover: (nodeId: string | null) => void;
  onAscend: () => void;
}

export class TopologyInteraction {
  private _raycaster = new THREE.Raycaster();
  private _mouse = new THREE.Vector2();
  private _renderer: TopologyRenderer;
  private _callbacks: InteractionCallbacks;
  private _nodeMap: Map<string, THREE.Object3D> = new Map();
  private _sceneNodes: Map<string, SceneNode> = new Map();
  private _nodeObjects: THREE.Object3D[] = [];  // cached for raycast
  private _hoveredId: string | null = null;
  private _canvas: HTMLCanvasElement;

  // Bound handlers for cleanup
  private _onPointerMove: (e: PointerEvent) => void;
  private _onClick: (e: PointerEvent) => void;
  private _onKeyDown: (e: KeyboardEvent) => void;

  constructor(
    renderer: TopologyRenderer,
    canvas: HTMLCanvasElement,
    callbacks: InteractionCallbacks,
  ) {
    this._renderer = renderer;
    this._canvas = canvas;
    this._callbacks = callbacks;

    this._onPointerMove = this._handlePointerMove.bind(this);
    this._onClick = this._handleClick.bind(this);
    this._onKeyDown = this._handleKeyDown.bind(this);

    canvas.addEventListener('pointermove', this._onPointerMove);
    canvas.addEventListener('pointerdown', this._onClick);
    window.addEventListener('keydown', this._onKeyDown);
  }

  /** Register a Three.js object as a clickable node. */
  registerNode(nodeId: string, object: THREE.Object3D, sceneNode: SceneNode): void {
    this._nodeMap.set(nodeId, object);
    this._sceneNodes.set(nodeId, sceneNode);
    this._nodeObjects = Array.from(this._nodeMap.values());
    object.userData.nodeId = nodeId;
  }

  /** Clear all registered nodes. */
  clear(): void {
    this._nodeMap.clear();
    this._sceneNodes.clear();
    this._nodeObjects = [];
  }

  /** Highlight a node by ID (for search). */
  highlightNode(nodeId: string): void {
    const obj = this._nodeMap.get(nodeId);
    const sceneNode = this._sceneNodes.get(nodeId);
    if (obj && sceneNode) {
      const pos = new THREE.Vector3(...sceneNode.position);
      this._renderer.focusOn(pos, 15);
    }
  }

  dispose(): void {
    this._canvas.removeEventListener('pointermove', this._onPointerMove);
    this._canvas.removeEventListener('pointerdown', this._onClick);
    window.removeEventListener('keydown', this._onKeyDown);
  }

  private _updateMouse(event: PointerEvent): void {
    const rect = this._canvas.getBoundingClientRect();
    this._mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this._mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  }

  private _raycast(): THREE.Intersection[] {
    this._raycaster.setFromCamera(this._mouse, this._renderer.camera);
    return this._raycaster.intersectObjects(this._nodeObjects, false);
  }

  private _handlePointerMove(event: PointerEvent): void {
    this._updateMouse(event);
    const hits = this._raycast();
    const hitId = hits[0]?.object.userData.nodeId ?? null;

    if (hitId !== this._hoveredId) {
      this._hoveredId = hitId;
      this._callbacks.onNodeHover(hitId);
      this._canvas.style.cursor = hitId ? 'pointer' : 'default';
    }
  }

  private _handleClick(event: PointerEvent): void {
    // Only handle left-click
    if (event.button !== 0) return;

    this._updateMouse(event);
    const hits = this._raycast();
    const hitId = hits[0]?.object.userData.nodeId;
    if (hitId) {
      this._callbacks.onNodeClick(hitId);
    }
  }

  private _handleKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      this._callbacks.onAscend();
    }
  }
}
