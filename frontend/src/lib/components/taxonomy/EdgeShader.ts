/**
 * Depth-attenuated edge shader for topology hierarchical edges.
 *
 * Fades edges based on distance from camera — background edges become
 * near-invisible, giving the 3D depth natural z-culling for visual clarity.
 */
import * as THREE from 'three';

export const EDGE_DEPTH_VERTEX = /* glsl */ `
  varying float vDepth;
  void main() {
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    vDepth = -mvPosition.z;
    gl_Position = projectionMatrix * mvPosition;
  }
`;

export const EDGE_DEPTH_FRAGMENT = /* glsl */ `
  uniform vec3 uColor;
  uniform float uBaseOpacity;
  uniform float uNearDist;
  uniform float uFarDist;
  uniform float uMaxReduction;

  varying float vDepth;

  void main() {
    // Proportional attenuation — depth reduces base opacity by up to
    // uMaxReduction (e.g. 0.6 = at most 60% dimmer at far distance).
    // This preserves density-opacity as the dominant control and prevents
    // the double-reduction problem (density * depth → near-zero).
    float t = clamp((vDepth - uNearDist) / (uFarDist - uNearDist), 0.0, 1.0);
    float opacity = uBaseOpacity * (1.0 - t * uMaxReduction);
    gl_FragColor = vec4(uColor, opacity);
  }
`;

/** Create uniforms for the edge depth shader.
 *  Camera range: starts at z=80, auto-focuses to ~60, zoom range 3-200.
 *  Proportional model: far edges render at (1 - maxReduction) of base opacity.
 *  With maxReduction=0.25: near=full base, far=75% of base — subtle depth cue
 *  that doesn't compete with density opacity for visibility control. */
export function createEdgeDepthUniforms(color: number, baseOpacity: number) {
  return {
    uColor: { value: new THREE.Color(color) },
    uBaseOpacity: { value: baseOpacity },
    uNearDist: { value: 30.0 },
    uFarDist: { value: 120.0 },
    uMaxReduction: { value: 0.25 },
  };
}
