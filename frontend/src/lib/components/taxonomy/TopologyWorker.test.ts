import { describe, it, expect } from 'vitest';
import { settleForces } from './TopologyWorker';

describe('settleForces', () => {
  it('returns settled positions for valid input', () => {
    const positions = new Float32Array([0, 0, 0, 1, 1, 1]);
    const sizes = new Float32Array([1, 1]);
    const result = settleForces({ positions, sizes, iterations: 10 });
    expect(result.positions).toHaveLength(6);
    expect(result.elapsed).toBeGreaterThanOrEqual(0);
  });

  it('does not mutate the input positions array', () => {
    const positions = new Float32Array([0, 0, 0, 0.1, 0.1, 0.1]);
    const sizes = new Float32Array([1, 1]);
    const original = new Float32Array(positions);
    settleForces({ positions, sizes, iterations: 5 });
    expect(positions).toEqual(original);
  });

  it('throws when positions.length !== sizes.length * 3', () => {
    const positions = new Float32Array([0, 0, 0, 1, 1]); // 5 — not divisible by 3 for 2 nodes
    const sizes = new Float32Array([1, 1]);
    expect(() => settleForces({ positions, sizes, iterations: 1 })).toThrow(
      /positions\.length.*must equal.*sizes\.length \* 3/
    );
  });

  it('handles single node without error', () => {
    const positions = new Float32Array([5, 10, 15]);
    const sizes = new Float32Array([2]);
    const result = settleForces({ positions, sizes, iterations: 10 });
    // Single node has nothing to repel — stays in place
    expect(result.positions[0]).toBeCloseTo(5, 1);
    expect(result.positions[1]).toBeCloseTo(10, 1);
    expect(result.positions[2]).toBeCloseTo(15, 1);
  });

  it('separates overlapping nodes', () => {
    // Two nodes at nearly the same position
    const positions = new Float32Array([0, 0, 0, 0.01, 0, 0]);
    const sizes = new Float32Array([2, 2]);
    const result = settleForces({ positions, sizes, iterations: 50 });
    const dx = result.positions[0] - result.positions[3];
    const dy = result.positions[1] - result.positions[4];
    const dz = result.positions[2] - result.positions[5];
    const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
    // After settling, nodes should be further apart than before
    expect(dist).toBeGreaterThan(0.01);
  });
});
