import { describe, it, expect } from 'vitest';
import { settleForces, type WorkerInput } from './TopologyWorker';

/** Build a minimal valid WorkerInput. */
function makeInput(overrides: Partial<WorkerInput> & { positions: Float32Array; sizes: Float32Array }): WorkerInput {
  const n = overrides.sizes.length;
  return {
    restPositions: overrides.restPositions ?? new Float32Array(overrides.positions),
    parentIndices: overrides.parentIndices ?? new Int32Array(n).fill(-1),
    domainGroups: overrides.domainGroups ?? new Int32Array(n),
    iterations: overrides.iterations ?? 10,
    ...overrides,
  };
}

describe('settleForces', () => {
  it('returns settled positions for valid input', () => {
    const result = settleForces(makeInput({
      positions: new Float32Array([0, 0, 0, 1, 1, 1]),
      sizes: new Float32Array([1, 1]),
    }));
    expect(result.positions).toHaveLength(6);
    expect(result.elapsed).toBeGreaterThanOrEqual(0);
  });

  it('does not mutate the input positions array', () => {
    const positions = new Float32Array([0, 0, 0, 0.1, 0.1, 0.1]);
    const original = new Float32Array(positions);
    settleForces(makeInput({ positions, sizes: new Float32Array([1, 1]) }));
    expect(positions).toEqual(original);
  });

  it('throws when positions.length !== sizes.length * 3', () => {
    expect(() => settleForces(makeInput({
      positions: new Float32Array([0, 0, 0, 1, 1]),
      sizes: new Float32Array([1, 1]),
    }))).toThrow(/positions\.length.*must equal.*sizes\.length \* 3/);
  });

  it('handles single node without error', () => {
    const result = settleForces(makeInput({
      positions: new Float32Array([5, 10, 15]),
      sizes: new Float32Array([2]),
    }));
    // Single node anchored to UMAP rest position — stays close
    expect(result.positions[0]).toBeCloseTo(5, 0);
    expect(result.positions[1]).toBeCloseTo(10, 0);
    expect(result.positions[2]).toBeCloseTo(15, 0);
  });

  it('separates overlapping nodes', () => {
    const result = settleForces(makeInput({
      positions: new Float32Array([0, 0, 0, 0.01, 0, 0]),
      sizes: new Float32Array([2, 2]),
      iterations: 50,
    }));
    const dx = result.positions[0] - result.positions[3];
    const dy = result.positions[1] - result.positions[4];
    const dz = result.positions[2] - result.positions[5];
    const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
    expect(dist).toBeGreaterThan(0.01);
  });

  it('same-domain nodes attract toward each other', () => {
    // Two nodes far apart but in the same domain
    const result = settleForces(makeInput({
      positions: new Float32Array([0, 0, 0, 15, 0, 0]),
      sizes: new Float32Array([1, 1]),
      domainGroups: new Int32Array([0, 0]), // same domain
      iterations: 60,
    }));
    const dist = Math.abs(result.positions[0] - result.positions[3]);
    // Should be closer than 15 (initial distance) due to domain attraction
    expect(dist).toBeLessThan(15);
  });

  it('parent-child spring pulls children toward parent', () => {
    // Parent at origin, child far away
    const result = settleForces(makeInput({
      positions: new Float32Array([0, 0, 0, 20, 0, 0]),
      sizes: new Float32Array([2, 1]),
      parentIndices: new Int32Array([-1, 0]), // node 1's parent is node 0
      iterations: 60,
    }));
    const childDist = Math.abs(result.positions[3]);
    // Child should be pulled closer to parent (but not on top — rest length)
    expect(childDist).toBeLessThan(20);
    expect(childDist).toBeGreaterThan(1); // not collapsed
  });
});
