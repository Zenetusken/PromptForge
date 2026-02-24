# Frontend Internals

Detailed reference for frontend stores, shared utilities, key components, and routing. Read the source files for the latest API — this doc provides orientation and intent, not exhaustive signatures.

## Stores

Svelte 5 runes-based stores (`.svelte.ts` files in `frontend/src/lib/stores/`):

| Store | Purpose |
|-------|---------|
| `optimization.svelte.ts` | Current pipeline run state (isRunning, result, steps, strategyData, error). 4 steps: analyze, strategy, optimize, validate. Rolling `resultHistory[]` (last 10) for comparison workflow. Generic `_runNode()` helper for orchestration step execution. |
| `history.svelte.ts` | History list with pagination, filtering, search. |
| `forgeSession.svelte.ts` | Unified forge session state with multi-tab workspace (`WorkspaceTab[]`). `isActive` flag controls IDE workspace visibility — set by `activate()`, `loadRequest()`, `updateDraft(text)`, `focusTextarea()`; cleared by `reset()`. Draft text/metadata/context/strategy, tray/section open state, validation errors, auto-retry flag. `loadRequest()` replaces entire draft (opens new tab if current has text), `updateDraft()` patches individual fields, `buildMetadata()` produces API payload. `sessionStorage` persistence with hydration on load. |
| `forgeMachine.svelte.ts` | Mode state machine (compose → forging → review → compare). Panel width with sessionStorage persistence and 3 tiers: compact (240px), standard (380px), wide (560px). Comparison slot management. Guards transitions: `forge()`, `complete()`, `compare()`, `back()`, `reset()`. |
| `promptAnalysis.svelte.ts` | Client-side heuristic task type estimation and strategy recommendations. Debounced `analyzePrompt()` uses keyword patterns from `promptHeuristics.ts` + `recommendation.ts` engine. `updateFromPipeline()` accepts authoritative classification from pipeline results. |
| `provider.svelte.ts` | Provider selection, API key management (sessionStorage/localStorage), model selection, LLM header building. Health polling with MCP transition detection. |
| `projects.svelte.ts` | Project CRUD, prompt management, sidebar list. `hasLoaded`/`isLoading` guards for lazy initialization. |
| `sidebar.svelte.ts` | Tab state (history/projects) and open/closed state, both localStorage-persisted. Private `#_isOpen` backing field with getter/setter for auto-persistence through two-way bindings. Methods: `open()`, `close()`, `toggle()`, `openTo(tab)`. |
| `toast.svelte.ts` | Toast notifications. |
| `stats.svelte.ts` | Global + project-scoped stats. `load(total)` fetches global stats when history total changes. `setContext(projectName)` loads project-scoped stats, `clearProjectContext()` reverts to global. `activeStats` getter returns context-appropriate stats (project-scoped when active, global otherwise). `reset()` clears all. Initialized in `+layout.svelte`; project context set from `/projects/[id]` and `/optimize/[id]` route pages. |

## Shared Utilities

Located in `frontend/src/lib/utils/`:

| Utility | Purpose |
|---------|---------|
| `strategies.ts` | Canonical list of 10 strategy names, labels, descriptions, details (`STRATEGY_DETAILS`), and 10 unique colors (`STRATEGY_COLOR_META`). Single lookup: `getStrategyColor(name)` returns `StrategyColorMeta` with `bar`, `text`, `border`, `btnBg`, `rawRgba` fields. Cyan fallback for unknown. |
| `taskTypes.ts` | 14 task types with per-type neon colors (`TASK_TYPE_COLOR_META`). `getTaskTypeColor(name)` returns `TaskTypeColorMeta` with `text`, `chipBg`, `cssColor`, `rawRgba` fields. Dim fallback for unknown. |
| `complexity.ts` | 3-tier complexity colors with alias normalization (simple/low, moderate/medium, complex/high). `getComplexityColor(name)` returns `ComplexityColorMeta`. |
| `recommendation.ts` | Multi-signal recommendation engine for Strategy Explorer. Scores untried strategies via 4 weighted signals (task-type affinity 0.50, gap analysis 0.25, diversity 0.25) plus secondary composite (0.20) and confidence dampener. Upgrades precision when backend analytics are available (score matrix, variance, combo effectiveness). Pure functions, no side effects. |
| `stackTemplates.ts` | 8 pre-built `CodebaseContext` profiles for common stacks (SvelteKit, FastAPI, Next.js, Django, Express, Rails, Spring Boot, Go). |
| `promptParser.ts` | Pure functions for prompt text analysis: `extractVariables()` (detects `{{var}}` and `{var}` patterns with position/matchLength tracking), `detectSections()` (recognizes 7 section types: role, context, steps, constraints, examples, output, task). Used by ForgeEditor for gutter dots and variable chips. |
| `promptHeuristics.ts` | Client-side keyword-based task type estimation. Matches prompt text against patterns from `taskTypes.ts` and `strategies.ts` bestFor fields. Returns estimated task type + confidence. Used by `promptAnalysis.svelte.ts`. |
| `scoreDimensions.ts` | Score dimension definitions: `ALL_DIMENSIONS`, `DIMENSION_LABELS`, `DIMENSION_COLORS`, `SCORE_WEIGHTS`, `computeContribution()`. Pipeline step dot styling via `stepDotClass()`. |

## Key Components

### Layout & Navigation

