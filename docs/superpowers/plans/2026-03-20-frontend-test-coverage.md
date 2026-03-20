# Frontend Test Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring SvelteKit frontend from ~0% to ≥90% line coverage using Vitest + @testing-library/svelte.

**Architecture:** Install testing-library dependencies, configure Vitest with jsdom + coverage thresholds, create shared test utilities (mock factories, fetch helpers, store reset), then write tests bottom-up: pure utils → stores → API client → components. Co-located test files next to source.

**Tech Stack:** Vitest 4.x, @testing-library/svelte 5.x, @testing-library/jest-dom, @testing-library/user-event, jsdom, @vitest/coverage-v8

**Spec:** `docs/superpowers/specs/2026-03-20-frontend-test-coverage-design.md`

---

## File Structure

### New files to create

| File | Responsibility |
|------|---------------|
| `src/lib/test-setup.ts` | Global test setup: jest-dom matchers, EventSource mock, clipboard mock, SVG API mocks |
| `src/lib/test-utils.ts` | Shared mock factories, mockFetch helper, re-exports of testing-library |
| `src/lib/utils/formatting.test.ts` | Tier 1: formatting utility tests |
| `src/lib/constants/patterns.test.ts` | Tier 1: domain/score color tests |
| `src/lib/utils/strategies.test.ts` | Tier 1: strategy option transform tests |
| `src/lib/utils/dimensions.test.ts` | Tier 1: dimension/phase label tests |
| `src/lib/stores/toast.svelte.test.ts` | Tier 2: toast queue management tests |
| `src/lib/stores/editor.svelte.test.ts` | Tier 2: tab management + result cache tests |
| `src/lib/stores/preferences.svelte.test.ts` | Tier 2: preferences load/update tests |
| `src/lib/stores/github.svelte.test.ts` | Tier 2: GitHub auth + repo linking tests |
| `src/lib/stores/patterns.svelte.test.ts` | Tier 2: paste detection + suggestion lifecycle tests |
| `src/lib/stores/refinement.svelte.test.ts` | Tier 2: refinement turns + branching tests |
| `src/lib/stores/forge.svelte.test.ts` | Tier 2: forge status machine + SSE handling tests |
| `src/lib/utils/mcp-tooltips.test.ts` | Tier 2: store-dependent tooltip tests |
| `src/lib/api/client.test.ts` | Tier 3: API client + SSE streaming tests |
| `src/lib/api/patterns.test.ts` | Tier 3: pattern API function tests |
| `src/lib/components/shared/Toast.test.ts` | Tier 4a: toast rendering tests |
| `src/lib/components/shared/ScoreCard.test.ts` | Tier 4a: score dimension display tests |
| `src/lib/components/shared/ProviderBadge.test.ts` | Tier 4a: provider badge variant tests |
| `src/lib/components/shared/DiffView.test.ts` | Tier 4a: diff rendering tests |
| `src/lib/components/shared/CommandPalette.test.ts` | Tier 4a: keyboard + action tests |
| `src/lib/components/shared/MarkdownRenderer.test.ts` | Tier 4a: markdown rendering tests |
| `src/lib/components/editor/PatternSuggestion.test.ts` | Tier 4a: suggestion apply/skip tests |
| `src/lib/components/editor/PromptEdit.test.ts` | Tier 4a: prompt input + forge trigger tests |
| `src/lib/components/refinement/RefinementInput.test.ts` | Tier 4a: submit + keyboard tests |
| `src/lib/components/refinement/SuggestionChips.test.ts` | Tier 4a: chip click tests |
| `src/lib/components/refinement/ScoreSparkline.test.ts` | Tier 4a: SVG polyline tests |
| `src/lib/components/refinement/BranchSwitcher.test.ts` | Tier 4a: branch navigation tests |
| `src/lib/components/layout/ActivityBar.test.ts` | Tier 4a: activity selection tests |
| `src/lib/components/layout/StatusBar.test.ts` | Tier 4a: status display tests |
| `src/lib/components/layout/EditorGroups.test.ts` | Tier 4a: tab bar + content switching tests |
| `src/lib/components/layout/Navigator.test.ts` | Tier 4b: history, preferences, API key tests |
| `src/lib/components/layout/Inspector.test.ts` | Tier 4b: family detail + rename tests |
| `src/lib/components/layout/PatternNavigator.test.ts` | Tier 4b: paginated family list + search tests |
| `src/lib/components/shared/Logo.test.ts` | Tier 4c: smoke test |
| `src/lib/components/editor/ForgeArtifact.test.ts` | Tier 4c: smoke test |
| `src/lib/components/editor/PassthroughView.test.ts` | Tier 4c: smoke test |
| `src/lib/components/refinement/RefinementTimeline.test.ts` | Tier 4c: smoke test |
| `src/lib/components/refinement/RefinementTurnCard.test.ts` | Tier 4c: smoke test |
| `src/lib/components/patterns/RadialMindmap.test.ts` | Tier 4c: smoke test (D3 mocked) |
| `src/lib/components/landing/Navbar.test.ts` | Tier 4c: smoke test |
| `src/lib/components/landing/Footer.test.ts` | Tier 4c: smoke test |

### Files to modify

| File | Change |
|------|--------|
| `vite.config.ts` | Add `test` block with jsdom, coverage, setup files |
| `package.json` | Add @testing-library/* devDependencies |
| Each store `.svelte.ts` file | Add `_reset()` method for test isolation |

---

### Task 1: Install Dependencies and Configure Vitest

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`

- [ ] **Step 1: Install test dependencies**

```bash
cd frontend && npm install -D @testing-library/svelte @testing-library/jest-dom @testing-library/user-event
```

- [ ] **Step 2: Add test block to vite.config.ts**

Read `frontend/vite.config.ts` and add the `test` property to the config object:

```typescript
import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  server: { port: 5199 },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/lib/test-setup.ts'],
    include: ['src/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      include: ['src/lib/**/*.ts', 'src/lib/**/*.svelte'],
      exclude: ['**/*.test.ts', '**/test-*.ts', 'src/lib/content/**'],
      thresholds: { lines: 90 },
    },
  },
});
```

Note: Change the import from `'vite'` to `'vitest/config'` so the `test` property is properly typed.

- [ ] **Step 3: Verify vitest runs with no tests**

```bash
cd frontend && npx vitest run
```

Expected: exits cleanly (the existing `layout.test.ts` should pass).

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts
git commit -m "test: install testing-library and configure vitest coverage"
```

---

### Task 2: Create Shared Test Infrastructure

**Files:**
- Create: `frontend/src/lib/test-setup.ts`
- Create: `frontend/src/lib/test-utils.ts`

- [ ] **Step 1: Create test-setup.ts**

