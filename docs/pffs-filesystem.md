# PromptForge File System (PFFS)

The PromptForge File System is the type system, document hierarchy, and routing layer that gives every entity in PromptForge — prompts, forge results, sub-artifacts, desktop icons, folders — a clear type identity, file extension, and behavioral contract. It spans backend (DB schema, REST endpoints) through frontend (stores, descriptors, components).

## Type System

### File Extensions

8 registered extensions in `frontend/src/lib/utils/fileTypes.ts`:

| Extension | Label | Icon | Color | Editable | Versionable | Purpose |
|-----------|-------|------|-------|----------|-------------|---------|
| `.md` | Markdown Prompt | `file-text` | cyan | yes | yes | User-authored prompt |
| `.forge` | Forge Result | `zap` | purple | no | no | Complete optimization result |
| `.scan` | Forge Analysis | `search` | green | no | no | Sub-artifact: task type, complexity, strengths, weaknesses |
| `.val` | Forge Scores | `activity` | yellow | no | no | Sub-artifact: 5 dimension scores + verdict |
| `.strat` | Forge Strategy | `sliders` | indigo | no | no | Sub-artifact: strategy name, reasoning, confidence |
| `.tmpl` | Prompt Template | `file-code` | teal | no | no | Reusable template (future) |
| `.app` | Application | `monitor` | cyan | no | no | System application (internal, not shown in label) |
| `.lnk` | Shortcut | `link` | blue | no | no | Link with preset prompt text |

### Artifact Kinds

4 artifact kinds map to extensions via `ARTIFACT_EXTENSION_MAP`:

| Kind | Extension | Label | Purpose |
|------|-----------|-------|---------|
| `forge-result` | `.forge` | Forge Result | Complete optimization |
| `forge-analysis` | `.scan` | Analysis | Virtual extract: task type, complexity, weaknesses, strengths, changes |
| `forge-scores` | `.val` | Scores | Virtual extract: 5 dimension scores, overall, verdict, improvement |
| `forge-strategy` | `.strat` | Strategy | Virtual extract: strategy, reasoning, confidence, secondary frameworks |

### Sort Order

`TYPE_SORT_ORDER` controls desktop icon ordering:

| Type | Weight | Examples |
|------|--------|---------|
| `system` | 0 | Forge IDE, Recycle Bin |
| `folder` | 1 | Projects, History, DB folders |
| `shortcut` | 2 | Code Review.lnk |
| `file` / `prompt` | 3 | Desktop prompts (.md) |

### Filename Helpers

| Function | Example Input → Output |
|----------|----------------------|
| `toFilename(content, title?)` | `"Review this code carefully"` → `"Review this code carefully.md"` |
| `toArtifactName(title?, score?)` | `null, 0.8` → `"Forge Result (8/10)"` |
| `toForgeFilename(title?, score?, version?)` | `"My Prompt", 0.9, "v2"` → `"My Prompt v2.forge"` |
| `toSubArtifactFilename(kind)` | `'forge-analysis'` → `"analysis.scan"` |

---

## Document Descriptors

Discriminated union in `frontend/src/lib/utils/fileDescriptor.ts`. Every document in the IDE carries a descriptor that determines its icon, color, open behavior, and tab identity.

### Descriptor Types

```
FileDescriptor = PromptDescriptor | ArtifactDescriptor | SubArtifactDescriptor | TemplateDescriptor
NodeDescriptor = FileDescriptor | FolderDescriptor
```

| Kind | Key Fields | Opens As |
|------|------------|----------|
| `prompt` | `id`, `projectId` (empty = desktop), `name`, `extension` | IDE compose mode |
| `artifact` | `id`, `artifactKind`, `name`, `sourcePromptId?`, `sourceProjectId?` | IDE review mode |
| `sub-artifact` | `id`, `artifactKind`, `name`, `parentForgeId`, `extension` | IDE review mode (parent forge) |
| `template` | `id`, `name`, `extension`, `category` | IDE compose (future) |
| `folder` | `id`, `name`, `parentId?`, `depth` | Folder window |

### Factories & Guards

| Function | Purpose |
|----------|---------|
| `createPromptDescriptor(id, projectId, name, ext?)` | Default extension `.md` |
| `createArtifactDescriptor(id, name, opts?)` | Default kind `forge-result` |
| `createSubArtifactDescriptor(parentForgeId, kind, name?)` | Auto-derives canonical name and extension |
| `createFolderDescriptor(id, name, parentId?, depth?)` | For drag-drop and navigation |
| `isPromptDescriptor(d)` | Type guard |
| `isArtifactDescriptor(d)` | Type guard |
| `isSubArtifactDescriptor(d)` | Type guard |
| `isFolderDescriptor(d)` | Type guard |

