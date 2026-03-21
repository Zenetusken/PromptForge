import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock Three.js classes — must be constructable with `new`
vi.mock('three', () => {
  class Vector3 {
    x: number; y: number; z: number;
    constructor(x = 0, y = 0, z = 0) { this.x = x; this.y = y; this.z = z; }
    clone() { return new Vector3(this.x, this.y, this.z); }
    add(v: Vector3) { this.x += v.x; this.y += v.y; this.z += v.z; return this; }
    subVectors(_a: Vector3, _b: Vector3) { return this; }
    normalize() { return this; }
    multiplyScalar() { return this; }
    lerpVectors() { return this; }
    set(x: number, y: number, z: number) { this.x = x; this.y = y; this.z = z; }
    distanceTo() { return 80; }
  }

  class Scene {
    background: unknown = null;
    children: unknown[] = [];
    add = vi.fn();
    remove = vi.fn();
    traverse = vi.fn();
  }

  class PerspectiveCamera {
    position = Object.assign(new Vector3(0, 0, 80), {
      clone: () => new Vector3(0, 0, 80),
      distanceTo: () => 80,
      lerpVectors: vi.fn(),
    });
    aspect = 1;
    updateProjectionMatrix = vi.fn();
  }

  class WebGLRenderer {
    setPixelRatio = vi.fn();
    setSize = vi.fn();
    render = vi.fn();
    dispose = vi.fn();
    domElement = document.createElement('canvas');
  }

  class Color {
    constructor() {}
  }

  class Mesh {}

  return { Scene, PerspectiveCamera, WebGLRenderer, Color, Mesh, Vector3 };
});

vi.mock('three/addons/controls/OrbitControls.js', () => {
  class OrbitControls {
    enableDamping = false;
    dampingFactor = 0;
    minDistance = 0;
    maxDistance = 0;
    addEventListener = vi.fn();
    update = vi.fn();
    dispose = vi.fn();
    target = {
      clone: () => ({ x: 0, y: 0, z: 0, lerpVectors: vi.fn() }),
      lerpVectors: vi.fn(),
    };
  }
  return { OrbitControls };
});

import { TopologyRenderer, type LODTier } from './TopologyRenderer';

describe('TopologyRenderer', () => {
  let canvas: HTMLCanvasElement;

  beforeEach(() => {
    vi.clearAllMocks();
    canvas = document.createElement('canvas');
    Object.defineProperty(canvas, 'clientWidth', { value: 800, configurable: true });
    Object.defineProperty(canvas, 'clientHeight', { value: 600, configurable: true });
  });

  it('constructs without error', () => {
    const r = new TopologyRenderer(canvas);
    expect(r).toBeDefined();
    expect(r.scene).toBeDefined();
    expect(r.camera).toBeDefined();
    expect(r.controls).toBeDefined();
  });

  it('initial lodTier is far', () => {
    const r = new TopologyRenderer(canvas);
    expect(r.lodTier).toBe('far');
  });

  it('start begins render loop without error', () => {
    const r = new TopologyRenderer(canvas);
    const rafSpy = vi.spyOn(globalThis, 'requestAnimationFrame').mockReturnValue(1);
    r.start();
    expect(rafSpy).toHaveBeenCalled();
    r.dispose();
    rafSpy.mockRestore();
  });

  it('resize updates camera aspect and renderer size', () => {
    const r = new TopologyRenderer(canvas);
    r.resize(1024, 768);
    expect(r.camera.aspect).toBeCloseTo(1024 / 768);
    expect(r.camera.updateProjectionMatrix).toHaveBeenCalled();
  });

  it('dispose cancels animation frame', () => {
    const r = new TopologyRenderer(canvas);
    const cancelSpy = vi.spyOn(globalThis, 'cancelAnimationFrame').mockImplementation(() => {});
    const rafSpy = vi.spyOn(globalThis, 'requestAnimationFrame').mockReturnValue(42);
    r.start();
    r.dispose();
    expect(cancelSpy).toHaveBeenCalledWith(42);
    cancelSpy.mockRestore();
    rafSpy.mockRestore();
  });

  it('onLodChange registers callback', () => {
    const r = new TopologyRenderer(canvas);
    const cb = vi.fn();
    r.onLodChange(cb);
    expect(cb).not.toHaveBeenCalled();
  });

  it('focusOn does not throw', async () => {
    const r = new TopologyRenderer(canvas);
    const THREE = await import('three');
    expect(() => r.focusOn(new THREE.Vector3(1, 2, 3))).not.toThrow();
  });
});

describe('LODTier type', () => {
  it('accepts valid tier values', () => {
    const tiers: LODTier[] = ['far', 'mid', 'near'];
    expect(tiers).toHaveLength(3);
  });
});
