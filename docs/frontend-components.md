# Frontend Components Reference

Complete inventory of all 77 Svelte 5 components (66 in `components/`, 11 in `components/ui/`). Components are organized into **shared** (reusable across the app) and **individual** (single-use, feature-specific) categories.

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
| `DesktopSurface` | — | `desktopStore`, `fsOrchestrator`, `systemBus`, `settingsState` | Desktop wallpaper + store-driven icon grid with absolute positioning. Handles icon selection, double-click, right-click context menu, inline rename flow. Two drag systems: grid-repositioning (mousedown-based, for system/shortcut icons) and HTML5 native drag (for DB-backed folder/prompt icons, encodes `DragPayload` via `DRAG_MIME` with `source: 'desktop'`). Drop target: accepts `DRAG_MIME` on empty surface (move to root) or on folder icons (move into folder), with self-drop and same-location guards. Document-level `mouseup`/`mouseleave` listeners end grid drag. Debounced (250ms) window `resize` listener calls `desktopStore.reclampPositions()`. Renders `DesktopContextMenu`. Local `editingIconId` and `draggingDesktopIconId` state. Subscribes to `fs:created/moved/deleted/renamed` bus events for root content sync. |
| `DesktopIcon` | `id`, `icon`, `label`, `color`, `selected?`, `dragging?`, `editing?`, `renameable?`, `binIndicator?`, `binEmpty?`, `draggable?`, `onselect?`, `ondblclick?`, `oncontextmenu?`, `onmousedown?`, `ondragstart?`, `ondragend?`, `onlabelclick?`, `onrename?` | None | Split icon+label: 40×40 icon graphic button (selection ring, drag opacity) + separate label span/input. When `draggable` is set, outer `<div>` gets HTML5 `draggable` attribute and fires `ondragstart`/`ondragend` (payload encoding done by parent). Standardized Nautilus interaction: single click selects, double click opens, right-click context menus. Label supports inline rename for non-system icons (guarded by `renameable` prop). Rename input auto-focuses with select-all, commits on Enter/blur, cancels on Escape. Double-commit guard prevents race between keydown and focusout. |
| `MoveToDialog` | `open` (bindable), `nodeType: 'project'\|'prompt'\|null`, `nodeId: string\|null`, `batchItems?: Array<{type, id}>`, `onmove?`, `onmovebatch?`, `oncancel?` | `fsOrchestrator` | Folder picker modal for "Move to..." context menu action. Supports single-item and batch moves. Loads root-level folders via `fsOrchestrator.loadChildren(null)`, excludes self/batch folder items. Shows "Desktop" root-level target at top of list (`selectedFolderId = null`). Move button enabled once any target is selected. Batch mode shows "Move N items to..." title. Used in `+layout.svelte` (desktop icons) and `FolderWindow` (folder content). Uses `AlertDialog` from bits-ui. |
| `DesktopContextMenu` | `open`, `x`, `y`, `actions: ContextAction[]`, `onaction`, `onclose` | None | Right-click context menu with viewport clamping, fly transition, separator dividers, danger styling. z-index 45. Outside-click dismiss uses `bind:this` ref containment check (not querySelector). rAF-deferred bubble-phase listener matches StartMenu/NotificationTray pattern. |
| `DesktopWindow` | `windowId`, `title`, `icon`, `minimizable?`, `onclose?` | `windowManager` | Window chrome: title bar with minimize/maximize/close, z-index stacking. Address bar rendered between title bar and content when breadcrumbs or navigation state exists. Back/forward chevron buttons appear when `windowManager.getNavigation(windowId)` is set. **Snap integration**: Lock guards prevent drag/resize in locked snap groups; lock icon in title bar unsnaps on click; maximize button shows layout picker popover on 300ms hover (100ms grace period); title bar context menu with snap/unsnap/minimize/maximize/close actions. Drag handler calls `computeSnapZone()` on every move for live preview, snaps to zone on drop; when not in a viewport zone, applies magnetic edge snapping via `computeEdgeSnap()`. Resize handler applies `computeResizeEdgeSnap()` for window-to-window magnetic attraction. Timer cleanup on destroy. |
| `DesktopTaskbar` | — | `windowManager`, `desktopStore` | Bottom taskbar: Start button, open window buttons, system tray. |
| `StartMenu` | — | `windowManager`, `historyState`, `projectsState`, `forgeSession`, `forgeMachine` | Start menu overlay with quick actions (New Forge, New Project), recent forges (click opens in IDE via `openDocument(createArtifactDescriptor(...))`), project list (click opens ProjectsWindow via `navigateToProject` + `openProjectsWindow`). |
| `RecycleBinWindow` | — | `desktopStore`, `toastState` | Recycle bin window content using `FileManagerRow` for standardized Nautilus interaction. `selectedId` state tracks selection. Single-click selects, double-click restores, right-click opens context menu (Restore, Delete Permanently). Background click deselects. Toolbar with "Empty Recycle Bin", grid-full warning banner, toast on off-screen restore. Uses `DesktopContextMenu` + two `ConfirmModal` instances. `sourceTypeIcon()` maps 4 source types: `optimization` → bolt, `project`/`folder` → folder, `file` → file-text. |
| `FileManagerView` | `columns`, `sortKey`, `sortOrder`, `onsort`, `itemCount`, `itemLabel`, `isLoading`, `hasMore?`, `onloadmore?`, `emptyIcon?`, `emptyMessage?`, `onbackgroundclick?`, `toolbar?` (Snippet), `rows` (Snippet) | — | Shared file-manager frame: toolbar with count + custom controls, sortable column headers (active column highlighted in neon-cyan with arrow indicator, gap-3 matching row gap), flush row layout (0px gap), scrollable content area with background click handler for deselection, load-more button, empty/loading states. Used by `ProjectsWindow` and `HistoryWindow`. |
| `FileManagerRow` | `onselect?`, `onopen?`, `oncontextmenu?: (e: MouseEvent) => void`, `active?` (boolean), `dragPayload?: DragPayload` (from `dragPayload.ts`), `children` (Snippet), `testId?` | — | ~36px row wrapper with Nautilus-style interaction: single click selects (`onselect`), double click opens (`onopen`), right-click selects + context menu. Optional drag-and-drop: when `dragPayload` is provided, the row is `draggable` and encodes the payload as `application/x-promptforge` MIME on dragstart. Active state: `bg-neon-cyan/10`. Clicks `stopPropagation` so `FileManagerView.onbackgroundclick` only fires on empty area. Flush layout (0px row gap, `rounded-sm`). Parent renders cell content as children with widths matching column defs. |
| `ProjectsWindow` | — | `projectsState`, `windowManager`, `forgeSession`, `toastState` | Nautilus-style drill-down project browser with `selectedId` state. **List view**: sortable columns (Name, Prompts, Modified) via `FileManagerView`, search, active/archived filter. Single-click selects row, double-click drills into project prompts view. Right-click selects + opens context menu (Open, Archive/Unarchive, Delete with confirm). **Project view**: shows prompts as `.md` files (file-text icon + `toFilename()` derived name) with version, forge count, modified date. Column header "Name" instead of "Prompt". Double-click opens prompt in IDE via `openDocument(createPromptDescriptor(...))`. Prompt rows have `dragPayload` for drag-and-drop to IDE tab bar. Right-click opens context menu (Open, Forge, Copy Content, Delete Prompt with confirm). Selection resets on navigate/back/forward. Background click deselects. Back/forward navigation stacks with `WindowNavigation` integration. Consumes `pendingNavigateProjectId` from `projectsState` via `$effect` to allow external code to request navigation. Manages own breadcrumbs (`Desktop / Projects` or `Desktop / Projects / ProjectName`). Uses `fetchProject()` directly to avoid polluting `projectsState.activeProject`. Uses `DesktopContextMenu` + `ConfirmModal`. |
| `HistoryWindow` | — | `historyState`, `windowManager`, `optimizationState`, `forgeSession`, `toastState` | Sortable history browser using `FileManagerView` with `selectedId` state. Columns: Score, Title, Type, Project, Date — all sortable via column headers. Search toolbar. Score badge with color-coded `getScoreBadgeClass`. Load-more pagination. Manages own breadcrumbs. Single-click selects row, double-click opens in IDE via `openDocument(createArtifactDescriptor(...))`. Rows have `dragPayload` for drag-and-drop to IDE tab bar. Right-click selects + opens context menu (Open in IDE, Re-forge, Iterate, Copy Result, Delete with confirm). Error-status entries show reduced menu (Open in IDE, Delete only). Background click deselects. Uses `DesktopContextMenu` + `ConfirmModal`. |
| `FolderWindow` | `folderId` | `fsOrchestrator`, `windowManager`, `systemBus` | Hierarchical folder browser rendered inside `DesktopWindow`. Breadcrumb navigation via `fsOrchestrator.getPath()`. Shows folders and prompts with `.md` extension appended to prompt names. Forge count badge on prompts with `forge_count > 0` (neon-purple). Expandable forge children: disclosure chevron on prompt rows, `expandedPrompts: Set<string>` state, fetches forge list on expand. Double-click forge → `openDocument(createArtifactDescriptor(...))`. Drag-and-drop: folder/prompt rows emit `DragPayload` with `source: 'folder-window'`; content area and folder rows accept drops from any `DragSource` (including `'desktop'`) via `DRAG_MIME` → `fsOrchestrator.move()`. Context menu: single-item (Open / Move to... / Delete) and batch (Move N items to... / Delete N items) with `Ctrl/Cmd+click` multi-selection. Local `MoveToDialog` and `ConfirmModal` instances. Subscribes to `fs:created/moved/deleted/renamed` bus events for live reload. |
| `TaskbarWindowButton` | `win: WindowEntry` | `windowManager`, `forgeMachine` | Individual window button in the taskbar. Active click: minimizes persistent windows (`PERSISTENT_WINDOW_IDS`), navigates home for route-driven windows. Pulsing dot for IDE when forge is running. **Snap group indicator**: colored 2px bar at bottom when in a snap group (color-keyed via `getGroupColor()`); hovering highlights all sibling buttons via `hoveredSnapGroupId` state. |
| `SnapPreview` | — | `windowManager` | Translucent zone preview overlay during drag. Reads `windowManager.activeSnapZone`, positioned absolutely with `fade` transition (120ms). z-index 9. |
| `SnapAssist` | — | `windowManager` | Post-snap overlay showing clickable window cards for filling remaining layout zones. Full-viewport scrim, max 4 candidates per zone. Auto-dismisses when no candidates. Reactive viewport via `svelte:window` bindings. z-index 15. |
| `SnapLayoutPicker` | `windowId` | `windowManager` | Popover showing 7 layout thumbnails (64×44px each) in flex-wrap layout with shared hover label at bottom. No per-item labels or browser tooltips. Hovered slot highlighted in neon-cyan. Click assigns window to slot and triggers snap assist for remaining slots. |
| `TaskbarSystemTray` | — | `providerState`, `statsState` | System tray area: compact stats, API/MCP quick links, notifications, health tooltip, clock. |
| `BatchProcessorWindow` | — | `settingsState` | Multi-prompt batch optimization window. Two modes: input (textarea with blank-line or `---` separator parsing, strategy selector from `ALL_STRATEGIES`, max 20 prompts) and progress (per-item status list with `pending`/`running`/`completed`/`error` color coding, overall progress bar, aggregate stats: completed count, error count, avg score). Runs batch via `batchOptimize()` API. Toolbar: Cancel (during run), Clear, Resume/Start, Export JSON (completed results as downloadable blob). |
| `ControlPanelWindow` | — | `settingsState`, `providerState`, `processScheduler`, `windowManager`, `appRegistry` | System settings window with 4 static tabs + dynamic app settings tabs. Static: Providers, Pipeline, Display, System. Dynamic: one tab per app from `appRegistry.appsWithSettings` — lazy-loads settings component via `app.getSettingsComponent()` with cached promise. |
| `DisplaySettingsWindow` | — | `settingsState` | Dedicated display settings window with 4 sections: Performance Profile (3 preset cards — Low/Balanced/High — with icon, label, description; active state `border-neon-cyan`; "Custom" indicator when settings don't match a preset), Wallpaper (segmented animation mode control `static`/`subtle`/`dynamic`, opacity range slider 5%–35% with `.cyber-range` styling), Theme (5×2 accent color grid from `NEON_COLOR_HEX`), Visual Effects (UI animations checkbox). All controls write to `settingsState`. Accessible from desktop right-click → "Display Settings...", command palette, and ControlPanel Display tab cross-link. |
| `StrategyWorkshopWindow` | — | `statsState` | Analytics window with 3 tab views: Score Heatmap (strategy x task-type matrix table with color-coded cells from `score_matrix`, per-strategy averages from `score_by_strategy`), Win Rates (per-strategy usage bars with score and confidence percentages from `strategy_distribution`/`confidence_by_strategy`, best strategy by task type from `win_rates`), Combo Analysis (primary+secondary strategy pair effectiveness with avg scores and run counts from `combo_effectiveness`). Empty-state messaging when no analytics data. |
| `TemplateLibraryWindow` | — | `projectsState`, `windowManager`, `clipboardService` | Prompt template browser with search input and category filter dropdown. 10 built-in templates across 6 categories (Engineering, Marketing, Product, UX, Analytics, QA). Grid layout with category badges, truncated preview text. Double-click opens prompt in IDE via dynamic import of `forgeMachine`/`forgeSession` + `windowManager.openIDE()`. Copy button uses `clipboardService.copy()`. Export all as JSON blob download. Footer shows filtered/total count. |
| `TerminalWindow` | — | `commandPalette`, `systemBus`, `processScheduler`, `historyState`, `statsState`, `windowManager` | Interactive command-line terminal with 15 built-in commands: `help`, `stats`, `processes`, `history [n]`, `commands`, `events [n]`, `clear`, `forge "text"`, `forge! "text"`, `tournament`, `chain`, `mcp`, `mcp-log [n]`, `netmon`, `open <window>`, `close <window>`, `version`. Arrow-key command history (50 entries), auto-scroll on output, color-coded lines (`input`/`output`/`error`/`system`). `forge`, `mcp`, and `open` use dynamic imports. Click-to-focus on terminal body. |
| `NetworkMonitorWindow` | — | `mcpActivityFeed`, `windowManager` | Real-time MCP tool call activity monitor with 3 tabs: Live Activity (active tool call cards with tool name color-coded by category, client ID, elapsed time, progress bar, status message), Event Log (table: time, type, tool, message, duration), Connections (MCP server status, session count, event metrics). Status bar: connection indicator, active call count, session count, total events. Footer: MCP server address, buffered event count. Color scheme: Pipeline=cyan, Query=blue, Organize=purple, Projects=green, Destructive=red. |
| `TaskManagerWindow` | — | `processScheduler`, `providerState`, `mcpActivityFeed`, `appRegistry` | Process monitor with sortable table (PID, Title, Type, Status, Strategy, Progress, Duration). "Type" column shows process type metadata (icon + label) from `appRegistry.allProcessTypes`, falling back to `forge` with `zap` icon. Per-process actions: Cancel (running/queued), Open in IDE (completed, via `openDocument(createArtifactDescriptor(...))`), Retry (errored), Dismiss (non-running). External (MCP) section shows active MCP tool calls. |
| `CommandPaletteUI` | — | `commandPalette` | Floating command palette overlay (z-50) activated by `commandPalette.isOpen`. Fixed position at 15vh from top. Search input with auto-focus on open, fuzzy-filtered results from `commandPalette.filteredCommands`. Arrow key navigation with `selectedIndex` tracking, Enter to execute, Escape to close. Result items show icon, label, category, and keyboard shortcut. Backdrop click to dismiss. Resets selection index on filter change via `$effect`. |
| `NotificationTray` | — | `notificationService` | Dropdown notification panel anchored to a bell button in the taskbar. Unread count badge (max "9+") over the bell icon. Panel (z-50, 272px wide) shows notification list with type-colored icons (`info`/`success`/`warning`/`error`), title, body, relative timestamp, optional action button, and per-item dismiss. Header actions: "Mark all read" (when unread exist), "Clear" (when any exist). Outside-click-to-close via rAF-deferred bubble-phase document listener with `stopPropagation` (prevents cascading overlay dismissals). Escape key closes panel. Deserialized notifications have `actionLabel` cleared (callback can't survive reload). |
| `AppManagerWindow` | — | `systemBus`, `appManagerClient`, `auditClient` | Kernel app management window. Grid of installed apps with icon, name, version, status badge (ENABLED/DISABLED/ERROR/DISCOVERED/INSTALLED with color mapping), service satisfaction indicator. Expandable detail per app: resource usage vs. quota with color-coded progress bars (green/yellow/red). Enable/disable toggle buttons with loading state. Live-updates via bus events (`kernel:app_enabled`, `kernel:app_disabled`, `kernel:audit_logged`). |
| `AuditLogWindow` | — | `systemBus`, `auditClient`, `appManagerClient` | Kernel audit log viewer. Table with columns: Timestamp (relative: "just now", "5m ago"), App (dynamic dropdown from `fetchApps()` with static fallback), Action (color-coded: 18 action types — optimize/analyze/strategy/validate=cyan, create=purple, update=yellow, delete/bulk_delete/clear_all/disconnect=red, archive/cancel=orange, unarchive=teal, move/reorder=blue), Resource type, ID (truncated with full UUID `title` tooltip). Expandable detail rows: click any row to toggle formatted key-value `entry.details` below it. Live indicator: pulsing green dot next to Refresh when bus bridge connected. Pagination with prev/next buttons. Live-updates via `kernel:audit_logged` bus event. |
| `ExtensionSlot` | `slotId: string`, `context?: Record<string, unknown>` | `appRegistry` | Kernel extension point renderer. Iterates `appRegistry.getExtensions(slotId)` sorted by priority. Lazy-loads guest app components via `ext.loadComponent()` with `{#await}` blocks. Context props spread to loaded components. Error handling renders red error text. Used in `ForgeReview` with slot `promptforge:review-actions`. |

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
| `ForgeIDEEditor` | — | `forgeSession`, `optimizationState`, `forgeMachine`, `tabCoherence` | Center pane (flex-1): multi-tab workspace with tab bar, renders `ForgeEditor` per tab. Document-aware tab icons: cyan `file-text` for prompts, purple `zap` for artifacts, gray `file-text` for untitled tabs (via `tabIconName()`/`tabIconColor()`). Tab bar is a drop target for `DragPayload` — accepts drops from HistoryWindow and ProjectsWindow rows. Tab operations (`switchTab`, `closeTab`, `newTab`, `exitIDE`) use `saveActiveTabState()`/`restoreTabState()` from `tabCoherence.ts`. Forging guard blocks tab switching, active-tab close button (`pointer-events-none`), and new tab creation during an active forge. |
| `ForgeIDEInspector` | — | `promptAnalysis`, `forgeSession`, `optimizationState`, `forgeMachine`, `windowManager` | Right pane (320px): strategy selector with heuristic recommendations (analyzing spinner, "type more" hint), Analyze Only / Full Optimization buttons, pipeline step inspector, score display, error panel. Full Optimization delegates to `optimizationState.startOptimization()` which internally spawns a process via `processScheduler`. |
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
| `ForgeContents` | `result: OptimizationResultState` | None | Collapsible sub-artifact accordion in IDE review mode. 3 virtual files: `analysis.scan` (task type, complexity, strengths, weaknesses, changes made), `scores.val` (5 dimension score bars + overall + verdict + improvement indicator), `strategy.strat` (strategy name, confidence %, secondary frameworks, reasoning). Each row has extension-colored icon and filename with extension. Chevron toggle expands inline content. Dynamic file count label. |
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

### App: TextForge (`apps/textforge/`)

| Component | Props | Stores | Description |
|-----------|-------|--------|-------------|
| `TextForgeWindow` | — | `appSettings`, `processScheduler`, `systemBus` | Main transform UI. Header bar with orange accent, 7 transform type buttons (summarize/expand/rewrite/simplify/translate/extract_keywords/fix_grammar), conditional tone/language selectors, split input/output panels. Spawns process with `processType: 'transform'`. Calls `POST /api/apps/textforge/transform`. Loads default transform from app settings. |
| `TextForgeHistoryWindow` | — | — | List+detail view of past transforms. Left panel: scrollable transform list with type-colored badges and date. Right panel: full input/output display with delete action. Calls `GET /api/apps/textforge/transforms` and `GET/DELETE .../transforms/{id}`. |
| `TextForgeSettings` | — | `appSettings` | Settings panel for ControlPanel dynamic tab. Controls: default transform type selector, output format (plain/markdown/html), preserve formatting toggle. Uses `appSettings.load/save('textforge')`. |

### App: Hello World (`apps/hello_world/`)

| Component | Props | Stores | Description |
|-----------|-------|--------|-------------|
| `HelloWorldWindow` | — | — | Minimal example app with green accent header, greeting display, name input with Enter submit, fetch from `GET /api/apps/hello-world/greet`. Brand-guideline styled. |

## Patterns

- **Store-driven**: Most individual components read directly from stores rather than accepting props. Shared components are presentational (props-only) for reusability.
- **IDE-native interactions**: All forge/project entry points open results in the IDE via `openDocument()` from `documentOpener.ts` — no detail page routes exist. `PromptDescriptor` for project prompts, `ArtifactDescriptor` for forge results. Legacy `openInIDEFromHistory()` and `openPromptInIDE()` still exist but the preferred path is `openDocument()`.
- **bits-ui**: All UI primitives wrap bits-ui headless components (Tooltip, AlertDialog, Select, Tabs, Switch, Separator).
- **Snippets**: `RecentForges` uses `{#snippet}` for shared card body between `<a>`/`<button>` wrappers. `Dropdown` accepts `itemContent` snippet for custom option rendering.
- **Sidebar card pattern**: `HistoryEntry` and `ProjectItem` share `.sidebar-card` base styling with hover overlays and stretched-link click targets.
- **Bindable props**: `Header.sidebarOpen`, `HistorySidebar.open`, `MCPInfo.open`, `ConfirmModal.open` use Svelte 5 `$bindable()` for two-way binding.

## Test Files

| File | Component | Notes |
|------|-----------|-------|
| `HistoryEntry.test.ts` | HistoryEntry | Integration: store mocks, IDE-visible/hidden modes, delete flow, actions |
| `desktopStore.test.ts` | desktopStore | 95+ tests: initial state (4-tier type system: system/folder/file/prompt with `.app`/`.lnk`/`.md` extensions), selection, drag lifecycle (column/row clamping, double-drag guard, sort/trash cancel), context menu (folder/file rename+delete, system blocked), recycle bin CRUD (folder + file sourceTypes), sort (system → folder → shortcut → file/prompt ordering), persistence, reset, rename (folder + file), getMaxRow/getMaxCol, reclampPositions, gridFull, restoreItem off-screen detection, auto-layout (bin placement, column-first fill, no overlaps, grid bounds, sort integration), DB prompt sync, DB folder sync |
| `ConfirmModal.test.ts` | ConfirmModal | Render + fireEvent, bits-ui dialog |
| `ui/EntryTitle.test.ts` | EntryTitle | Unit: truncation, placeholder fallback |
| `utils/fileDescriptor.test.ts` | fileDescriptor | Factory helpers, type guards, edge cases |
| `utils/dragPayload.test.ts` | dragPayload | Encode/decode round-trips, invalid input handling |
| `utils/fileTypes.test.ts` | fileTypes | Extension metadata, artifact kinds, `ARTIFACT_EXTENSION_MAP`, `toForgeFilename()`, `toSubArtifactFilename()`, `TYPE_SORT_ORDER` |
| `utils/documentOpener.test.ts` | documentOpener | Prompt/artifact/sub-artifact/template opening paths, desktop prompt routing, error toasts, context passing |
| `ui/__test__/Passthrough.svelte` | — | Test helper: passthrough component for mocking bits-ui primitives |
| `apps/textforge/index.test.ts` | TextForgeApp | 12 tests: manifest fields, command registration, init/destroy lifecycle, component/settings loading |
| `kernel/services/appSettings.test.ts` | appSettings | 3 tests: exports, get unknown app, isLoading default |
