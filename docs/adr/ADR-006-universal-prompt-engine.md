# ADR-006: Universal Prompt Engine — Domain-Agnostic Architecture

**Status:** Accepted
**Date:** 2026-04-08
**Authors:** Human + Claude Opus 4.6

## Context

### The Product Identity Question

Project Synthesis has two identities:

1. **The engine** — a self-organizing taxonomy that clusters prompts, discovers patterns, and injects proven techniques. This is domain-agnostic. A marketing team's prompts would organically discover "copywriting", "brand-voice", "campaign" domains the same way developer prompts discovered "backend", "frontend", "devops".

2. **The scaffolding** — GitHub integration, codebase scanning, IDE MCP server, developer-specific domain seeds, code-focused seed agents. This assumes the user is a developer.

The engine is the value. The scaffolding is the distribution channel. The question is whether the architecture should constrain itself to developers or remain universal.

### Current State Audit

An audit of the codebase reveals the engine is already universal, but the scaffolding introduces developer bias at 10 specific points:

**Hard blocks (features unavailable to non-developers):**

| Item | What | Impact |
|------|------|--------|
| Seed agents | 5/5 are developer-focused (coding, testing, architecture, analysis, docs) | Zero agents for marketing, legal, business, content creation |
| GitHub integration | Sole external integration; required for explore phase | Non-developers cannot use context enrichment from external sources |
| Codebase scanning | Scans for Python/Node manifests, code files, `.cursorrules` | No workspace intelligence for non-code projects |
| Domain keyword seeds | All keywords are tech-focused (API, React, Docker, SQL) | Non-developer prompts always classified as "general" |
| Workspace files | Looks for `CLAUDE.md`, `.cursorrules` — developer tooling files | No guidance file discovery for non-technical workspaces |

**Soft biases (features work but with reduced quality):**

| Item | What | Impact |
|------|------|--------|
| Pre-seeded domains | 6/8 are technical; "general" has zero keywords | Non-developer domains never organically emerge without traffic |
| Analyzer prompt | 6 technical domain rules, 1 SaaS example, rest → "general" | No explicit decision rules for marketing, legal, education, etc. |
| Heuristic analyzer | Weakness detection for code/data/system; minimal for writing | Business weaknesses (missing market context, unclear audience) never flagged |
| Seed strategy mapping | `coding → structured-output`, `writing → role-playing` | Reasonable defaults but no domain-specific refinement for non-dev work |
| README language | Claims "prompt optimization tool" but 70% of features/examples are developer-centric | Sets wrong expectation for non-developer users |

**Already universal (no changes needed):**

| Item | What |
|------|------|
| Task type classification | 7 types including `writing`, `analysis`, `creative`, `general` |
| Strategy files | All 6 strategies are domain-agnostic |
| Taxonomy engine | Organic domain discovery, pattern extraction, cross-project sharing |
| EmbeddingIndex | Clusters by semantic similarity, not by hardcoded domain |
| GlobalPattern tier | Promotes patterns across projects regardless of domain |
| Scoring system | 5-dimension evaluation works on any prompt type |
| Refinement loop | Iterative improvement is domain-agnostic |

### The Core Insight

The taxonomy engine's organic domain discovery IS the universal mechanism. When a marketing team uses Project Synthesis:
- Their prompts cluster by semantic similarity (not by pre-coded rules)
- Domains like "copywriting", "brand-voice", "email-campaign" emerge organically
- MetaPatterns extract reusable techniques ("always specify target audience and tone")
- Cross-project GlobalPatterns share universal techniques across teams

This already works. The only thing preventing it is the scaffolding — specifically the 5 hard blocks that make the non-developer experience empty.

## Decision

### Principle: The engine is universal. The scaffolding is extensible.

**The taxonomy engine, scoring system, pattern extraction, and optimization pipeline must NEVER be narrowed to developer-only use.** No feature should assume prompts are about code. No classification should hardcode developer domains. No pattern extraction should privilege technical signals over other domains.

**The developer scaffolding is the FIRST vertical, not the ONLY one.** GitHub integration, codebase scanning, and IDE MCP are the developer distribution channel. Future verticals (marketing, legal, education, etc.) would add their own scaffolding without modifying the engine.

### Architectural Constraints

1. **No hardcoded domain assumptions in the engine layer.** Domain classification must flow through organic discovery (`_propose_domains()` in warm path Phase 5), not through hardcoded rules. The pre-seeded developer domains are bootstrapping data, not architectural constraints.

2. **Task type classification stays universal.** The 7 task types (`coding`, `writing`, `analysis`, `creative`, `data`, `system`, `general`) cover any domain. If a new type is needed (e.g., `legal`, `marketing`), it's added to the Literal enum — the engine adapts.

3. **Seed agents are the extensibility mechanism for verticals.** The `prompts/seed-agents/*.md` hot-reload system is the correct pattern. Adding marketing seed agents is a content addition, not a code change. Each vertical ships its own seed agents.

4. **External integrations should be pluggable, not GitHub-only.** The explore phase should support multiple context sources: GitHub repos (developers), Google Drive (business teams), Notion (product teams), local file systems (anyone). The `ContextEnrichmentService` abstraction already supports this — only the GitHub implementation exists today.