```typescript
import '@testing-library/jest-dom/vitest';

// ── EventSource mock (jsdom doesn't provide it) ──────────────────
class MockEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;

  url: string;
  readyState = MockEventSource.OPEN;
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  private _listeners: Record<string, Array<(ev: MessageEvent) => void>> = {};

  constructor(url: string) {
    this.url = url;
    // Auto-fire open
    queueMicrotask(() => this.onopen?.(new Event('open')));
  }

  addEventListener(type: string, fn: (ev: MessageEvent) => void) {
    (this._listeners[type] ??= []).push(fn);
  }

  removeEventListener(type: string, fn: (ev: MessageEvent) => void) {
    const list = this._listeners[type];
    if (list) this._listeners[type] = list.filter((f) => f !== fn);
  }

  /** Test helper: simulate server sending a named event */
  __simulateEvent(type: string, data: string) {
    const ev = new MessageEvent(type, { data });
    this._listeners[type]?.forEach((fn) => fn(ev));
  }

  /** Test helper: simulate error */
  __simulateError() {
    this.readyState = MockEventSource.CLOSED;
    this.onerror?.(new Event('error'));
  }

  close() {
    this.readyState = MockEventSource.CLOSED;
  }
}

Object.assign(globalThis, { EventSource: MockEventSource });

// ── Clipboard mock ───────────────────────────────────────────────
if (!navigator.clipboard) {
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
    writable: true,
  });
} else {
  vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue(undefined);
}

// ── SVG API mocks (for D3 components in jsdom) ──────────────────
if (typeof SVGElement !== 'undefined') {
  SVGElement.prototype.getBBox = () => ({ x: 0, y: 0, width: 100, height: 20 }) as DOMRect;
  SVGElement.prototype.getComputedTextLength = () => 50;
}
```

- [ ] **Step 2: Create test-utils.ts**

```typescript
import { render, screen, cleanup, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';

export { render, screen, cleanup, within, userEvent };

// ── Mock response factories ──────────────────────────────────────

export function mockHealthResponse(overrides: Record<string, unknown> = {}) {
  return {
    status: 'ok',
    version: '0.2.0',
    provider: 'claude-cli',
    score_health: { last_n_mean: 7.5, last_n_stddev: 0.8, count: 10, clustering_warning: false },
    avg_duration_ms: 3200,
    phase_durations: { analyzing: 800, optimizing: 1800, scoring: 600 },
    recent_errors: { last_hour: 0, last_24h: 2 },
    sampling_capable: null,
    mcp_disconnected: false,
    available_tiers: ['internal', 'passthrough'],
    ...overrides,
  };
}

export function mockDimensionScores(overrides: Record<string, number> = {}) {
  return {
    clarity: 7.5,
    specificity: 8.0,
    structure: 7.0,
    faithfulness: 9.0,
    conciseness: 6.5,
    ...overrides,
  };
}

export function mockOptimizationResult(overrides: Record<string, unknown> = {}) {
  return {
    id: 'opt-1',
    trace_id: 'trace-1',
    raw_prompt: 'Write a hello world',
    optimized_prompt: 'Craft a concise hello world program',
    task_type: 'coding',
    strategy_used: 'chain-of-thought',
    changes_summary: 'Added specificity',
    scores: mockDimensionScores(),
    original_scores: mockDimensionScores({ clarity: 5.0, specificity: 4.5 }),
    score_deltas: { clarity: 2.5, specificity: 3.5, structure: 0, faithfulness: 0, conciseness: 0 },
    overall_score: 7.6,
    provider: 'claude-cli',
    scoring_mode: 'hybrid',
    duration_ms: 3200,
    status: 'complete',
    created_at: '2026-03-20T12:00:00Z',
    model_used: 'claude-sonnet-4-6',
    context_sources: null,
    intent_label: 'Hello world program',
    domain: 'backend',
    family_id: null,
    ...overrides,
  };
}

export function mockHistoryItem(overrides: Record<string, unknown> = {}) {
  return {
    id: 'opt-1',
    trace_id: 'trace-1',
    created_at: '2026-03-20T12:00:00Z',
    task_type: 'coding',
    strategy_used: 'chain-of-thought',
    overall_score: 7.6,
    status: 'complete',
    duration_ms: 3200,
    provider: 'claude-cli',
    raw_prompt: 'Write a hello world',
    optimized_prompt: 'Craft a concise hello world program',
    model_used: 'claude-sonnet-4-6',
    scoring_mode: 'hybrid',
    intent_label: 'Hello world program',
    domain: 'backend',
    family_id: null,
    ...overrides,
  };
}

export function mockPatternFamily(overrides: Record<string, unknown> = {}) {
  return {
    id: 'fam-1',
    intent_label: 'API endpoint patterns',
    domain: 'backend',
    task_type: 'coding',
    usage_count: 5,
    member_count: 3,
    avg_score: 7.8,
    created_at: '2026-03-15T10:00:00Z',
    ...overrides,
  };
}

export function mockMetaPattern(overrides: Record<string, unknown> = {}) {
  return {
    id: 'mp-1',
    pattern_text: 'Include error handling for edge cases',
    source_count: 3,
    ...overrides,
  };
}

export function mockPatternMatch(overrides: Record<string, unknown> = {}) {
  return {
    family: mockPatternFamily(),
    meta_patterns: [mockMetaPattern()],
    similarity: 0.85,
    ...overrides,
  };
}

export function mockRefinementTurn(overrides: Record<string, unknown> = {}) {
  return {
    id: 'turn-1',
    optimization_id: 'opt-1',
    version: 1,
    branch_id: 'branch-main',
    parent_version: null,
    refinement_request: 'Make it more concise',
    prompt: 'Refined prompt text',
    scores: { clarity: 8.0, specificity: 8.5, structure: 7.5, faithfulness: 9.0, conciseness: 7.0 },
    deltas: { clarity: 0.5, specificity: 0.5, structure: 0.5, faithfulness: 0, conciseness: 0.5 },
    deltas_from_original: { clarity: 3.0, specificity: 4.0, structure: 0.5, faithfulness: 0, conciseness: 0.5 },
    strategy_used: 'chain-of-thought',
    suggestions: [{ text: 'Try adding examples', source: 'model' }],
    created_at: '2026-03-20T12:05:00Z',
    ...overrides,
  };
}

export function mockRefinementBranch(overrides: Record<string, unknown> = {}) {
  return {
    id: 'branch-main',
    optimization_id: 'opt-1',
    parent_branch_id: null,
    forked_at_version: null,
    created_at: '2026-03-20T12:00:00Z',
    ...overrides,
  };
}

export function mockStrategyInfo(overrides: Record<string, unknown> = {}) {
  return {
    name: 'chain-of-thought',
    tagline: 'Step-by-step reasoning',
    description: 'Breaks down the task into logical steps',
    ...overrides,
  };
}

// ── Fetch mock helper ────────────────────────────────────────────

type FetchHandler = { match: string | RegExp; response: unknown; status?: number };

/**
 * Set up a mock fetch that matches URL patterns and returns canned responses.
 * Call in beforeEach; automatically restored in afterEach by vitest.
 */
export function mockFetch(handlers: FetchHandler[]) {
  const mock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString();
    for (const h of handlers) {
      const matches = typeof h.match === 'string' ? url.includes(h.match) : h.match.test(url);
      if (matches) {
        return new Response(JSON.stringify(h.response), {
          status: h.status ?? 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
    }
    return new Response('Not Found', { status: 404 });
  });
  vi.stubGlobal('fetch', mock);
  return mock;
}
```

