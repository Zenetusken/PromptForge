/**
 * Web Worker for force-directed collision resolution.
 *
 * Input: node positions from UMAP (may overlap).
 * Output: settled positions after 50 iterations of repulsion.
 * Budget: <100ms for 500 nodes.
 */

export interface WorkerInput {
  positions: Float32Array; // [x0,y0,z0, x1,y1,z1, ...]
  sizes: Float32Array;     // [s0, s1, ...]
  iterations: number;
}

export interface WorkerOutput {
  positions: Float32Array;
  elapsed: number;
}

const REPULSION = 0.5;
const DAMPING = 0.95;

/**
 * Run force settling synchronously (for use inside worker or inline).
 */
export function settleForces(input: WorkerInput): WorkerOutput {
  const { positions, sizes, iterations } = input;
  if (positions.length !== sizes.length * 3) {
    throw new Error(
      `settleForces: positions.length (${positions.length}) must equal sizes.length * 3 (${sizes.length * 3})`
    );
  }
  const n = sizes.length;
  const start = performance.now();

  // Copy positions (don't mutate input)
  const pos = new Float32Array(positions);
  const vel = new Float32Array(n * 3);
  const force = new Float32Array(n * 3);

  for (let iter = 0; iter < iterations; iter++) {
    // Reset forces
    force.fill(0);

    // Pairwise repulsion (O(n^2) — acceptable for n<=2000)
    for (let i = 0; i < n; i++) {
      const ix = i * 3, iy = ix + 1, iz = ix + 2;
      for (let j = i + 1; j < n; j++) {
        const jx = j * 3, jy = jx + 1, jz = jx + 2;

        const dx = pos[ix] - pos[jx];
        const dy = pos[iy] - pos[jy];
        const dz = pos[iz] - pos[jz];
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz) || 0.001;
        const minDist = (sizes[i] + sizes[j]) * 0.5;

        if (dist < minDist * 2) {
          const f = REPULSION * (minDist * 2 - dist) / dist;
          force[ix] += dx * f; force[iy] += dy * f; force[iz] += dz * f;
          force[jx] -= dx * f; force[jy] -= dy * f; force[jz] -= dz * f;
        }
      }
    }

    // Apply forces with velocity damping
    for (let i = 0; i < n; i++) {
      const ix = i * 3, iy = ix + 1, iz = ix + 2;
      vel[ix] = (vel[ix] + force[ix]) * DAMPING;
      vel[iy] = (vel[iy] + force[iy]) * DAMPING;
      vel[iz] = (vel[iz] + force[iz]) * DAMPING;
      pos[ix] += vel[ix];
      pos[iy] += vel[iy];
      pos[iz] += vel[iz];
    }
  }

  return { positions: pos, elapsed: performance.now() - start };
}

// Worker message handler (only active when loaded as Web Worker)
if (typeof self !== 'undefined' && typeof (self as any).importScripts === 'function') {
  self.onmessage = (event: MessageEvent<WorkerInput>) => {
    const result = settleForces(event.data);
    (self as any).postMessage(result, [result.positions.buffer]);
  };
}
