/**
 * N-body force simulation for taxonomy topology layout.
 *
 * Transforms UMAP positions into a galaxy-like spatial distribution:
 * - Long-range inverse-square repulsion spreads nodes apart
 * - Gentle centering prevents infinite drift
 * - Spiral perturbation breaks linear UMAP projections into organic arcs
 * - Collision resolution prevents overlap
 *
 * Respects semantic distances from UMAP while reshaping the distribution
 * from elongated lines into a more spatial, navigable galaxy form.
 *
 * Budget: <100ms for 500 nodes at 60 iterations.
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

// --- Force constants ---
// Tuned for 20-200 nodes in a UMAP-scaled space (~[-10, 10] per axis).

/** Inverse-square repulsion strength. Pushes all nodes apart. */
const REPULSION = 0.15;
/** Distance beyond which repulsion is negligible (performance cutoff). */
const REPULSION_RANGE = 25;
/** Collision repulsion strength (much stronger, short range). */
const COLLISION_STRENGTH = 0.8;
/** Pull toward centroid. Prevents explosion and keeps the graph centered. */
const CENTERING = 0.008;
/** Perpendicular spiral force. Breaks linear UMAP alignment into arcs. */
const SPIRAL = 0.03;
/** Velocity decay per iteration. Lower = more damping = faster settling. */
const DAMPING = 0.88;

/**
 * Run the n-body simulation synchronously.
 */
export function settleForces(input: WorkerInput): WorkerOutput {
  const { positions, sizes, iterations } = input;
  if (positions.length !== sizes.length * 3) {
    throw new Error(
      `settleForces: positions.length (${positions.length}) must equal sizes.length * 3 (${sizes.length * 3})`
    );
  }
  const n = sizes.length;
  if (n === 0) return { positions: new Float32Array(0), elapsed: 0 };
  const start = performance.now();

  const pos = new Float32Array(positions);
  const vel = new Float32Array(n * 3);
  const force = new Float32Array(n * 3);

  for (let iter = 0; iter < iterations; iter++) {
    force.fill(0);

    // --- 1. Compute centroid ---
    let cx = 0, cy = 0, cz = 0;
    for (let i = 0; i < n; i++) {
      cx += pos[i * 3];
      cy += pos[i * 3 + 1];
      cz += pos[i * 3 + 2];
    }
    cx /= n; cy /= n; cz /= n;

    // --- 2. Pairwise forces (O(n²)) ---
    for (let i = 0; i < n; i++) {
      const ix = i * 3, iy = ix + 1, iz = ix + 2;
      for (let j = i + 1; j < n; j++) {
        const jx = j * 3, jy = jx + 1, jz = jx + 2;

        const dx = pos[ix] - pos[jx];
        const dy = pos[iy] - pos[jy];
        const dz = pos[iz] - pos[jz];
        const distSq = dx * dx + dy * dy + dz * dz;
        const dist = Math.sqrt(distSq) || 0.001;

        // Skip if far beyond repulsion range
        if (dist > REPULSION_RANGE) continue;

        // Long-range inverse-square repulsion (galaxy spread)
        const repF = REPULSION / (distSq + 1); // +1 softens singularity
        const repNorm = repF / dist; // normalize direction
        force[ix] += dx * repNorm;
        force[iy] += dy * repNorm;
        force[iz] += dz * repNorm;
        force[jx] -= dx * repNorm;
        force[jy] -= dy * repNorm;
        force[jz] -= dz * repNorm;

        // Short-range collision resolution (strong, prevents overlap)
        const minDist = (sizes[i] + sizes[j]) * 0.6;
        if (dist < minDist) {
          const collF = COLLISION_STRENGTH * (minDist - dist) / dist;
          force[ix] += dx * collF;
          force[iy] += dy * collF;
          force[iz] += dz * collF;
          force[jx] -= dx * collF;
          force[jy] -= dy * collF;
          force[jz] -= dz * collF;
        }
      }
    }

    // --- 3. Per-node forces ---
    for (let i = 0; i < n; i++) {
      const ix = i * 3, iy = ix + 1, iz = ix + 2;

      // Centering: gentle pull toward centroid
      force[ix] -= (pos[ix] - cx) * CENTERING;
      force[iy] -= (pos[iy] - cy) * CENTERING;
      force[iz] -= (pos[iz] - cz) * CENTERING;

      // Spiral: perpendicular force breaks linearity into arcs.
      // Compute vector from centroid to node, then cross with Y-axis
      // to get a tangential push in the XZ plane.
      const rx = pos[ix] - cx;
      const rz = pos[iz] - cz;
      const rLen = Math.sqrt(rx * rx + rz * rz) || 0.001;
      // Tangential direction (perpendicular in XZ plane, clockwise)
      const tx = -rz / rLen;
      const tz = rx / rLen;
      // Scale by distance from centroid (more force at edges → wider arcs)
      const spiralMag = SPIRAL * Math.min(rLen, 8);
      force[ix] += tx * spiralMag;
      force[iz] += tz * spiralMag;
    }

    // --- 4. Integrate: apply forces with velocity damping ---
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