- [ ] **Step 3: Verify test infra loads**

```bash
cd frontend && npx vitest run
```

Expected: existing `layout.test.ts` still passes. Setup file loads without errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/test-setup.ts frontend/src/lib/test-utils.ts
git commit -m "test: add shared test infrastructure (setup, mocks, factories)"
```

---

### Task 3: Add `_reset()` Methods to All Stores

**Files:**
- Modify: `frontend/src/lib/stores/toast.svelte.ts`
- Modify: `frontend/src/lib/stores/editor.svelte.ts`
- Modify: `frontend/src/lib/stores/preferences.svelte.ts`
- Modify: `frontend/src/lib/stores/github.svelte.ts`
- Modify: `frontend/src/lib/stores/patterns.svelte.ts`
- Modify: `frontend/src/lib/stores/refinement.svelte.ts`
- Modify: `frontend/src/lib/stores/forge.svelte.ts`

Add a `_reset()` method to each store class that restores all `$state` fields to their initial values. This is used in `beforeEach` blocks to isolate tests.

- [ ] **Step 1: Add _reset() to ToastStore**

Add to class `ToastStore` in `frontend/src/lib/stores/toast.svelte.ts`:

```typescript
/** @internal Test-only: restore initial state */
_reset() {
  this.toasts = [];
  for (const timer of this._timers.values()) clearTimeout(timer);
  this._timers.clear();
}
```

- [ ] **Step 2: Add _reset() to EditorStore**

Add to class `EditorStore` in `frontend/src/lib/stores/editor.svelte.ts`:

```typescript
/** @internal Test-only: restore initial state */
_reset() {
  this.tabs = [{ id: PROMPT_TAB_ID, title: 'Prompt', type: 'prompt', pinned: true }];
  this.activeTabId = PROMPT_TAB_ID;
  this._resultCache = {};
}
```

- [ ] **Step 3: Add _reset() to PreferencesStore**

Add to class `PreferencesStore` in `frontend/src/lib/stores/preferences.svelte.ts`:

```typescript
/** @internal Test-only: restore initial state */
_reset() {
  this.prefs = structuredClone(DEFAULTS);
  this.loading = false;
  this.error = null;
}
```

Note: `DEFAULTS` is already defined as a module-level constant in the source. The `_reset()` clones it to avoid shared mutation. Actual defaults: `models: { analyzer: 'sonnet', optimizer: 'opus', scorer: 'sonnet' }`, `pipeline: { enable_explore: true, enable_scoring: true, enable_adaptation: true, force_sampling: false, force_passthrough: false }`, `defaults: { strategy: 'auto' }`.

- [ ] **Step 4: Add _reset() to GitHubStore**

Add to class `GitHubStore` in `frontend/src/lib/stores/github.svelte.ts`:

```typescript
/** @internal Test-only: restore initial state */
_reset() {
  this.user = null;
  this.linkedRepo = null;
  this.repos = [];
  this.loading = false;
  this.error = null;
}
```

- [ ] **Step 5: Add _reset() to PatternStore**

Add to class `PatternStore` in `frontend/src/lib/stores/patterns.svelte.ts`:

```typescript
/** @internal Test-only: restore initial state */
_reset() {
  this.suggestion = null;
  this.suggestionVisible = false;
  this.graph = null;
  this.graphLoaded = false;
  this.graphError = null;
  this.selectedFamilyId = null;
  this.familyDetail = null;
  this.familyDetailLoading = false;
  this.familyDetailError = null;
  if (this._debounceTimer) clearTimeout(this._debounceTimer);
  if (this._dismissTimer) clearTimeout(this._dismissTimer);
  this._debounceTimer = null;
  this._dismissTimer = null;
  this._lastLength = 0;
}
```

- [ ] **Step 6: Add _reset() to RefinementStore**

Add to class `RefinementStore` in `frontend/src/lib/stores/refinement.svelte.ts`:

```typescript
/** @internal Test-only: restore initial state */
_reset() {
  this.cancel();
  this.optimizationId = null;
  this.turns = [];
  this.branches = [];
  this.activeBranchId = null;
  this.suggestions = [];
  this.selectedVersion = null;
  this.status = 'idle';
  this.error = null;
}
```

- [ ] **Step 7: Add _reset() to ForgeStore**

Add to class `ForgeStore` in `frontend/src/lib/stores/forge.svelte.ts`:

```typescript
/** @internal Test-only: restore initial state */
_reset() {
  this.cancel();
  this.prompt = '';
  this.strategy = null;
  this.status = 'idle';
  this.result = null;
  this.traceId = null;
  this.error = null;
  this.feedback = null;
  this.currentPhase = null;
  this.previewPrompt = null;
  this.scores = null;
  this.originalScores = null;
  this.scoreDeltas = null;
  this.assembledPrompt = null;
  this.passthroughTraceId = null;
  this.passthroughStrategy = null;
  this.initialSuggestions = [];
  this.appliedPatternIds = null;
  this.familyId = null;
  this.routingDecision = null;
  this.samplingCapable = null;
  this.mcpDisconnected = false;
}
```

- [ ] **Step 8: Run existing tests to verify no regressions**

```bash
cd frontend && npx vitest run
```

Expected: all existing tests pass.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/stores/
git commit -m "test: add _reset() methods to all stores for test isolation"
```

---

### Task 4: Tier 1 — Pure Utility Tests

**Files:**
- Create: `frontend/src/lib/utils/formatting.test.ts`
- Create: `frontend/src/lib/constants/patterns.test.ts`
- Create: `frontend/src/lib/utils/strategies.test.ts`
- Create: `frontend/src/lib/utils/dimensions.test.ts`

- [ ] **Step 1: Write formatting.test.ts**

```typescript
import { describe, it, expect, vi } from 'vitest';
import { formatScore, formatDelta, truncateText, copyToClipboard } from './formatting';

describe('formatScore', () => {
  it('formats a number with 1 decimal by default', () => {
    expect(formatScore(7.56)).toBe('7.6');
  });
  it('formats with custom decimals', () => {
    expect(formatScore(7.567, 2)).toBe('7.57');
  });
  it('returns dash for null', () => {
    expect(formatScore(null)).toBe('--');
  });
  it('returns dash for undefined', () => {
    expect(formatScore(undefined)).toBe('--');
  });
  it('handles zero', () => {
    expect(formatScore(0)).toBe('0.0');
  });
  it('handles 10', () => {
    expect(formatScore(10)).toBe('10.0');
  });
});

describe('formatDelta', () => {
  it('formats positive delta with + prefix', () => {
    expect(formatDelta(2.5)).toMatch(/^\+/);
  });
  it('formats negative delta with - prefix', () => {
    expect(formatDelta(-1.3)).toMatch(/^-/);
  });
  it('formats zero delta', () => {
    const result = formatDelta(0);
    expect(result).toContain('0');
  });
  it('respects custom decimals', () => {
    expect(formatDelta(2.567, 2)).toContain('2.57');
  });
});

describe('truncateText', () => {
  it('returns short text unchanged', () => {
    expect(truncateText('hello', 80)).toBe('hello');
  });
  it('truncates long text with ellipsis', () => {
    const long = 'a'.repeat(100);
    const result = truncateText(long, 80);
    expect(result.length).toBeLessThanOrEqual(83); // 80 + '...'
    expect(result).toContain('...');
  });
  it('uses default maxLen of 80', () => {
    const exactlyAt = 'a'.repeat(80);
    expect(truncateText(exactlyAt)).toBe(exactlyAt);
  });
});

describe('copyToClipboard', () => {
  it('copies text via clipboard API', async () => {
    const result = await copyToClipboard('hello');
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('hello');
    expect(result).toBe(true);
  });
  it('returns false on failure', async () => {
    vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValueOnce(new Error('fail'));
    const result = await copyToClipboard('hello');
    expect(result).toBe(false);
  });
});
```