---

## Document Routing

Single entry point in `frontend/src/lib/utils/documentOpener.ts`:

```
openDocument(descriptor: NodeDescriptor) → void
```

### Routing Table

| Descriptor Kind | Handler | Behavior |
|-----------------|---------|----------|
| `folder` | — | Opens `FolderWindow` via window manager |
| `prompt` (with projectId) | `openPrompt()` | Fetches project → finds prompt → compose or review (if forges exist) |
| `prompt` (empty projectId) | `openDesktopPrompt()` | Fetches via `GET /api/apps/promptforge/fs/prompt/{id}` → compose mode |
| `artifact` | `openArtifact()` → `openForgeResult()` | Fetches optimization → review mode |
| `sub-artifact` | `openSubArtifact()` → `openForgeResult()` | Fetches parent optimization → review mode |
| `template` | — | Not yet implemented (placeholder) |

`openForgeResult()` is a shared helper used by both `openArtifact` and `openSubArtifact` — fetches the optimization, maps to result state, loads into the IDE, attaches the descriptor to the tab, and enters review mode.

---

## Desktop Hierarchy

```
Desktop/
├── Forge IDE                  ← system (.app, label clean)
├── Projects                   ← system (.app)
├── History                    ← system (.app)
├── Control Panel              ← system (.app)
├── Code Review.lnk            ← shortcut (extension visible)
├── Marketing Email.lnk        ← shortcut
├── My Loose Prompt.md         ← desktop prompt (project_id=null)
├── My Project/                ← folder (DB project)
│   ├── Review Code.md         ← prompt
│   │   ├── v1.forge           ← forge result (expandable in FolderWindow)
│   │   └── v2.forge           ← retry
│   ├── API Design.md
│   └── Docs/                  ← sub-folder
└── Recycle Bin                ← system (bottom-left)
```

Within a `.forge` result in the IDE, sub-artifacts are browsable via inline accordion (`ForgeContents`):

```
Review Code v1.forge
├── analysis.scan    ← task type, complexity, weaknesses, strengths
├── scores.val       ← 5 dimension scores + verdict
└── strategy.strat   ← strategy name, reasoning, confidence
```

### Desktop Icon Types

Desktop store (`desktopStore.svelte.ts`) has a 4-tier `IconType` hierarchy:

| IconType | ID Pattern | Extension | Label Shows Extension |
|----------|------------|-----------|----------------------|
| `system` | `sys-*` | `.app` | No |
| `folder` | `db-folder-{uuid}` | — | No |
| `file` | `shortcut-*` | `.lnk` | Yes |
| `prompt` | `db-prompt-{uuid}` | `.md` | Yes |

### Desktop ↔ Filesystem Sync

- `syncDbFolders(folders)` — mirrors root-level DB folders as desktop icons
- `syncDbPrompts(prompts)` — mirrors root-level DB prompts (project_id=null) as desktop icons
- `DesktopSurface.svelte` calls both on mount and on `fs:created`/`fs:moved`/`fs:deleted`/`fs:renamed` bus events

---

## Filesystem Orchestrator

Central state manager in `frontend/src/lib/stores/filesystemOrchestrator.svelte.ts`. All filesystem API calls go through this store.

### Queries

| Method | Return | Purpose |
|--------|--------|---------|
| `getChildren(parentId)` | `FsNode[]` | Cached children (empty if not loaded) |
| `loadChildren(parentId)` | `FsNode[]` | Fetch + cache from server |
| `getPath(projectId)` | `PathSegment[]` | Breadcrumb path (cached) |
| `loadTree(rootId?)` | `FsNode[]` | Recursive folder tree |
| `isLoading(parentId)` | `boolean` | Loading state |

### Mutations

| Method | Return | Bus Event | Purpose |
|--------|--------|-----------|---------|
| `createFolder(name, parentId)` | `FsNode?` | `fs:created` | Create folder, invalidate cache |
| `move(type, id, newParentId)` | `boolean` | `fs:moved` | Move folder or prompt |
| `renameFolder(id, newName)` | `boolean` | `fs:renamed` | Rename folder |
| `deleteFolder(id)` | `boolean` | `fs:deleted` | Delete folder (cascade) |
| `deletePrompt(id)` | `boolean` | `fs:deleted` | Delete prompt (cascade) |

### Drop Validation

`validateDrop(descriptor, targetId, targetDepth)` enforces:
- No self-drop (folder into itself)
- Depth limit (`MAX_FOLDER_DEPTH = 8`)

