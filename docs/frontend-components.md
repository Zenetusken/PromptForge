# Frontend Components Reference

Complete inventory of all 75 Svelte 5 components (65 in `components/`, 10 in `components/ui/`). Components are organized into **shared** (reusable across the app) and **individual** (single-use, feature-specific) categories.

## Shared Components

Reusable building blocks imported by multiple features. Changes here have wide blast radius.

### UI Primitives (`components/ui/`)

Barrel-exported from `components/ui/index.ts`. Import as `{ Tooltip, MetaBadge, StatusDot } from "./ui"`.

| Component | Props | Description |
|-----------|-------|-------------|
| `Tooltip` | `text`, `children: Snippet`, `side?`, `sideOffset?`, `class?`, `interactive?` | bits-ui floating label on hover. `interactive` keeps tooltip open when hovered. |
| `MetaBadge` | `type: "strategy"\|"task"\|"tag"\|"complexity"`, `value`, `variant?: "text"\|"pill"\|"solid"`, `size?: "sm"\|"xs"`, `showTooltip?` | Colored badge with auto-resolved display label and color from utility lookups. |
| `EntryTitle` | `title: string\|null`, `maxLength?`, `placeholder?`, `class?` | Truncated title with fallback placeholder. Pure presentational. |
| `Separator` | `class?`, `orientation?: "horizontal"\|"vertical"` | bits-ui divider line. |
| `Switch` | `checked: boolean`, `onCheckedChange`, `label?` | bits-ui toggle. |
| `SidebarTabs` | `value`, `onValueChange`, `tabs: {value, label, testid?, activeClass?}[]`, `label?` | bits-ui tabbed navigation strip. |
| `WindowTabStrip` | `tabs: {id, label, icon?}[]`, `activeTab`, `onTabChange`, `accent?: "cyan"\|"green"` | Shared window tab bar. Replaces duplicated tab strips in ControlPanel, Workspace, StrategyWorkshop, NetworkMonitor. |
| `EmptyState` | `icon`, `message`, `submessage?` | Centered empty-state placeholder with icon + text. Used across 6+ windows. |
| `StatusDot` | `color: "green"\|"yellow"\|"red"\|"cyan"\|"orange"`, `class?` | Enforces `rounded-full` on all status indicators. Replaces square dots. |
| `InlineProgress` | `percent`, `color?: "cyan"\|"green"\|"yellow"`, `class?` | Standardized `h-1` progress bar. Replaces duplicated bars in TaskManager, NetworkMonitor, BatchProcessor. |

### Icon System

| Component | Props | Description |
|-----------|-------|-------------|
| `Icon` | `name: IconName`, `size?`, `class?`, `style?` | 52 inline SVG icons. Most-imported component (~40 consumers). Pure, no store deps. |

### Data Display

| Component | Props | Stores | Description |
|-----------|-------|--------|-------------|
| `Breadcrumbs` | `segments: {label, href?}[]` | None | Glass pill breadcrumb trail with `/` separators. Currently unused (was used by removed detail pages); retained for potential reuse. |
| `CopyButton` | `text: string` | None | Inline copy-to-clipboard with "Copied!" feedback state. |
| `DiffView` | `original`, `optimized`, `defaultMode?` | None | Unified/side-by-side diff with synchronized scroll. Memoized computation. |
| `MetadataSummaryLine` | `strategy?`, `taskType?`, `complexity?`, `score?`, `compact?` | None | Single-line metadata row composing MetaBadge instances. |
| `Dropdown` | `value`, `options: {value, label, group?}[]`, `label`, `onchange`, `testid?`, `itemContent?: Snippet` | None | bits-ui select with optional grouped options and custom item renderer. |

### Modals & Dialogs