- [ ] **Step 2: Write patterns.test.ts (constants)**

```typescript
import { describe, it, expect } from 'vitest';
import { DOMAIN_COLORS, domainColor, scoreColor } from './patterns';

describe('DOMAIN_COLORS', () => {
  it('has all 7 domains', () => {
    expect(Object.keys(DOMAIN_COLORS)).toEqual(
      expect.arrayContaining(['backend', 'frontend', 'database', 'security', 'devops', 'fullstack', 'general'])
    );
  });
});

describe('domainColor', () => {
  it('returns color for known domain', () => {
    expect(domainColor('backend')).toBe(DOMAIN_COLORS.backend);
  });
  it('returns general color for unknown domain', () => {
    expect(domainColor('unknown')).toBe(DOMAIN_COLORS.general);
  });
});

describe('scoreColor', () => {
  it('returns correct token for high score', () => {
    const color = scoreColor(9.0);
    expect(typeof color).toBe('string');
    expect(color.length).toBeGreaterThan(0);
  });
  it('returns correct token for low score', () => {
    const color = scoreColor(3.0);
    expect(typeof color).toBe('string');
  });
  it('handles null score', () => {
    const color = scoreColor(null);
    expect(typeof color).toBe('string');
  });
  it('handles boundary values (0, 5, 7, 10)', () => {
    for (const s of [0, 5, 7, 10]) {
      expect(typeof scoreColor(s)).toBe('string');
    }
  });
});
```

- [ ] **Step 3: Write strategies.test.ts**

```typescript
import { describe, it, expect } from 'vitest';
import { strategyListToOptions } from './strategies';

describe('strategyListToOptions', () => {
  it('transforms strategy list and prepends auto', () => {
    const list = [
      { name: 'chain-of-thought', tagline: 'Step-by-step', description: '' },
      { name: 'few-shot', tagline: 'Examples', description: '' },
    ];
    const options = strategyListToOptions(list);
    expect(options[0]).toEqual({ value: '', label: 'auto' });
    expect(options).toHaveLength(3);
    expect(options[1].value).toBe('chain-of-thought');
    expect(options[2].value).toBe('few-shot');
  });

  it('handles empty list', () => {
    const options = strategyListToOptions([]);
    expect(options).toHaveLength(1);
    expect(options[0]).toEqual({ value: '', label: 'auto' });
  });
});
```

- [ ] **Step 4: Write dimensions.test.ts**

```typescript
import { describe, it, expect } from 'vitest';
import { DIMENSION_LABELS, PHASE_LABELS, getPhaseLabel } from './dimensions';

describe('DIMENSION_LABELS', () => {
  it('has all 5 dimensions', () => {
    expect(Object.keys(DIMENSION_LABELS)).toEqual(
      expect.arrayContaining(['clarity', 'specificity', 'structure', 'faithfulness', 'conciseness'])
    );
  });
  it('values are non-empty strings', () => {
    Object.values(DIMENSION_LABELS).forEach((v) => {
      expect(typeof v).toBe('string');
      expect(v.length).toBeGreaterThan(0);
    });
  });
});

describe('PHASE_LABELS', () => {
  it('has labels for known phases', () => {
    expect(PHASE_LABELS).toHaveProperty('analyzing');
    expect(PHASE_LABELS).toHaveProperty('optimizing');
    expect(PHASE_LABELS).toHaveProperty('scoring');
  });
});

describe('getPhaseLabel', () => {
  it('returns label for known phase', () => {
    expect(getPhaseLabel('analyzing')).toBe(PHASE_LABELS.analyzing);
  });
  it('returns null for unknown phase', () => {
    expect(getPhaseLabel('unknown')).toBeNull();
  });
});
```

- [ ] **Step 5: Run all Tier 1 tests**

```bash
cd frontend && npx vitest run src/lib/utils/ src/lib/constants/
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/utils/*.test.ts frontend/src/lib/constants/*.test.ts
git commit -m "test: add Tier 1 pure utility tests (formatting, patterns, strategies, dimensions)"
```

---

### Task 5: Tier 2 — Store Tests (toast, editor, preferences)

**Files:**
- Create: `frontend/src/lib/stores/toast.svelte.test.ts`
- Create: `frontend/src/lib/stores/editor.svelte.test.ts`
- Create: `frontend/src/lib/stores/preferences.svelte.test.ts`

- [ ] **Step 1: Write toast.svelte.test.ts**