### Caching

- `_childrenCache: Map<string, FsNode[]>` — keyed by parent ID (root = `__root__`)
- `_pathCache: Map<string, PathSegment[]>` — keyed by project ID
- `invalidate(parentId)` / `invalidateAll()` for cache management
- Mutations auto-invalidate affected parents

---

## Backend API

### Endpoints

All in `backend/apps/promptforge/routers/filesystem.py`:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/apps/promptforge/fs/children?parent_id={id\|null}` | List folder contents (folders + prompts) + breadcrumbs |
| GET | `/api/apps/promptforge/fs/tree?root_id={id\|null}` | Recursive folder tree (folders only) |
| GET | `/api/apps/promptforge/fs/path/{project_id}` | Ancestor breadcrumb path |
| GET | `/api/apps/promptforge/fs/prompt/{prompt_id}` | Single prompt by ID (any prompt, incl. desktop) |
| DELETE | `/api/apps/promptforge/fs/prompt/{prompt_id}` | Delete prompt + cascade optimizations |
| POST | `/api/apps/promptforge/fs/move` | Move folder or prompt to new parent |

### Schemas

In `backend/apps/promptforge/schemas/filesystem.py`:

```python
FsNode:
  id: str
  name: str
  type: "folder" | "prompt"
  parent_id: str | None       # null = root/desktop
  depth: int                   # 0 = root
  content: str | None          # prompts only
  version: int | None          # prompts only
  forge_count: int | None      # prompts only (batch-counted)

PathSegment:
  id: str
  name: str

MoveRequest:
  type: "project" | "prompt"
  id: str
  new_parent_id: str | None    # null = move to root/desktop