5. **Heuristic signals should be domain-configurable.** The `HeuristicAnalyzer`'s weakness detection signals should be loadable from domain metadata (similar to how `DomainSignalLoader` loads keywords). A marketing domain's metadata would include weaknesses like "missing target audience definition" or "no call-to-action specified". A legal domain would include "missing jurisdiction" or "no precedent cited".

6. **Pattern extraction and injection are already universal.** `extract_patterns.md` and `pattern_injection.py` operate on semantic similarity, not domain labels. No changes needed — this is the correct architecture.

7. **The analyzer prompt's domain rules should be examples, not constraints.** The current analyzer prompt lists 7 explicit domain decision rules (backend, frontend, database, devops, security, fullstack, data). These should be framed as examples of organic domains, with guidance to classify ANY subject area — not just technical ones. The instruction "use a descriptive domain name (marketing, finance, education, legal, design)" already exists but is buried as a fallback.

### What This Means in Practice

**For the engine layer (no changes needed):**
- Taxonomy clustering, pattern extraction, GlobalPattern promotion, adaptive scheduling, EmbeddingIndex — all domain-agnostic by design
- Organic domain discovery fires when coherent sub-populations emerge under "general" — works for any prompt type
- Cross-project pattern sharing evaluates semantic similarity, not domain labels

**For the scaffolding layer (extensible, not modified):**

The following are CORRECT as developer-first implementations. They should NOT be generalized — they should be supplemented with additional verticals when demand exists:

| Component | Developer vertical (exists) | Future vertical (example) |
|-----------|---------------------------|--------------------------|
| Seed agents | `coding-implementation.md`, `testing-quality.md`, etc. | `marketing-copywriting.md`, `legal-contract-review.md` |
| External integration | GitHub repos → codebase context | Google Drive → document context, Notion → knowledge base context |
| Workspace scanning | Code manifests, `.cursorrules` | Brand guidelines, style guides, tone-of-voice docs |
| Domain keyword seeds | backend, frontend, devops, etc. | copywriting, campaign, brand-voice, audience-research |
| Heuristic weaknesses | "no language specified", "missing test criteria" | "no target audience", "missing call-to-action", "unclear brand voice" |

**For documentation and positioning:**
- README should describe the product as "AI-powered prompt optimization" (not "for developers")
- Developer features should be positioned as the first vertical, with language acknowledging the engine is universal
- The architecture overview should explain the engine/scaffolding distinction

### Migration Path

No immediate code changes required. The architecture already supports universality. This ADR documents the decision so future development respects it:

**Phase 1 (immediate — positioning):** Update README to frame developers as the primary audience, not the only audience. Remove language that implies the tool only works for code.

**Phase 2 (on demand — content):** When a non-developer audience is identified, add seed agents for that vertical. This is a content addition in `prompts/seed-agents/`, not a code change. The hot-reload system handles it automatically.

**Phase 3 (on demand — integrations):** When a non-developer integration is needed (e.g., Google Drive, Notion), implement it as a new `ContextProvider` behind the existing `ContextEnrichmentService` abstraction. The explore phase becomes provider-pluggable.

**Phase 4 (on demand — classification):** When a non-developer vertical has enough traffic, the organic domain discovery will create domains automatically. If bootstrapping is needed, add domain keyword seeds via the existing migration pattern (same as the developer domain seeds).

## Consequences

### Positive

- The engine scales to any domain without code changes
- New verticals are content additions (seed agents, domain keywords), not architectural changes
- Cross-domain pattern sharing works universally — a technique discovered in marketing ("always specify target audience") can benefit a developer writing user-facing documentation
- The product can expand beyond developers without breaking existing functionality
- Clear separation of engine (universal) from scaffolding (vertical-specific) prevents future narrowing

### Negative

- The developer scaffolding may create a perception that the tool is developer-only, even though the engine is universal
- Non-developer users who discover the tool today will have a degraded experience (no seed agents, no context enrichment, "general" domain for everything)
- Adding new verticals requires content creation effort (seed agents, domain keywords, weakness signals) even though no code changes are needed

### Risks

- **Feature drift toward developer-only:** Without this ADR, new features might hardcode developer assumptions. Example: a "code review" feature that only works on GitHub PRs, when the engine could support "content review" for any text. Mitigation: this ADR establishes the principle that engine-layer features must be universal.
- **Quality gap for non-developers:** Even though the engine works, the quality of optimization for non-developer prompts is lower because few-shot examples, domain keywords, and weakness detection are all developer-focused. Mitigation: organic domain discovery and pattern extraction will improve quality over time as non-developer prompts accumulate.
- **Complexity of multi-vertical support:** Supporting multiple context providers (GitHub, Google Drive, Notion) adds integration complexity. Mitigation: Phase 3 is on-demand, triggered by actual user need.

## References

- Taxonomy engine: `backend/app/services/taxonomy/` (domain-agnostic by design)
- Organic domain discovery: `engine.py` → `_propose_domains()` (fires for any coherent sub-population)
- Seed agents: `prompts/seed-agents/*.md` (hot-reloaded, extensible)
- Domain signal loader: `backend/app/services/domain_signal_loader.py` (keyword-driven, configurable)
- Context enrichment: `backend/app/services/context_enrichment.py` (abstraction layer)
- Heuristic analyzer: `backend/app/services/heuristic_analyzer.py` (signal-driven, extensible)
- ADR-005: Taxonomy scaling architecture (multi-project isolation supports multi-vertical)
