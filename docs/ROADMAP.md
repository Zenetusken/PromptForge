# Project Synthesis — Roadmap

Living document tracking planned improvements. Items are prioritized but not scheduled. Each entry links to the relevant spec or ADR when available.

## Conventions

- **Planned** — designed, waiting for implementation
- **Exploring** — under investigation, no decision yet
- **Deferred** — considered and postponed with rationale

---

## Planned

### Multi-label domain classification
**Status:** Planned
**Context:** Domain classification currently uses a single `domain` field with "primary: qualifier" convention in `domain_raw`. Cross-cutting concerns (e.g., backend + security) are expressed but the data model is single-valued. A proper `domain_tags: list[str]` column on Optimization and PromptCluster would enable multi-label classification, richer cluster grouping, and more accurate cross-domain edge generation in the Pattern Graph.
**Prerequisite:** Alembic migration, schema change to both models, update all save paths

### Unified scoring service
**Status:** Planned
**Context:** The scoring orchestration (heuristic compute → historical stats fetch → hybrid blend → delta compute) is repeated across `pipeline.py`, `sampling_pipeline.py`, `save_result.py`, and `optimize.py` with divergent error handling. A shared `ScoringService` would eliminate duplication and ensure consistent behavior across all tiers.
**Spec:** Code quality audit (2026-03-27) identified this as the #3 finding

### Conciseness heuristic calibration for technical prompts
**Status:** Exploring
**Context:** The heuristic conciseness scorer uses Type-Token Ratio which penalizes repeated domain terminology (e.g., "scoring", "heuristic", "pipeline" across sections). Technical specification prompts score artificially low on conciseness despite being well-structured. Needs a domain-aware TTR adjustment or alternative metric.

### Unified onboarding journey
**Status:** Planned
**Context:** The current system has 3 separate tier-specific modals (InternalGuide, SamplingGuide, PassthroughGuide) that fire independently on routing tier detection. This creates a fragmented first-run experience — users only see one tier's guide and miss the others. Two changes required:

**1. Consolidated onboarding modal:** Replace the 3 separate modals with a single multi-step onboarding journey that walks the user through all 3 tiers sequentially (Internal → Sampling → Passthrough). Each tier section is actionable — the user must acknowledge each before proceeding. The modal blocks the UI until all steps are actioned. Fires at every startup unless a "Don't show again" checkbox is checked and persisted to preferences.

**2. Dynamic routing change toasts:** Replace the per-tier-change modal triggers with concise inline toasts that explain *what caused* the routing change (e.g., "Routing changed to passthrough — no provider detected", "Sampling available — VS Code bridge connected"). These fire only on *automatic* tier transitions, not when the user manually toggles force_passthrough or force_sampling.

**Prerequisite:** Refactor `tier-onboarding.svelte.ts`, merge 3 guide components into 1, new `onboarding-dismissed` preference field, update `triggerTierGuide()` to emit toast instead of modal after initial onboarding, update `+page.svelte` startup gate.

### Passthrough refinement UX
**Status:** Deferred
**Context:** Passthrough results cannot be refined (returns 503). Refinement requires an LLM provider to rewrite the prompt. The user already has their external LLM — refinement would need a different interaction model (e.g., show the assembled refinement prompt for copy-paste like the initial passthrough flow).
**Rationale:** Low demand — users who use passthrough can iterate manually

---

## Completed (recent)

### Multi-dimensional domain classification (v0.3.6-dev)
LLM analyze prompt and heuristic analyzer now output "primary: qualifier" format (e.g., "backend: security"). Taxonomy clustering, Pattern Graph edges, and color resolution all parse the primary domain for comparison while preserving the full qualifier for display. Zero schema changes required.

### Zero-LLM heuristic suggestions (v0.3.6-dev)
Deterministic suggestions from weakness analysis, score dimensions, and strategy context for the passthrough tier. 18 unit tests.

### Structural pattern extraction (v0.3.6-dev)
Zero-LLM meta-pattern extraction via score delta detection and structural regex. Passthrough results now contribute patterns to the taxonomy knowledge graph.

### Process-level singleton RoutingManager (v0.3.6-dev)
Fixed 6 routing tier bugs caused by per-session RoutingManager replacement in FastMCP's Streamable HTTP transport.

### Inspector metadata parity (v0.3.6-dev)
All tiers now show provider, scoring mode, model, suggestions, changes, domain, and duration in the Inspector panel.

### Electric neon domain palette (v0.3.6-dev)
Domain colors overhauled to vibrant neon tones with zero overlap to tier accent colors. Sharp wireframe contour nodes in Pattern Graph matching the brand's zero-effects directive.