```

### Repository Layer

Key methods in `backend/apps/promptforge/repositories/project.py`:

| Method | Purpose |
|--------|---------|
| `get_children(parent_id)` | Direct child folders + prompts |
| `get_subtree(root_id)` | Recursive CTE query for folder tree |
| `get_path(project_id)` | Recursive CTE query for breadcrumb chain |
| `move_project(id, new_parent_id)` | Validates circular refs + depth + name uniqueness; cascade-updates subtree depths |
| `move_prompt(id, new_project_id)` | Updates project_id (null = desktop) |
| `get_prompt_by_id(id)` | Fetch any prompt regardless of project |
| `delete_prompt(prompt)` | Cascade: linked optimizations, unlinked matches, version history |
| `delete_project_data(project)` | Depth-first: child folders, all prompts, sweep legacy optimizations |

### Validation Rules

| Operation | Enforced By | Rules |
|-----------|-------------|-------|
| Create folder | `create_project()` | Name non-empty, parent exists, depth ≤ 8, name unique within parent |
| Move folder | `move_project()` | No self-nesting, no circular refs, subtree fits depth limit, name unique in target |
| Move prompt | `move_prompt()` | Target parent exists (if not null) |
| Delete folder | `delete_project_data()` | Recursive cascade: children → prompts → optimizations |
| Delete prompt | `delete_prompt()` | Cascade: optimizations (linked + content-matched) |

---

## MCP Integration

Two MCP tools in `backend/apps/promptforge/mcp_server.py` support the filesystem:

| Tool | Purpose |
|------|---------|
| `get_children` | List direct children of a folder or root (mirrors `GET /api/apps/promptforge/fs/children`) |
| `move` | Move a folder or prompt to a new parent (mirrors `POST /api/apps/promptforge/fs/move`) |

---

## UI Components

### FolderWindow (`FolderWindow.svelte`)

Hierarchical folder browser rendered inside `DesktopWindow`.

- **Breadcrumbs**: Navigate ancestor chain via `fsOrchestrator.getPath()`
- **Prompt names**: Display with `.md` extension appended
- **Forge count badge**: Shown on prompts with `forge_count > 0` in neon-purple
- **Expandable forges**: Disclosure chevron → lazy-fetches forge list → renders `.forge` rows with score badges
- **Drag & drop**: Move folders/prompts between folders; drop validation via `fsOrchestrator.validateDrop()`
- **Context menu**: Single-item (Open / Move to... / Delete) and batch (Move N items to... / Delete N items) via `Ctrl/Cmd+click` multi-selection
- **Move to... dialog**: Local `MoveToDialog` instance for single-item and batch moves from context menu
- **New Folder**: Inline input with Enter/Escape keyboard handling
- **Live reload**: Subscribes to `fs:created`/`fs:moved`/`fs:deleted`/`fs:renamed` bus events

### ForgeContents (`ForgeContents.svelte`)

Inline accordion in IDE review mode showing 3 sub-artifacts of a forge result.

- **Props**: `result: OptimizationResultState`
- **Sub-artifacts**: `analysis.scan`, `scores.val`, `strategy.strat`
- **Each row**: Extension-colored icon, canonical filename, chevron toggle
- **Expanded content**:
  - `.scan`: task type, complexity, strengths list, weaknesses list, changes made
  - `.val`: 5 dimension score bars with colors, overall score, improvement indicator, verdict
  - `.strat`: strategy name, confidence %, secondary frameworks, reasoning
- **Integrated into**: `ForgeReview.svelte`

### ForgeIDEEditor Tab Icons

Tab icon logic in `ForgeIDEEditor.svelte` routes by descriptor kind:

| Tab Document Kind | Icon Source | Color Source |
|-------------------|------------|--------------|
| `prompt` | `FILE_EXTENSIONS[ext].icon` | `FILE_EXTENSIONS[ext].color` |
| `artifact` or `sub-artifact` | `ARTIFACT_KINDS[kind].icon` | `ARTIFACT_KINDS[kind].color` |
| (none) | `file-text` | default |

### HistoryWindow

Shows `.forge` extension on history items via `toForgeFilename()`.

---

## Tab Coherence

`frontend/src/lib/stores/tabCoherence.ts` handles tab state persistence:

- `saveActiveTabState()`: Writes `forgeResult.id` and machine mode onto the active tab
- `restoreTabState(tab)`: Loads result from cache or server, sets machine mode
- On restore failure: clears `document` field for both `artifact` and `sub-artifact` tabs to prevent stale references

### Session Hydration

`forgeSession._hydrateDocument()` validates persisted tab documents against `FILE_DESCRIPTOR_KINDS` (`['prompt', 'artifact', 'template', 'sub-artifact']`). Unknown kinds are discarded on hydrate.

---

## Data Model

### Projects Table

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID | Primary key |
| `name` | string | Unique within parent |
| `parent_id` | UUID? | Self-FK (null = root level) |
| `depth` | int | 0 = root, max 8 |
| `status` | enum | `active` / `archived` / `deleted` |
| `context_profile` | JSON? | Codebase context for optimizations |

### Prompts Table

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID | Primary key |
| `project_id` | UUID? | FK → projects (null = desktop/unorganized) |
| `content` | text | Prompt text |
| `version` | int | Incremented on edit |
| `order_index` | int | Position within project |

### Optimizations Table (relevant columns)

| Column | Type | Purpose |
|--------|------|---------|
| `prompt_id` | UUID? | FK → prompts (links forge to source prompt) |
| `project` | string? | Legacy project name (MCP compat) |

---

## System Bus Events

| Event | Emitter | Payload | Consumers |
|-------|---------|---------|-----------|
| `fs:created` | fsOrchestrator | `{ node }` | DesktopSurface, FolderWindow |
| `fs:moved` | fsOrchestrator | `{ type, id, newParentId }` | DesktopSurface, FolderWindow |
| `fs:deleted` | fsOrchestrator | `{ id }` | DesktopSurface, FolderWindow |
| `fs:renamed` | fsOrchestrator | `{ id, newName }` | DesktopSurface, FolderWindow |

---

## Drag & Drop

Cross-component drag & drop uses `DragPayload` (`frontend/src/lib/utils/dragPayload.ts`):

```typescript
interface DragPayload {
  descriptor: NodeDescriptor   // What is being dragged
  source: string               // Where it came from
}
```

Custom MIME type: `application/x-promptforge`

| Source | Creates Payload | Accepts Drop |
|--------|----------------|--------------|
| FolderWindow (folder row) | `FolderDescriptor` | Yes (folders accept children from any source) |
| FolderWindow (prompt row) | `PromptDescriptor` | — |
| HistoryWindow (row) | `ArtifactDescriptor` | — |
| ProjectsWindow (prompt row) | `PromptDescriptor` | — |
| IDE tab bar | — | Yes (opens document) |
| Desktop (DB folder icon) | `FolderDescriptor`, source `'desktop'` | Yes (folder icons accept children) |
| Desktop (DB prompt icon) | `PromptDescriptor`, source `'desktop'` | — |
| Desktop (empty surface) | — | Yes (moves to root; no-op for `source: 'desktop'`) |

Guards: self-drop (folder onto itself) is a no-op; desktop→desktop empty space is a no-op. System/shortcut icons use grid-repositioning drag (not HTML5 drag). "Move to..." context menu provides a non-drag alternative — available in both desktop icon context menus and FolderWindow context menus (single and batch). The `MoveToDialog` offers both named folders and a "Desktop" root-level target.