```typescript
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { toastStore, addToast } from './toast.svelte';

describe('ToastStore', () => {
  beforeEach(() => {
    toastStore._reset();
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('starts with empty queue', () => {
    expect(toastStore.toasts).toHaveLength(0);
  });

  it('adds a toast with created action', () => {
    toastStore.add('created', 'Item created');
    expect(toastStore.toasts).toHaveLength(1);
    expect(toastStore.toasts[0].message).toBe('Item created');
    expect(toastStore.toasts[0].symbol).toBe('+');
  });

  it('adds a toast with modified action', () => {
    toastStore.add('modified', 'Item modified');
    expect(toastStore.toasts[0].symbol).toBe('~');
  });

  it('adds a toast with deleted action', () => {
    toastStore.add('deleted', 'Item deleted');
    expect(toastStore.toasts[0].symbol).toBe('-');
  });

  it('limits to 3 visible toasts', () => {
    toastStore.add('created', 'First');
    toastStore.add('created', 'Second');
    toastStore.add('created', 'Third');
    toastStore.add('created', 'Fourth');
    expect(toastStore.toasts.length).toBeLessThanOrEqual(3);
  });

  it('auto-dismisses after timeout', () => {
    toastStore.add('created', 'Temporary');
    expect(toastStore.toasts).toHaveLength(1);
    vi.advanceTimersByTime(4000);
    expect(toastStore.toasts).toHaveLength(0);
  });

  it('dismiss removes specific toast', () => {
    toastStore.add('created', 'Stay');
    toastStore.add('created', 'Go');
    const goId = toastStore.toasts[1].id;
    toastStore.dismiss(goId);
    expect(toastStore.toasts).toHaveLength(1);
    expect(toastStore.toasts[0].message).toBe('Stay');
  });

  it('addToast convenience function works', () => {
    addToast('created', 'Via helper');
    expect(toastStore.toasts).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Write editor.svelte.test.ts**

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { editorStore, PROMPT_TAB_ID } from './editor.svelte';
import { mockOptimizationResult } from '../test-utils';

describe('EditorStore', () => {
  beforeEach(() => {
    editorStore._reset();
  });

  it('starts with prompt tab active', () => {
    expect(editorStore.tabs).toHaveLength(1);
    expect(editorStore.tabs[0].id).toBe(PROMPT_TAB_ID);
    expect(editorStore.activeTabId).toBe(PROMPT_TAB_ID);
  });

  it('activeTab returns the current tab', () => {
    expect(editorStore.activeTab?.id).toBe(PROMPT_TAB_ID);
  });

  describe('openTab', () => {
    it('adds a new tab and activates it', () => {
      editorStore.openTab({ id: 'result-1', title: 'Result', type: 'result', optimizationId: 'opt-1' });
      expect(editorStore.tabs).toHaveLength(2);
      expect(editorStore.activeTabId).toBe('result-1');
    });

    it('activates existing tab instead of duplicating', () => {
      editorStore.openTab({ id: 'result-1', title: 'Result', type: 'result' });
      editorStore.openTab({ id: 'result-1', title: 'Result', type: 'result' });
      expect(editorStore.tabs).toHaveLength(2); // prompt + result-1
    });
  });

  describe('closeTab', () => {
    it('removes the tab', () => {
      editorStore.openTab({ id: 'result-1', title: 'Result', type: 'result' });
      editorStore.closeTab('result-1');
      expect(editorStore.tabs).toHaveLength(1);
    });

    it('activates prompt tab when closing active tab', () => {
      editorStore.openTab({ id: 'result-1', title: 'Result', type: 'result' });
      editorStore.closeTab('result-1');
      expect(editorStore.activeTabId).toBe(PROMPT_TAB_ID);
    });

    it('does not close pinned prompt tab', () => {
      editorStore.closeTab(PROMPT_TAB_ID);
      expect(editorStore.tabs).toHaveLength(1);
    });
  });

  describe('setActive', () => {
    it('changes active tab', () => {
      editorStore.openTab({ id: 'result-1', title: 'Result', type: 'result' });
      editorStore.setActive(PROMPT_TAB_ID);
      expect(editorStore.activeTabId).toBe(PROMPT_TAB_ID);
    });
  });

  describe('result cache', () => {
    it('caches and retrieves results', () => {
      const result = mockOptimizationResult();
      editorStore.cacheResult('opt-1', result as any);
      expect(editorStore.getResult('opt-1')).toEqual(result);
    });

    it('returns null for uncached result', () => {
      expect(editorStore.getResult('nonexistent')).toBeNull();
    });
  });

  describe('openResult', () => {
    it('creates a result tab for the optimization', () => {
      editorStore.openResult('opt-1');
      expect(editorStore.tabs.some((t) => t.type === 'result')).toBe(true);
    });

    it('caches data when provided', () => {
      const data = mockOptimizationResult();
      editorStore.openResult('opt-1', data as any);
      expect(editorStore.getResult('opt-1')).toBeTruthy();
    });
  });

  describe('openDiff', () => {
    it('creates a diff tab', () => {
      editorStore.openDiff('opt-1');
      expect(editorStore.tabs.some((t) => t.type === 'diff')).toBe(true);
    });
  });

  describe('openMindmap', () => {
    it('creates a mindmap tab', () => {
      editorStore.openMindmap();
      expect(editorStore.tabs.some((t) => t.type === 'mindmap')).toBe(true);
    });
  });

  describe('closeAllResults', () => {
    it('removes all non-prompt tabs', () => {
      editorStore.openResult('opt-1');
      editorStore.openDiff('opt-2');
      editorStore.closeAllResults();
      expect(editorStore.tabs).toHaveLength(1);
      expect(editorStore.tabs[0].id).toBe(PROMPT_TAB_ID);
    });
  });
});
```

- [ ] **Step 3: Write preferences.svelte.test.ts**

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { preferencesStore } from './preferences.svelte';
import { mockFetch } from '../test-utils';

describe('PreferencesStore', () => {
  beforeEach(() => {
    preferencesStore._reset();
  });

  it('starts with default values', () => {
    expect(preferencesStore.defaultStrategy).toBe('auto');
    expect(preferencesStore.loading).toBe(false);
    expect(preferencesStore.error).toBeNull();
  });

  describe('init', () => {
    it('loads preferences from API', async () => {
      mockFetch([{
        match: '/api/preferences',
        response: {
          schema_version: 1,
          models: { analyzer: 'sonnet', optimizer: 'opus', scorer: 'sonnet' },
          pipeline: { enable_explore: true, enable_scoring: true, enable_adaptation: true, force_sampling: false, force_passthrough: false },
          defaults: { strategy: 'chain-of-thought' },
        },
      }]);
      await preferencesStore.init();
      expect(preferencesStore.defaultStrategy).toBe('chain-of-thought');
      expect(preferencesStore.models.optimizer).toBe('opus');
    });
  });

  describe('setModel', () => {
    it('patches a model preference', async () => {
      const fetchMock = mockFetch([
        { match: '/api/preferences', response: preferencesStore.prefs },
      ]);
      await preferencesStore.setModel('optimizer', 'haiku');
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/preferences'),
        expect.objectContaining({ method: 'PATCH' }),
      );
    });
  });

  describe('setPipelineToggle', () => {
    it('patches a pipeline toggle', async () => {
      mockFetch([{ match: '/api/preferences', response: preferencesStore.prefs }]);
      await preferencesStore.setPipelineToggle('enable_explore', true);
      expect(preferencesStore.pipeline.enable_explore).toBe(true);
    });
  });

  describe('isLeanMode', () => {
    it('returns true when explore and scoring are disabled', () => {
      preferencesStore.prefs.pipeline.enable_explore = false;
      preferencesStore.prefs.pipeline.enable_scoring = false;
      expect(preferencesStore.isLeanMode).toBe(true);
    });
  });
});
```

- [ ] **Step 4: Run Tier 2 batch 1 tests**

```bash
cd frontend && npx vitest run src/lib/stores/toast src/lib/stores/editor src/lib/stores/preferences
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/stores/toast.svelte.test.ts frontend/src/lib/stores/editor.svelte.test.ts frontend/src/lib/stores/preferences.svelte.test.ts
git commit -m "test: add store tests for toast, editor, and preferences"
```

---

### Task 6: Tier 2 — Store Tests (github, patterns, refinement, forge, mcp-tooltips)

**Files:**
- Create: `frontend/src/lib/stores/github.svelte.test.ts`
- Create: `frontend/src/lib/stores/patterns.svelte.test.ts`
- Create: `frontend/src/lib/stores/refinement.svelte.test.ts`
- Create: `frontend/src/lib/stores/forge.svelte.test.ts`
- Create: `frontend/src/lib/utils/mcp-tooltips.test.ts`

- [ ] **Step 1: Write github.svelte.test.ts**

Test `checkAuth` (sets user), `login` (returns URL), `logout` (clears user), `loadRepos`, `linkRepo`, `loadLinked`, `unlinkRepo`. Mock all API calls via `mockFetch`. ~12 tests.

- [ ] **Step 2: Write patterns.svelte.test.ts**

Test `checkForPatterns` (50-char delta threshold, debounce timer), `applySuggestion` (returns IDs, clears suggestion), `dismissSuggestion`, `loadGraph`, `invalidateGraph` (sets graphLoaded=false), `selectFamily`. Use `vi.useFakeTimers()` for debounce/dismiss timer tests. Mock `matchPattern`/`getPatternGraph`/`getFamilyDetail` via `mockFetch`. ~18 tests.

- [ ] **Step 3: Write refinement.svelte.test.ts**

Test `init` (loads versions from API), `handleEvent` for SSE events (refinement_turn, scoring_complete, error), `rollback` (creates branch fork), `cancel` (aborts controller), `reset` (clears all state), `scoreProgression` getter (averages dimension scores), `selectVersion`. Mock `getRefinementVersions`/`rollbackRefinement` via `mockFetch`. ~16 tests.

- [ ] **Step 4: Write forge.svelte.test.ts**

This is the largest store. Test:
- Status machine transitions: `handleEvent` for `routing`, `phase`, `preview`, `analysis`, `result`, `passthrough_ready`, `error` SSE events
- `forge()` calls `optimizeSSE` with correct args and opens result tab
- `submitFeedback` sends API call and updates state
- `submitPassthrough` sends API call and loads result
- `loadFromRecord` hydrates from optimization result
- `restoreSession` reads from localStorage and calls `getOptimization`
- `_saveSession` writes to localStorage
- `reset()` clears all state
- Cross-store: `handleEvent('result', ...)` calls `editorStore.cacheResult`

Mock `optimizeSSE`/`getOptimization`/`submitFeedback`/`savePassthrough` via `vi.mock('$lib/api/client')`. ~30 tests.

- [ ] **Step 5: Write mcp-tooltips.test.ts**

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { forgeStore } from '$lib/stores/forge.svelte';
import { preferencesStore } from '$lib/stores/preferences.svelte';
import { forceSamplingTooltip, forcePassthroughTooltip } from './mcp-tooltips';

describe('forceSamplingTooltip', () => {
  beforeEach(() => {
    forgeStore._reset();
    preferencesStore._reset();
  });

  it('returns undefined when not disabled', () => {
    expect(forceSamplingTooltip(false)).toBeUndefined();
  });

  it('returns tooltip when disabled and passthrough is on', () => {
    preferencesStore.prefs.pipeline.force_passthrough = true;
    const tip = forceSamplingTooltip(true);
    expect(tip).toBeTruthy();
    expect(typeof tip).toBe('string');
  });

  it('returns tooltip when disabled and not sampling capable', () => {
    forgeStore.samplingCapable = false;
    const tip = forceSamplingTooltip(true);
    expect(tip).toBeTruthy();
  });
});

describe('forcePassthroughTooltip', () => {
  beforeEach(() => {
    forgeStore._reset();
    preferencesStore._reset();
  });

  it('returns undefined when not disabled', () => {
    expect(forcePassthroughTooltip(false)).toBeUndefined();
  });

  it('returns tooltip when disabled and sampling is on', () => {
    preferencesStore.prefs.pipeline.force_sampling = true;
    const tip = forcePassthroughTooltip(true);
    expect(tip).toBeTruthy();
  });
});
```