| Component | Props | Stores | Description |
|-----------|-------|--------|-------------|
| `ConfirmModal` | `open` (bindable), `title?`, `message?`, `confirmLabel?`, `cancelLabel?`, `variant?: "danger"\|"warning"`, `onconfirm?`, `oncancel?` | None | bits-ui AlertDialog with danger/warning variants. |
| `MCPInfo` | `open` (bindable) | `providerState`, `windowManager`, `clipboardService` | Interactive MCP reference panel: 19 tools with click-to-copy, SSE endpoint chip, search filter, live connection status, config snippets with copy buttons, Open Terminal footer action. |

### Input

| Component | Props | Stores | Description |
|-----------|-------|--------|-------------|
| `ApiKeyInput` | `provider`, `maskedKey?`, `validating?`, `validationResult?`, `onsave`, `onclear` | None | API key editor with show/hide toggle and validation indicator. |

---

## Individual Components

Single-use components bound to a specific feature area. Grouped by the feature they serve.

### OS Desktop

Desktop metaphor shell composed in `routes/+layout.svelte`.

| Component | Props | Stores | Description |
|-----------|-------|--------|-------------|
| `DesktopSurface` | — | `desktopStore`, `windowManager`, `forgeSession`, `forgeMachine` | Desktop wallpaper + store-driven icon grid with absolute positioning. Handles icon selection, double-click, drag-and-drop with ghost preview, right-click context menu, inline rename flow. Document-level `mouseup`/`mouseleave` listeners end drag even when mouse leaves the surface. Debounced (250ms) window `resize` listener calls `desktopStore.reclampPositions()`. Renders `DesktopContextMenu`. Local `editingIconId` state tracks which icon's label is in edit mode; observes `desktopStore.requestRename` via `$effect`. Rename enabled for all non-system icons (folder + file types). |
| `DesktopIcon` | `id`, `icon`, `label`, `color`, `selected?`, `dragging?`, `editing?`, `renameable?`, `binIndicator?`, `binEmpty?`, `onselect?`, `ondblclick?`, `oncontextmenu?`, `onmousedown?`, `onlabelclick?`, `onrename?` | None | Split icon+label: 40×40 icon graphic button (selection ring, drag opacity) + separate label span/input. Standardized Nautilus interaction: single click selects (`onselect` + `stopPropagation`), double click opens (`ondblclick`), right-click selects then context menus (`onselect` + `oncontextmenu` + `stopPropagation`). Label supports inline rename for non-system icons (guarded by `renameable` prop). Rename input auto-focuses with select-all, commits on Enter/blur, cancels on Escape. Double-commit guard prevents race between keydown and focusout. |
| `DesktopContextMenu` | `open`, `x`, `y`, `actions: ContextAction[]`, `onaction`, `onclose` | None | Right-click context menu with viewport clamping, fly transition, separator dividers, danger styling. z-index 45. Outside-click dismiss uses `bind:this` ref containment check (not querySelector). rAF-deferred bubble-phase listener matches StartMenu/NotificationTray pattern. |
| `DesktopWindow` | `windowId`, `title`, `icon`, `minimizable?`, `onclose?` | `windowManager` | Window chrome: title bar with minimize/maximize/close, z-index stacking. Address bar rendered between title bar and content when breadcrumbs or navigation state exists. Back/forward chevron buttons appear when `windowManager.getNavigation(windowId)` is set. **Snap integration**: Lock guards prevent drag/resize in locked snap groups; lock icon in title bar unsnaps on click; maximize button shows layout picker popover on 300ms hover (100ms grace period); title bar context menu with snap/unsnap/minimize/maximize/close actions. Drag handler calls `computeSnapZone()` on every move for live preview, snaps to zone on drop; when not in a viewport zone, applies magnetic edge snapping via `computeEdgeSnap()`. Resize handler applies `computeResizeEdgeSnap()` for window-to-window magnetic attraction. Timer cleanup on destroy. |
| `DesktopTaskbar` | — | `windowManager`, `desktopStore` | Bottom taskbar: Start button, open window buttons, system tray. |
| `StartMenu` | — | `windowManager`, `historyState`, `projectsState`, `forgeSession`, `forgeMachine`, `optimizationState` | Start menu overlay with quick actions (New Forge, New Project), recent forges (click opens in IDE via `openInIDEFromHistory`), project list (click opens ProjectsWindow via `navigateToProject` + `openProjectsWindow`). |
| `RecycleBinWindow` | — | `desktopStore`, `toastState` | Recycle bin window content using `FileManagerRow` for standardized Nautilus interaction. `selectedId` state tracks selection. Single-click selects, double-click restores, right-click opens context menu (Restore, Delete Permanently). Background click deselects. Toolbar with "Empty Recycle Bin", grid-full warning banner, toast on off-screen restore. Uses `DesktopContextMenu` + two `ConfirmModal` instances. `sourceTypeIcon()` maps 4 source types: `optimization` → bolt, `project`/`folder` → folder, `file` → file-text. |
| `FileManagerView` | `columns`, `sortKey`, `sortOrder`, `onsort`, `itemCount`, `itemLabel`, `isLoading`, `hasMore?`, `onloadmore?`, `emptyIcon?`, `emptyMessage?`, `onbackgroundclick?`, `toolbar?` (Snippet), `rows` (Snippet) | — | Shared file-manager frame: toolbar with count + custom controls, sortable column headers (active column highlighted in neon-cyan with arrow indicator, gap-3 matching row gap), flush row layout (0px gap), scrollable content area with background click handler for deselection, load-more button, empty/loading states. Used by `ProjectsWindow` and `HistoryWindow`. |
| `FileManagerRow` | `onselect?`, `onopen?`, `oncontextmenu?: (e: MouseEvent) => void`, `active?` (boolean), `children` (Snippet), `testId?` | — | ~36px row wrapper with Nautilus-style interaction: single click selects (`onselect`), double click opens (`onopen`), right-click selects + context menu. Active state: `bg-neon-cyan/10`. Clicks `stopPropagation` so `FileManagerView.onbackgroundclick` only fires on empty area. Flush layout (0px row gap, `rounded-sm`). Parent renders cell content as children with widths matching column defs. |
| `ProjectsWindow` | — | `projectsState`, `windowManager`, `forgeSession`, `toastState` | Nautilus-style drill-down project browser with `selectedId` state. **List view**: sortable columns (Name, Prompts, Modified) via `FileManagerView`, search, active/archived filter. Single-click selects row, double-click drills into project prompts view. Right-click selects + opens context menu (Open, Archive/Unarchive, Delete with confirm). **Project view**: shows prompts as `.md` files (file-text icon + `toFilename()` derived name) with version, forge count, modified date. Column header "Name" instead of "Prompt". Double-click opens prompt in IDE via `openPromptInIDE()` (from `$lib/utils/promptOpener.ts`). Right-click opens context menu (Open, Forge, Copy Content, Delete Prompt with confirm). Selection resets on navigate/back/forward. Background click deselects. Back/forward navigation stacks with `WindowNavigation` integration. Consumes `pendingNavigateProjectId` from `projectsState` via `$effect` to allow external code to request navigation. Manages own breadcrumbs (`Desktop / Projects` or `Desktop / Projects / ProjectName`). Uses `fetchProject()` directly to avoid polluting `projectsState.activeProject`. Uses `DesktopContextMenu` + `ConfirmModal`. |
| `HistoryWindow` | — | `historyState`, `windowManager`, `optimizationState`, `forgeSession`, `toastState` | Sortable history browser using `FileManagerView` with `selectedId` state. Columns: Score, Title, Type, Project, Date — all sortable via column headers. Search toolbar. Score badge with color-coded `getScoreBadgeClass`. Load-more pagination. Manages own breadcrumbs. Single-click selects row, double-click opens in IDE via `openInIDEFromHistory()`. Right-click selects + opens context menu (Open in IDE, Re-forge, Iterate, Copy Result, Delete with confirm). Error-status entries show reduced menu (Open in IDE, Delete only). Background click deselects. Uses `DesktopContextMenu` + `ConfirmModal`. |
| `TaskbarWindowButton` | `win: WindowEntry` | `windowManager`, `forgeMachine` | Individual window button in the taskbar. Active click: minimizes persistent windows (`PERSISTENT_WINDOW_IDS`), navigates home for route-driven windows. Pulsing dot for IDE when forge is running. **Snap group indicator**: colored 2px bar at bottom when in a snap group (color-keyed via `getGroupColor()`); hovering highlights all sibling buttons via `hoveredSnapGroupId` state. |
| `SnapPreview` | — | `windowManager` | Translucent zone preview overlay during drag. Reads `windowManager.activeSnapZone`, positioned absolutely with `fade` transition (120ms). z-index 9. |
| `SnapAssist` | — | `windowManager` | Post-snap overlay showing clickable window cards for filling remaining layout zones. Full-viewport scrim, max 4 candidates per zone. Auto-dismisses when no candidates. Reactive viewport via `svelte:window` bindings. z-index 15. |
| `SnapLayoutPicker` | `windowId` | `windowManager` | Popover showing 7 layout thumbnails (64×44px each) in flex-wrap layout with shared hover label at bottom. No per-item labels or browser tooltips. Hovered slot highlighted in neon-cyan. Click assigns window to slot and triggers snap assist for remaining slots. |
| `TaskbarSystemTray` | — | `providerState`, `statsState` | System tray area: compact stats, API/MCP quick links, notifications, health tooltip, clock. |
| `BatchProcessorWindow` | — | `settingsState` | Multi-prompt batch optimization window. Two modes: input (textarea with blank-line or `---` separator parsing, strategy selector from `ALL_STRATEGIES`, max 20 prompts) and progress (per-item status list with `pending`/`running`/`completed`/`error` color coding, overall progress bar, aggregate stats: completed count, error count, avg score). Runs batch via `batchOptimize()` API. Toolbar: Cancel (during run), Clear, Resume/Start, Export JSON (completed results as downloadable blob). |
| `ControlPanelWindow` | — | `settingsState`, `providerState`, `processScheduler`, `windowManager` | System settings window with 4 tabs: Providers (active provider, model, connection status from `providerState.health`), Pipeline (default strategy selector from `ALL_STRATEGIES`, max concurrent forges 1–5 synced to `processScheduler.maxConcurrent`, auto-retry on rate limit toggle), Display (10-color accent swatch grid from `NEON_COLOR_HEX`, animations toggle, "More Display Settings..." cross-link to `DisplaySettingsWindow`), System (backend version, DB/MCP connection status, active process counts, Reset All Settings button). |
| `DisplaySettingsWindow` | — | `settingsState` | Dedicated display settings window with 4 sections: Performance Profile (3 preset cards — Low/Balanced/High — with icon, label, description; active state `border-neon-cyan`; "Custom" indicator when settings don't match a preset), Wallpaper (segmented animation mode control `static`/`subtle`/`dynamic`, opacity range slider 5%–35% with `.cyber-range` styling), Theme (5×2 accent color grid from `NEON_COLOR_HEX`), Visual Effects (UI animations checkbox). All controls write to `settingsState`. Accessible from desktop right-click → "Display Settings...", command palette, and ControlPanel Display tab cross-link. |
| `StrategyWorkshopWindow` | — | `statsState` | Analytics window with 3 tab views: Score Heatmap (strategy x task-type matrix table with color-coded cells from `score_matrix`, per-strategy averages from `score_by_strategy`), Win Rates (per-strategy usage bars with score and confidence percentages from `strategy_distribution`/`confidence_by_strategy`, best strategy by task type from `win_rates`), Combo Analysis (primary+secondary strategy pair effectiveness with avg scores and run counts from `combo_effectiveness`). Empty-state messaging when no analytics data. |
| `TemplateLibraryWindow` | — | `projectsState`, `windowManager`, `clipboardService` | Prompt template browser with search input and category filter dropdown. 10 built-in templates across 6 categories (Engineering, Marketing, Product, UX, Analytics, QA). Grid layout with category badges, truncated preview text. Double-click opens prompt in IDE via dynamic import of `forgeMachine`/`forgeSession` + `windowManager.openIDE()`. Copy button uses `clipboardService.copy()`. Export all as JSON blob download. Footer shows filtered/total count. |
| `TerminalWindow` | — | `commandPalette`, `systemBus`, `processScheduler`, `historyState`, `statsState`, `windowManager` | Interactive command-line terminal with 15 built-in commands: `help`, `stats`, `processes`, `history [n]`, `commands`, `events [n]`, `clear`, `forge "text"`, `forge! "text"`, `tournament`, `chain`, `mcp`, `mcp-log [n]`, `netmon`, `open <window>`, `close <window>`, `version`. Arrow-key command history (50 entries), auto-scroll on output, color-coded lines (`input`/`output`/`error`/`system`). `forge`, `mcp`, and `open` use dynamic imports. Click-to-focus on terminal body. |
| `NetworkMonitorWindow` | — | `mcpActivityFeed`, `windowManager` | Real-time MCP tool call activity monitor with 3 tabs: Live Activity (active tool call cards with tool name color-coded by category, client ID, elapsed time, progress bar, status message), Event Log (table: time, type, tool, message, duration), Connections (MCP server status, session count, event metrics). Status bar: connection indicator, active call count, session count, total events. Footer: MCP server address, buffered event count. Color scheme: Pipeline=cyan, Query=blue, Organize=purple, Projects=green, Destructive=red. |
| `TaskManagerWindow` | — | `processScheduler`, `providerState`, `windowManager`, `optimizationState`, `forgeMachine` | Process monitor with sortable table (PID, Title, Status, Strategy, Progress, Duration). Summary bar: running/queued/completed counts with color dots, LLM provider status. Per-process actions: Cancel (running/queued), Open in IDE (completed), Retry (errored), Dismiss (non-running). Progress column: running shows percentage bar, completed shows score, error shows truncated message. Footer: max concurrent setting, next queued PID. |
| `CommandPaletteUI` | — | `commandPalette` | Floating command palette overlay (z-50) activated by `commandPalette.isOpen`. Fixed position at 15vh from top. Search input with auto-focus on open, fuzzy-filtered results from `commandPalette.filteredCommands`. Arrow key navigation with `selectedIndex` tracking, Enter to execute, Escape to close. Result items show icon, label, category, and keyboard shortcut. Backdrop click to dismiss. Resets selection index on filter change via `$effect`. |
| `NotificationTray` | — | `notificationService` | Dropdown notification panel anchored to a bell button in the taskbar. Unread count badge (max "9+") over the bell icon. Panel (z-50, 272px wide) shows notification list with type-colored icons (`info`/`success`/`warning`/`error`), title, body, relative timestamp, optional action button, and per-item dismiss. Header actions: "Mark all read" (when unread exist), "Clear" (when any exist). Outside-click-to-close via rAF-deferred bubble-phase document listener with `stopPropagation` (prevents cascading overlay dismissals). Escape key closes panel. Deserialized notifications have `actionLabel` cleared (callback can't survive reload). |

### Layout Shell

Composed in `routes/+layout.svelte`.

| Component | Props | Stores | Description |
|-----------|-------|--------|-------------|
| `Header` | `sidebarOpen` (bindable) | None | Sticky glass header with sidebar toggle. Renders `HeaderStats`. |
| `HeaderStats` | `sidebarOpen?` | `statsState` | Wing-formation stats bar (FORGED, AVG, IMP, PROJ, TODAY). Context-aware: shows project name when scoped. CSS grid centering. |
| `Footer` | — | `providerState` | Bottom status bar: health dots (API/DB/MCP/LLM), provider name, version. |
| `Toast` | — | `toastState` | Notification container. Success/error/info variants, auto-dismiss. |

### Sidebar

| Component | Props | Stores | Description |
|-----------|-------|--------|-------------|
| `HistorySidebar` | `open` (bindable) | `historyState`, `sidebarState`, `projectsState`, `forgeMachine`, `windowManager` | Collapsible aside: History/Projects tabs, running forges section, search/filter, load-more pagination. |
| `HistorySearch` | `searchQuery` (bindable), `showClearConfirm` (bindable) | `historyState`, `projectsState` | Search input + sort/filter dropdowns, hide-archived toggle, clear-all confirmation. |
| `HistoryEntry` | `item: HistorySummaryItem` | `optimizationState`, `forgeSession`, `forgeMachine`, `historyState`, `windowManager` | Sidebar card. IDE-aware: `<button>` (loads into IDE) when IDE visible, `<a>` (navigates) when not. Hover overlay: Open in IDE (hidden when IDE visible), Re-forge, Edit, Delete. Delete confirmation bar. |
| `HistoryEmptyState` | `searchQuery?` | None | Empty state messaging for zero history (search vs. initial). |
| `ProjectsSidebar` | — | `projectsState` | Projects list (active/archived toggle), search, new project button. Lazy-loads on first display. |
| `ProjectItem` | `project: ProjectSummary` | `projectsState`, `toastState` | Sidebar card for project. Archive/unarchive/delete with confirmation. Click navigates to detail. |
| `CreateProjectDialog` | `onclose` | `projectsState`, `toastState` | New project form dialog with validation. |

### Forge IDE

The 3-pane IDE overlay (Explorer/Editor/Inspector).

| Component | Props | Stores | Description |
|-----------|-------|--------|-------------|
| `ForgeIDEWorkspace` | — | `forgeSession`, `optimizationState`, `forgeMachine`, `promptAnalysis`, `projectsState`, `tabCoherence` | 3-column layout container. Drives prompt analysis reactively. `onMount` hydration recovery: restores tab result from server on page reload, or falls back to compose if `forgeMachine.mode` is `'review'` without a `forgeResult`. Shown when `windowManager.ideVisible && !forgeMachine.isMinimized`. |
| `ForgeIDEExplorer` | — | `forgeSession`, `projectsState` | Left pane (256px): metadata inputs (title/project/version/tags), context/assets section. |
| `ForgeIDEEditor` | — | `forgeSession`, `optimizationState`, `forgeMachine`, `tabCoherence` | Center pane (flex-1): multi-tab workspace with tab bar, renders `ForgeEditor` per tab. Tab operations (`switchTab`, `closeTab`, `newTab`, `exitIDE`) use `saveActiveTabState()`/`restoreTabState()` from `tabCoherence.ts`. Forging guard blocks tab switching, active-tab close button (`pointer-events-none`), and new tab creation during an active forge. |
| `ForgeIDEInspector` | — | `promptAnalysis`, `forgeSession`, `optimizationState`, `forgeMachine` | Right pane (320px): strategy selector with heuristic recommendations (analyzing spinner, "type more" hint), Analyze Only / Full Optimization buttons, pipeline step inspector, score display, error panel. |
| `ForgeEditor` | `variant?: "collapsed"\|"focus"`, `class?` | `forgeSession`, `optimizationState`, `toastState` | Prompt textarea with slash-command autocomplete (`/strategy`), structure gutter dots, variable chips. Uses `promptParser.ts`. |

### Forge Lifecycle

| Component | Props | Stores | Description |
|-----------|-------|--------|-------------|
| `ForgeMinimizedBar` | — | `forgeMachine`, `windowManager`, `optimizationState` | Slim status bar when IDE minimized. Mode-specific renders: forging (step dots + timer), review (score + strategy), compare (label). |
| `ForgeTaskbar` | — | `forgeMachine`, `optimizationState`, `windowManager` | Dashboard process strip (when IDE hidden + processes exist). Click running → open IDE; click completed → load via `openInIDE()`. |
| `ForgePipelineInline` | — | `optimizationState` | Inline running/completed pipeline visualization during forge. Shows step status dots with timing. |
| `ForgeError` | — | `optimizationState`, `forgeSession` | Error display with retry countdown and optional auto-retry. |

### Forge Review & Compare

| Component | Props | Stores | Description |
|-----------|-------|--------|-------------|
| `ForgeReview` | — | `optimizationState`, `forgeMachine`, `forgeSession` | IDE review panel: score header, dimension bars, optimized/original tabs, strategy reasoning, iteration timeline, actions (Copy/Iterate/Re-forge/Compare). |
| `ForgeCompare` | — | `forgeMachine`, `optimizationState` | Two-column comparison (Slot A vs B), score delta bars, Keep/Back actions. Auto-widens to 560px. Async server fallback with staleness guards and loading/error/empty states. |
| `ForgeCompareActions` | `slotA`, `slotB` | `forgeMachine`, `forgeSession` | Keep A / Keep B / Back action buttons for comparison. Guards against empty optimized text. |
| `ForgeScoreDelta` | `scoresA`, `scoresB` | None | Per-dimension score delta visualization with center-anchored bars and color coding. |
| `ForgeIterationTimeline` | `currentId?`, `onselect?` | `optimizationState` | Horizontal iteration nodes from `resultHistory`. Clickable to load previous results. |
| `ForgeSiblings` | `currentForgeId`, `projectId`, `promptId` | `toastState` | Prev/next navigation for sibling forges within a prompt. Fetches from API on mount. Currently unused (was used by removed `/optimize/[id]` route); retained for future IDE integration. |

### Forge Metadata & Context

| Component | Props | Stores | Description |
|-----------|-------|--------|-------------|
| `ForgeMetadataSection` | `projectListId?`, `compact?` | `forgeSession`, `projectsState` | IDE explorer metadata: title, project selector, tags, version fields. |
| `ForgeContextSection` | `compact?` | `forgeSession`, `projectsState` | IDE explorer codebase context editor with stack template picker. Auto-populates from project profile. |
| `ForgeStrategySection` | — | `forgeSession`, `promptAnalysis` | Strategy override selector + secondary framework picker. |
| `ForgeAnalysisPreview` | — | `optimizationState`, `promptAnalysis` | Quick analysis preview in inspector: task type, complexity, strengths, weaknesses. |
| `ContextProfileEditor` | `value: CodebaseContext`, `onsave`, `readonly?`, `showTemplates?` | None | 9-field context editor with 8 stack templates, dirty detection, save/clear. |
| `ContextSnapshotPanel` | `context: CodebaseContext` | None | Collapsible read-only display of resolved codebase context snapshot attached to an optimization. Shows field count badge, language/framework/test_framework as neon-cyan badges, conventions/patterns/test_patterns as pill lists, code snippets as code blocks, documentation truncated to 500 chars. Used in `ForgeReview`. |

### Dashboard

| Component | Props | Stores | Description |
|-----------|-------|--------|-------------|
| `OnboardingHero` | `onDismiss?` | None | 3-step workflow guide (Write/Forge/Iterate). Dismissible via localStorage. Shows for < 5 total forges. |
| `RecentForges` | — | `historyState`, `sidebarState`, `optimizationState`, `windowManager` | Last 6 forge cards. IDE-aware: `<button>` (loads into IDE) when IDE visible, `<a>` (navigates) when not. Uses `{#snippet cardBody()}`. |
| `RecentProjects` | — | `projectsState` | Up to 4 active project cards. Uses `onMount` (not `$effect`). |
| `StrategyInsights` | `stats: StatsResponse`, `lastPrompt?`, `onStrategySelect?` | None | Strategy Explorer: distribution bars, recommendation engine, expandable details. |

### Result Display

Currently unused (was used by removed `/optimize/[id]` route); retained for potential reuse.

| Component | Props | Stores | Description |
|-----------|-------|--------|-------------|
| `ResultPanel` | `result: OptimizationResultState` | None | Tabbed result viewer: Optimized / Diff View / Original. Composes ResultMetadata, ResultActions, DiffView, CopyButton. |
| `ResultActions` | `result: OptimizationResultState` | `optimizationState`, `forgeSession`, `forgeMachine`, `windowManager`, `projectsState` | Action bar: Copy, Re-forge (with process tracking), Open in IDE (when IDE not visible), Iterate (with full metadata), View Project (opens ProjectsWindow via `navigateToProject`), Export. |
| `ResultMetadata` | `result: OptimizationResultState` | None | Metadata display: title, task type, tags, strategy, timestamp, improvement indicator. |
| `ResultAnalysis` | `result: OptimizationResultState` | None | Analysis breakdown: task type, complexity, strengths, weaknesses lists. |
| `ResultChanges` | `result: OptimizationResultState` | None | Changes-made list and optimization notes. |
| `ScoreDecomposition` | `scores`, `verdict`, `isImprovement`, `pinnedDimension?`, `onHighlight?`, `onClear?`, `onPin?` | None | Interactive score breakdown by dimension. Pinning, highlighting, weighted contribution bars. |
| `PipelineNarrative` | `result: OptimizationResultState` | None | Stage-by-stage result narrative composing NarrativeStage instances. |
| `NarrativeStage` | `title`, `icon`, `status`, `duration?`, `children: Snippet` | None | Collapsible stage card for pipeline narrative. |
| `PipelineStep` | `step: StepState`, `index`, `isLatestActive?` | None | Individual pipeline step display with status icon, timing, expandable data. |

### Provider

| Component | Props | Stores | Description |
|-----------|-------|--------|-------------|
| `ProviderSelector` | — | `providerState` | LLM provider picker: provider cards, model dropdown, API key input. Auto-detects available providers. |

### Brand

| Component | Props | Stores | Description |
|-----------|-------|--------|-------------|
| `BrandLogo` | — | `optimizationState` | Animated PromptForge logo. Reactive modes: idle/forging/complete. SVG with plasma vortex and particle effects. |
| `BrandMark` | `height?`, `width?` | None | Logo wordmark. Currently unused in the app. |

## Patterns

- **Store-driven**: Most individual components read directly from stores rather than accepting props. Shared components are presentational (props-only) for reusability.
- **IDE-native interactions**: All forge/project entry points open results in the IDE via `openInIDEFromHistory()` or `openPromptInIDE()` — no detail page routes exist.
- **bits-ui**: All UI primitives wrap bits-ui headless components (Tooltip, AlertDialog, Select, Tabs, Switch, Separator).
- **Snippets**: `RecentForges` uses `{#snippet}` for shared card body between `<a>`/`<button>` wrappers. `Dropdown` accepts `itemContent` snippet for custom option rendering.
- **Sidebar card pattern**: `HistoryEntry` and `ProjectItem` share `.sidebar-card` base styling with hover overlays and stretched-link click targets.
- **Bindable props**: `Header.sidebarOpen`, `HistorySidebar.open`, `MCPInfo.open`, `ConfirmModal.open` use Svelte 5 `$bindable()` for two-way binding.

## Test Files

| File | Component | Notes |
|------|-----------|-------|
| `HistoryEntry.test.ts` | HistoryEntry | Integration: store mocks, IDE-visible/hidden modes, delete flow, actions |
| `desktopStore.test.ts` | desktopStore | 95+ tests: initial state (3-tier type system: system/folder/file), selection, drag lifecycle (column/row clamping, double-drag guard, sort/trash cancel), context menu (folder/file rename+delete, system blocked), recycle bin CRUD (folder + file sourceTypes), sort (system → folder → file ordering), persistence, reset, rename (folder + file), getMaxRow/getMaxCol, reclampPositions, gridFull, restoreItem off-screen detection, auto-layout (bin placement, column-first fill, no overlaps, grid bounds, sort integration) |
| `ConfirmModal.test.ts` | ConfirmModal | Render + fireEvent, bits-ui dialog |
| `ui/EntryTitle.test.ts` | EntryTitle | Unit: truncation, placeholder fallback |
| `ui/__test__/Passthrough.svelte` | — | Test helper: passthrough component for mocking bits-ui primitives |
