# Project Node UX — Graph Integration

## Context

The topology graph was built for a single-project world. Project nodes (`state="project"`) have zero special handling — they render as icosahedrons (identical to clusters), show only a label on hover, fall through to cluster mode in the Inspector, and have no dedicated metadata display. With multi-project (ADR-005), this creates a disorienting experience where the largest structural nodes in the hierarchy feel like broken clusters.

This is a bridge fix — making project nodes first-class citizens in the current flat topology. The full hierarchical drill-down (Roadmap: "Hierarchical topology navigation") will eventually replace this with L0/L1/L2/L3 navigation, but that's a major refactor. This spec covers the minimum viable project UX that works within the current flat graph.

## Changes

### 1. Rich hover tooltip (all node types)

**Current**: Label only, no metadata.
**After**: Single-line monospace tooltip with node-type-adapted metadata.

| Node type | Tooltip format |
|-----------|---------------|
| cluster | `label · DOMAIN · Nm · score` |
| domain | `label · Nc clusters · avg score` |
| project | `label · Nd domains · Nc clusters` |

Source: all fields available on `SceneNode` (from TopologyData.ts). No API call needed.

**File**: `SemanticTopology.svelte` — replace the `{label}` text with a computed tooltip string.

### 2. Inspector project mode

**Current**: Project nodes fall through to cluster mode (`if state === 'domain' → domain mode, else → cluster mode`).
**After**: Add `'project'` mode to `TopologyInfoPanel.svelte`.

Project mode displays:
- **Header**: Project label (large, monospace, consistent with domain mode)
- **Domains row**: Child domain labels as colored chips (using `taxonomyColor()`)
- **Stats**: `N domains · N clusters · N optimizations` (from detail API response)
- **Avg Score**: Averaged across project's optimizations
- **Recent optimizations**: List (same format as cluster mode — already returned by the fixed API)

Mode determination: `if (detail.state === 'project') return 'project'` — insert before the domain check.

**Files**: `TopologyInfoPanel.svelte` (mode logic + project template), `Inspector.svelte` (pass mode through)

### 3. Node rendering — dodecahedron for projects

**Current**: Projects render as icosahedrons (same as clusters). Visually indistinguishable.
**After**: Projects render as dodecahedrons (same as domains) with the rotation animation. This signals "structural node" in the visual language already established by domain nodes. Size is already correct (descendant aggregation from previous fix).

**File**: `SemanticTopology.svelte` — change the `isDomain` check to `isStructural = node.state === 'domain' || node.state === 'project'`.

### 4. Sidebar project group display

**Current**: `project:Legacy` and `project:project-synthesis/ProjectSynthesis` as group headers (from our previous fix).
**After**: Project groups render with a distinct project icon/indicator. The group header strips the `project:` prefix (already done) and shows the project label. The group's color dot uses the project's own color (or general gray).

Already partially implemented. Verify it works correctly.

## Files to modify

| File | Change |
|------|--------|
| `frontend/src/lib/components/taxonomy/SemanticTopology.svelte` | Rich tooltip, structural node rendering |
| `frontend/src/lib/components/taxonomy/TopologyInfoPanel.svelte` | Project mode in inspector overlay |
| `frontend/src/lib/components/layout/Inspector.svelte` | Project mode passthrough |

## Constraints

- No new API endpoints — all data already available from existing tree + detail endpoints
- No changes to the 3D force layout or worker
- Forward-compatible with the hierarchical drill-down roadmap item
- Follow existing brand guidelines: dark backgrounds, 1px neon contours, no rounded corners, monospace labels