| Component | Role |
|-----------|------|
| `ForgeIDEWorkspace.svelte` | Full-width 3-pane IDE overlay (replaces ForgePanel). Renders ForgeIDEExplorer (left), ForgeIDEEditor (center), ForgeIDEInspector (right) in a flex layout. Shown when `forgeSession.hasText` or `forgeMachine.mode !== 'compose'`. |
| `ForgeIDEExplorer.svelte` | Left pane (256px): collapsible context/assets section showing code snippet entries, metadata inputs (title/project/version). |
| `ForgeIDEEditor.svelte` | Center pane (flex-1): multi-tab workspace with tab bar (add/close/switch tabs), ForgeEditor in each tab. |
| `ForgeIDEInspector.svelte` | Right pane (320px): strategy selector, Analyze Only / Full Optimization action buttons, pipeline step inspector with status icons and timing, score display, error panel. Uses `optimizationState.runNodeAnalyze()` for ad-hoc single-step execution. |
| `Header.svelte` | Sticky glass header with sidebar toggle and `HeaderStats` bar. |
| `HeaderStats.svelte` | Wing formation stats bar via CSS grid (`1fr auto 1fr`): all content inside the grid so `1fr` columns guarantee true centering. Left wing (FORGED, AVG) in col 1 with `justify-self: start`, center task type chip in col 2, right wing (IMP, PROJ, TODAY + dimension mini-bars at `lg:`) in col 3 with `justify-self: end`. Center chip uses pulsating letter-contour stroke (`-webkit-text-stroke` + `header-contour-pulse` animation, color from task type). Context-aware: shows project name label when `statsState.activeProject` is set. Accepts `sidebarOpen` prop to pad left wing when sidebar toggle is visible. Reads from `statsState.activeStats`. Responsive: center only on mobile, adds wings progressively at `sm:`/`md:`/`lg:`. |
| `HistorySidebar.svelte` | Left sidebar with tabbed history/projects views. Bound to `sidebarState.isOpen`. |
| `Breadcrumbs.svelte` | Glass pill breadcrumb trail with monospace typography, `/` separators, sharp neon-cyan hover effect. Used on detail pages. |

### Home Page

| Component | Role |
|-----------|------|
| `OnboardingHero.svelte` | 3-step workflow guide (Write/Forge/Iterate). Dismissible via localStorage. Shows for < 5 total forges. |
| `RecentForges.svelte` | Last 6 optimizations as navigational cards (score, task type, strategy, time). "View all" opens sidebar history tab. |
| `RecentProjects.svelte` | Up to 4 active projects as navigational cards (prompt count, context dot, description). Uses `onMount` (not `$effect`) to avoid infinite retry. "View all" opens sidebar projects tab. |
| `StrategyInsights.svelte` | Interactive Strategy Explorer with distribution bars, recommendation engine, expandable detail panels. Accepts `onStrategySelect` callback for strategy pre-fill. |

### Forge & Input

| Component | Role |
|-----------|------|
| `ForgeOptionsTray.svelte` | Fly-out tray with three collapsible sections: ForgeMetadataSection (title/project/tags/version), ForgeContextSection (codebase fields, stack templates, auto-populates from project profile), ForgeStrategySection (override + secondary frameworks). |
| `ForgeComposer.svelte` | Compose mode body: ForgeChips + ForgeRecommendationChips + ForgeEditor (collapsed) + ForgeToolbar. Handles drag-and-drop context injection, focus mode overlay, and submit/cancel flow. |
| `ForgeEditor.svelte` | Prompt textarea with slash-command autocomplete, structure gutter dots (section markers), and variable chips. Supports collapsed (sidebar) and focus (fullscreen) variants. Uses `promptParser.ts` for real-time analysis. |
| `ForgeReview.svelte` | Inline result viewer: score header with dimension bars, optimized/original tabs, strategy reasoning, iteration timeline, action buttons (Copy/Iterate/Re-forge/Compare/Pop-out). |
| `ForgeCompare.svelte` | Two-column comparison: Slot A (reference) vs Slot B (current), per-dimension score delta bars, Keep A/Keep B/Back actions. Auto-widens panel to 560px. |
| `ForgeRecommendationChips.svelte` | Strategy recommendation chips derived from `promptAnalysis`. Shows top 3 suggestions when text > 50 chars and no manual strategy selected. |
| `ForgeError.svelte` | Shared error display with retry countdown and optional auto-retry. Reads from `optimizationState` and `forgeSession`. |
| `ContextProfileEditor.svelte` | Project detail page context editor. 9 fields, stack template picker, dirty detection, save/clear, readonly for archived. |

### History & Results

| Component | Role |
|-----------|------|
| `HistoryEntry.svelte` | Sidebar card with stretched link, hover overlay with Re-forge/Edit/Delete actions, delete confirmation bar. |
| `ResultPanel.svelte` | Full optimization result display (tabs: Optimized/Diff/Original, metadata, actions). |
| `ResultActions.svelte` | Copy/export/re-forge action buttons on result detail. |

## Routes

| Route | Content |
|-------|---------|
| `/` | Content dashboard: OnboardingHero (new users) or RecentForges + RecentProjects + StrategyInsights (returning users). Template cards when history is empty. |
| `/optimize/[id]` | Forge detail page with SSR data loading, breadcrumbs, context snapshot, error state, ForgeSiblings navigation. |
| `/projects/[id]` | Project detail with header card, context profile editor, prompt list (add/edit/delete/reorder), per-prompt forge history with filter bar. |

When `forgeSession.isActive` is true or the forge machine is in a non-compose mode, `+layout.svelte` shows `ForgeIDEWorkspace` (full-width 3-pane IDE: Explorer, Editor, Inspector). The workspace activates when the user clicks "New Forge" on the dashboard, presses `/`, clicks a template card, or loads a prompt from history/projects. Closing the last tab calls `reset()` which deactivates and returns to the dashboard.