- [ ] **Step 6: Run all Tier 2 tests**

```bash
cd frontend && npx vitest run src/lib/stores/ src/lib/utils/mcp-tooltips
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/stores/*.test.ts frontend/src/lib/utils/mcp-tooltips.test.ts
git commit -m "test: add store tests for github, patterns, refinement, forge, mcp-tooltips"
```

---

### Task 7: Tier 3 — API Client Tests

**Files:**
- Create: `frontend/src/lib/api/client.test.ts`
- Create: `frontend/src/lib/api/patterns.test.ts`

- [ ] **Step 1: Write client.test.ts**

Test groups:
- **apiFetch**: success (parses JSON), HTTP error (throws ApiError with status), network error (throws)
- **tryFetch**: returns data on success, returns null on error
- **ApiError**: constructor sets status and message
- **Endpoint functions**: each function (getHealth, getHistory, submitFeedback, getProviders, getSettings, getApiKey, setApiKey, deleteApiKey, getPreferences, patchPreferences, getStrategies, getStrategy, updateStrategy, getOptimization, savePassthrough, githubLogin, githubMe, githubLogout, githubRepos, githubLink, githubLinked, githubUnlink, getRefinementVersions, rollbackRefinement) — verify correct URL, method, body construction via `mockFetch`
- **optimizeSSE / refineSSE** (tests `streamSSE` indirectly — it's not exported): mock fetch to return a ReadableStream with SSE-formatted text, verify onEvent/onError/onComplete callbacks fire correctly
- **connectEventStream**: verify EventSource is created with correct URL, events dispatched to handler

~60 tests total.

- [ ] **Step 2: Write patterns.test.ts (API)**

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { matchPattern, getPatternGraph, listFamilies, getFamilyDetail, renameFamily, searchPatterns, getPatternStats } from './patterns';
import { mockFetch, mockPatternFamily, mockMetaPattern } from '../test-utils';

describe('Pattern API', () => {
  beforeEach(() => {
    mockFetch([
      { match: '/api/patterns/match', response: { match: { family: mockPatternFamily(), meta_patterns: [mockMetaPattern()], similarity: 0.85 } } },
      { match: '/api/patterns/graph', response: { center: { total_families: 1, total_patterns: 1, total_optimizations: 1 }, families: [], edges: [] } },
      { match: '/api/patterns/families/', response: mockPatternFamily() },
      { match: '/api/patterns/families', response: { total: 1, count: 1, offset: 0, has_more: false, next_offset: null, items: [mockPatternFamily()] } },
      { match: '/api/patterns/search', response: [] },
      { match: '/api/patterns/stats', response: { total_families: 5, total_patterns: 12, total_optimizations: 30, domain_distribution: {} } },
    ]);
  });

  it('matchPattern sends POST with prompt_text', async () => {
    const result = await matchPattern('test prompt');
    expect(result.match).toBeTruthy();
    expect(result.match!.similarity).toBe(0.85);
  });

  it('getPatternGraph returns graph data', async () => {
    const graph = await getPatternGraph();
    expect(graph.center.total_families).toBe(1);
  });

  it('listFamilies returns paginated result', async () => {
    const result = await listFamilies();
    expect(result.items).toHaveLength(1);
  });

  it('getFamilyDetail returns family with meta-patterns', async () => {
    const detail = await getFamilyDetail('fam-1');
    expect(detail).toBeTruthy();
  });

  it('searchPatterns returns array', async () => {
    const results = await searchPatterns('test');
    expect(Array.isArray(results)).toBe(true);
  });

  it('getPatternStats returns stats', async () => {
    const stats = await getPatternStats();
    expect(stats.total_families).toBe(5);
  });

  it('renameFamily sends PATCH', async () => {
    mockFetch([{ match: '/api/patterns/families/', response: { id: 'fam-1', intent_label: 'New Name' } }]);
    const result = await renameFamily('fam-1', 'New Name');
    expect(result.intent_label).toBe('New Name');
  });
});
```

- [ ] **Step 3: Run Tier 3 tests**

```bash
cd frontend && npx vitest run src/lib/api/
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api/client.test.ts frontend/src/lib/api/patterns.test.ts
git commit -m "test: add Tier 3 API client tests (client.ts + patterns.ts)"
```

---

### Task 8: Tier 4a — Simple Component Tests (batch 1: shared components)

**Files:**
- Create: `frontend/src/lib/components/shared/Toast.test.ts`
- Create: `frontend/src/lib/components/shared/ScoreCard.test.ts`
- Create: `frontend/src/lib/components/shared/ProviderBadge.test.ts`
- Create: `frontend/src/lib/components/shared/DiffView.test.ts`
- Create: `frontend/src/lib/components/shared/MarkdownRenderer.test.ts`
- Create: `frontend/src/lib/components/shared/CommandPalette.test.ts`

For each component, write behavioral tests with `@testing-library/svelte`'s `render()`. Query by role/text (not CSS classes). Use `userEvent` for interactions. Reset stores in `beforeEach`.

Test cases per component:
- **Toast**: renders toast messages from store, shows correct symbol per action type, dismiss click removes toast
- **ScoreCard**: renders all 5 dimension labels and scores, shows deltas when provided, handles missing overall score
- **ProviderBadge**: displays label for cli/api/mcp/passthrough/none variants, renders nothing when null
- **DiffView**: renders original and optimized text, shows added/removed line counts, toggles between unified/split modes
- **MarkdownRenderer**: renders headings, code blocks, inline code, lists, handles empty content
- **CommandPalette**: opens on Ctrl+K, filters actions by query, keyboard navigation (arrow keys, Enter, Escape)

~35 tests total.

- [ ] **Step 1: Write all 6 shared component test files**
- [ ] **Step 2: Run shared component tests**

```bash
cd frontend && npx vitest run src/lib/components/shared/
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/components/shared/*.test.ts
git commit -m "test: add Tier 4a shared component tests (Toast, ScoreCard, DiffView, etc.)"
```

---

### Task 9: Tier 4a — Simple Component Tests (batch 2: editor + refinement + layout)

**Files:**
- Create: `frontend/src/lib/components/editor/PatternSuggestion.test.ts`
- Create: `frontend/src/lib/components/editor/PromptEdit.test.ts`
- Create: `frontend/src/lib/components/refinement/RefinementInput.test.ts`
- Create: `frontend/src/lib/components/refinement/SuggestionChips.test.ts`
- Create: `frontend/src/lib/components/refinement/ScoreSparkline.test.ts`
- Create: `frontend/src/lib/components/refinement/BranchSwitcher.test.ts`
- Create: `frontend/src/lib/components/layout/ActivityBar.test.ts`
- Create: `frontend/src/lib/components/layout/StatusBar.test.ts`
- Create: `frontend/src/lib/components/layout/EditorGroups.test.ts`

Test cases per component:
- **PatternSuggestion**: shows family name + meta-patterns when suggestion visible, Apply button calls `patternsStore.applySuggestion`, Skip calls `dismissSuggestion`, hidden when no suggestion
- **PromptEdit**: textarea updates `forgeStore.prompt`, submit button triggers `forge()`, disabled during synthesizing, shows phase label during processing
- **RefinementInput**: text input, submit on Enter (not Shift+Enter), calls `onSubmit` with trimmed text, clears after submit, disabled prop disables input
- **SuggestionChips**: renders chip per suggestion, click calls `onSelect` with chip text
- **ScoreSparkline**: renders SVG with polyline, handles empty scores array, handles single score
- **BranchSwitcher**: shows current branch, prev/next buttons, disabled at boundaries, calls `onSwitch`
- **ActivityBar**: renders 5 activity icons, click changes active, highlights current
- **StatusBar**: shows provider name, MCP status, pattern count — mock health API
- **EditorGroups**: renders tab bar with tab names, clicking tab changes active, close button removes tab

~45 tests total.

- [ ] **Step 1: Write all 9 component test files**
- [ ] **Step 2: Run batch 2 tests**

```bash
cd frontend && npx vitest run src/lib/components/editor/ src/lib/components/refinement/ src/lib/components/layout/ActivityBar src/lib/components/layout/StatusBar src/lib/components/layout/EditorGroups
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/components/editor/*.test.ts frontend/src/lib/components/refinement/*.test.ts frontend/src/lib/components/layout/ActivityBar.test.ts frontend/src/lib/components/layout/StatusBar.test.ts frontend/src/lib/components/layout/EditorGroups.test.ts
git commit -m "test: add Tier 4a component tests (editor, refinement, layout basics)"
```

---

### Task 10: Tier 4b — Navigator Deep Tests

**Files:**
- Create: `frontend/src/lib/components/layout/Navigator.test.ts`

Navigator.svelte (984 lines) is the most complex component. Test key behavioral paths:

- [ ] **Step 1: Write Navigator.test.ts**

Test cases (~18 tests):
- **History rendering**: renders list of history items from mocked API, shows trace_id/strategy/score per item, handles empty history
- **Sort toggling**: clicking sort buttons changes sort order, re-fetches history
- **Pagination**: "Load more" button fetches next page, hidden when `has_more` is false
- **Preferences panel**: model dropdowns render current values, pipeline toggle switches reflect prefs state
- **API key management**: shows "Configure" when no key, shows masked key when configured, set/delete flow
- **Strategy editing**: click strategy opens editor, save calls `updateStrategy`, discard cancels
- **Empty state**: renders placeholder when no history items
- **Real-time events**: dispatching `optimization-event` refreshes the history list

Mock `getHistory`, `getStrategies`, `getProviders`, `getSettings`, `getApiKey` via `mockFetch`. Reset stores and mocks in `beforeEach`.

- [ ] **Step 2: Run Navigator tests**

```bash
cd frontend && npx vitest run src/lib/components/layout/Navigator
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/components/layout/Navigator.test.ts
git commit -m "test: add Tier 4b Navigator behavioral tests"
```

---

### Task 11: Tier 4b — Inspector Deep Tests

**Files:**
- Create: `frontend/src/lib/components/layout/Inspector.test.ts`

Inspector.svelte (705 lines). Test key behavioral paths:

- [ ] **Step 1: Write Inspector.test.ts**

Test cases (~14 tests):
- **Family detail display**: shows intent_label, domain badge, task_type, member count, usage count, avg score when family selected
- **Meta-patterns list**: renders each meta-pattern text with source count
- **Linked optimizations**: renders list of optimization entries, clicking one opens result tab
- **Inline rename**: click rename button enters edit mode, save calls `renameFamily`, cancel reverts, Escape cancels
- **Tab switching**: switches between forge result view and family detail view
- **Empty state**: shows placeholder when no family selected and no forge result
- **Score display**: renders ScoreCard when forge result has scores
- **Feedback state**: shows feedback indicator from forgeStore, syncs on feedback-event

Pre-set `patternsStore.selectedFamilyId` and mock `getFamilyDetail` via `mockFetch`. Mock `renameFamily` for rename tests. Reset stores in `beforeEach`.

- [ ] **Step 2: Run Inspector tests**

```bash
cd frontend && npx vitest run src/lib/components/layout/Inspector
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/components/layout/Inspector.test.ts
git commit -m "test: add Tier 4b Inspector behavioral tests"
```

---

### Task 12: Tier 4b — PatternNavigator Deep Tests

**Files:**
- Create: `frontend/src/lib/components/layout/PatternNavigator.test.ts`

PatternNavigator.svelte (543 lines). Test key behavioral paths:

- [ ] **Step 1: Write PatternNavigator.test.ts**

Test cases (~12 tests):
- **Family list rendering**: renders families grouped by domain, shows domain headers, shows intent_label/score/member_count per family
- **Pagination**: "Load more" button visible when has_more, clicking loads next page, hidden when fully loaded
- **Domain filtering**: selecting a domain filter re-fetches with domain param
- **Search**: typing in search input triggers `searchPatterns` after debounce, shows search results, clearing input returns to family list
- **Family selection**: clicking a family dispatches to `patternsStore.selectFamily`, opens Inspector
- **Empty state**: shows placeholder when no families
- **Loading state**: shows loading indicator during initial load
- **Graph invalidation**: when `patternsStore.graphLoaded` becomes false, reloads families

Mock `listFamilies`, `searchPatterns` via `mockFetch`. Reset stores in `beforeEach`.

- [ ] **Step 2: Run PatternNavigator tests**

```bash
cd frontend && npx vitest run src/lib/components/layout/PatternNavigator
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/components/layout/PatternNavigator.test.ts
git commit -m "test: add Tier 4b PatternNavigator behavioral tests"
```

---

### Task 13: Tier 4c — Smoke Tests

**Files:**
- Create: `frontend/src/lib/components/shared/Logo.test.ts`
- Create: `frontend/src/lib/components/editor/ForgeArtifact.test.ts`
- Create: `frontend/src/lib/components/editor/PassthroughView.test.ts`
- Create: `frontend/src/lib/components/refinement/RefinementTimeline.test.ts`
- Create: `frontend/src/lib/components/refinement/RefinementTurnCard.test.ts`
- Create: `frontend/src/lib/components/patterns/RadialMindmap.test.ts`
- Create: `frontend/src/lib/components/landing/Navbar.test.ts`
- Create: `frontend/src/lib/components/landing/Footer.test.ts`
- Create: `frontend/src/lib/components/landing/ContentPage.test.ts`
- Create: `frontend/src/lib/components/landing/sections/HeroSection.test.ts`
- Create: `frontend/src/lib/components/landing/sections/CardGrid.test.ts`
- Create: `frontend/src/lib/components/landing/sections/Timeline.test.ts`
- Create: `frontend/src/lib/components/landing/sections/MetricBar.test.ts`
- Create: `frontend/src/lib/components/landing/sections/CodeBlock.test.ts`
- Create: `frontend/src/lib/components/landing/sections/StepFlow.test.ts`
- Create: `frontend/src/lib/components/landing/sections/ProseSection.test.ts`

Each smoke test follows the same pattern:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import ComponentName from './ComponentName.svelte';

describe('ComponentName', () => {
  it('renders without crashing', () => {
    render(ComponentName, { props: { /* required props */ } });
    // Assert a key element is present
    expect(screen.getByText('expected text')).toBeInTheDocument();
  });
});
```

Per-component notes:
- **Logo**: no props, assert SVG or logo element renders
- **ForgeArtifact**: needs `forgeStore.result` pre-set, assert optimized prompt text visible
- **PassthroughView**: needs `forgeStore.assembledPrompt` pre-set, assert assembled prompt visible
- **RefinementTimeline**: pass `turns` and `branches` props, assert turn cards render
- **RefinementTurnCard**: pass a turn object, assert version number visible
- **RadialMindmap**: mock D3 module (`vi.mock('d3', ...)`), pass graph data, assert SVG renders
- **Navbar**: assert navigation links render, logo visible
- **Footer**: assert footer links render
- **ContentPage**: pass markdown content, assert rendered text visible
- **HeroSection**: no required props, assert heading text renders
- **CardGrid**: pass card items, assert cards render
- **Timeline**: pass timeline steps, assert steps render
- **MetricBar**: pass metric values, assert numbers visible
- **CodeBlock**: pass code content, assert code text renders
- **StepFlow**: pass step items, assert step labels render
- **ProseSection**: pass text content, assert content visible

- [ ] **Step 1: Write all 16 smoke test files**
- [ ] **Step 2: Run all smoke tests**

```bash
cd frontend && npx vitest run src/lib/components/shared/Logo src/lib/components/editor/ForgeArtifact src/lib/components/editor/PassthroughView src/lib/components/refinement/RefinementTimeline src/lib/components/refinement/RefinementTurnCard src/lib/components/patterns/RadialMindmap src/lib/components/landing/ src/lib/components/landing/sections/
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/components/shared/Logo.test.ts frontend/src/lib/components/editor/ForgeArtifact.test.ts frontend/src/lib/components/editor/PassthroughView.test.ts frontend/src/lib/components/refinement/RefinementTimeline.test.ts frontend/src/lib/components/refinement/RefinementTurnCard.test.ts frontend/src/lib/components/patterns/RadialMindmap.test.ts frontend/src/lib/components/landing/*.test.ts frontend/src/lib/components/landing/sections/*.test.ts
git commit -m "test: add Tier 4c smoke tests for remaining components"
```

---

### Task 14: Coverage Verification and Gap Filling

- [ ] **Step 1: Run full test suite with coverage**

```bash
cd frontend && npx vitest run --coverage
```

- [ ] **Step 2: Review coverage report**

Check the terminal output or open `frontend/coverage/index.html` in a browser. Identify any files below 90% line coverage.

- [ ] **Step 3: Fill coverage gaps**

Common gap sources and fixes:
- **Uncovered branches in stores**: add tests for error paths (API call failures, edge cases)
- **Uncovered component branches**: add tests for conditional rendering (empty states, loading states, error states)
- **Uncovered utility branches**: add edge case tests

Write additional tests as needed to bring coverage to ≥90%.

- [ ] **Step 4: Run final coverage verification**

```bash
cd frontend && npx vitest run --coverage
```

Expected: ≥90% line coverage on `src/lib/**`.

- [ ] **Step 5: Commit gap-fill tests**

```bash
git add frontend/src/
git commit -m "test: fill coverage gaps to reach 90% threshold"
```

---

### Task 15: Final Verification

- [ ] **Step 1: Run full test suite**

```bash
cd frontend && npx vitest run
```

Expected: all tests pass (0 failures).

- [ ] **Step 2: Run with coverage thresholds**

```bash
cd frontend && npx vitest run --coverage
```

Expected: passes with ≥90% line coverage (vitest exits 0).

- [ ] **Step 3: Run backend tests to confirm no regressions**

```bash
cd backend && source .venv/bin/activate && pytest --tb=short -q
```

Expected: 599 passed.

- [ ] **Step 4: Final commit if any loose changes**

```bash
git status
# If clean, nothing to do. Otherwise:
git add frontend/
git commit -m "test: frontend coverage at 90%+ — all tiers complete"
```
