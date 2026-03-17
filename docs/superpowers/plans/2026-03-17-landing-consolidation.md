# Landing Page Consolidation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate 15 content subpages into a single-scroll landing page with scroll-driven animations. Remove 11 pages, keep 4 legal/info pages.

**Architecture:** Complete rewrite of `+page.svelte` with 6 inline sections (Hero, Pipeline, Live Example, Works Everywhere, Trust+CTA, Footer). Delete 11 content page files, 4 section components, 3 landing components. Clean up type system and registry.

**Tech Stack:** SvelteKit 2, Svelte 5 runes, CSS `animation-timeline: scroll()`, CSS `@keyframes`, `position: sticky`, `@property --num` counters.

**Spec:** `docs/superpowers/specs/2026-03-17-landing-consolidation-design.md`

**Brand guidelines:** `.claude/skills/brand-guidelines` — dark-first, 1px neon contours, zero effects, Space Grotesk/Syne/Geist Mono, spring entrance (`cubic-bezier(0.16, 1, 0.3, 1)`), accelerating exit.

---

## Task 1: Delete removed files + clean registry

**Files:**
- Delete: `frontend/src/lib/content/pages/pipeline.ts`
- Delete: `frontend/src/lib/content/pages/scoring.ts`
- Delete: `frontend/src/lib/content/pages/refinement.ts`
- Delete: `frontend/src/lib/content/pages/integrations.ts`
- Delete: `frontend/src/lib/content/pages/documentation.ts`
- Delete: `frontend/src/lib/content/pages/api-reference.ts`
- Delete: `frontend/src/lib/content/pages/mcp-server.ts`
- Delete: `frontend/src/lib/content/pages/about.ts`
- Delete: `frontend/src/lib/content/pages/blog.ts`
- Delete: `frontend/src/lib/content/pages/careers.ts`
- Delete: `frontend/src/lib/content/pages/contact.ts`
- Delete: `frontend/src/lib/components/landing/sections/ArticleList.svelte`
- Delete: `frontend/src/lib/components/landing/sections/RoleList.svelte`
- Delete: `frontend/src/lib/components/landing/sections/ContactForm.svelte`
- Delete: `frontend/src/lib/components/landing/sections/EndpointList.svelte`
- Delete: `frontend/src/lib/components/landing/FeatureCard.svelte`
- Delete: `frontend/src/lib/components/landing/TestimonialCard.svelte`
- Delete: `frontend/src/lib/components/landing/StepCard.svelte`
- Modify: `frontend/src/lib/content/pages.ts`
- Modify: `frontend/src/lib/content/types.ts`
- Modify: `frontend/src/lib/components/landing/ContentPage.svelte`

**IMPORTANT: Steps 1-6 are a single atomic unit. Do not run verification until all 6 steps are complete. Intermediate states will have broken imports.**

- [ ] **Step 1: Delete the 11 content page data files**

```bash
cd frontend
rm src/lib/content/pages/pipeline.ts \
   src/lib/content/pages/scoring.ts \
   src/lib/content/pages/refinement.ts \
   src/lib/content/pages/integrations.ts \
   src/lib/content/pages/documentation.ts \
   src/lib/content/pages/api-reference.ts \
   src/lib/content/pages/mcp-server.ts \
   src/lib/content/pages/about.ts \
   src/lib/content/pages/blog.ts \
   src/lib/content/pages/careers.ts \
   src/lib/content/pages/contact.ts
```

- [ ] **Step 2: Delete the 4 section components no longer needed**

```bash
rm src/lib/components/landing/sections/ArticleList.svelte \
   src/lib/components/landing/sections/RoleList.svelte \
   src/lib/components/landing/sections/ContactForm.svelte \
   src/lib/components/landing/sections/EndpointList.svelte
```

- [ ] **Step 3: Delete the 3 landing-only components replaced by inline sections**

```bash
rm src/lib/components/landing/FeatureCard.svelte \
   src/lib/components/landing/TestimonialCard.svelte \
   src/lib/components/landing/StepCard.svelte
```

- [ ] **Step 4: Update pages.ts — keep only 4 pages**

Read current `src/lib/content/pages.ts`. Remove all imports except privacy, terms, security, changelog. The `allPages` record should have exactly 4 entries.

- [ ] **Step 5: Update types.ts — remove 4 dead section types**

Read current `src/lib/content/types.ts`. Remove these interfaces: `EndpointListSection`, `ArticleListSection`, `RoleListSection`, `ContactFormSection`. Remove them from the `Section` discriminated union. Keep all other types intact (hero, prose, card-grid, step-flow, code-block, metric-bar, timeline — used by the 4 remaining pages).

- [ ] **Step 6: Update ContentPage.svelte — remove 4 dead branches**

Read current `src/lib/components/landing/ContentPage.svelte`. Remove the imports and `{:else if}` branches for ArticleList, RoleList, ContactForm, EndpointList.

- [ ] **Step 7: Verify**

```bash
npx svelte-check --tsconfig ./tsconfig.json 2>&1 | tail -3
```
Expected: 0 errors, 0 warnings.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "chore(landing): remove 11 content pages, 7 unused components, clean registry"
```

---

## Task 2: Update animations CSS

**Files:**
- Modify: `frontend/src/lib/styles/content-animations.css`

- [ ] **Step 1: Add pipeline scroll, logo strip, and score bar keyframes**

Read the current `content-animations.css`. Add these keyframes (append, don't replace existing):

```css
/* Pipeline scroll-pinned phases — desktop only */
@supports (animation-timeline: scroll()) {
  @media (min-width: 768px) {
    .pipeline-phase {
      opacity: 0;
      transform: translateY(24px);
      animation: phase-reveal 1s var(--ease-spring) both;
      animation-timeline: view();
      animation-range: entry 0% entry 80%;
    }
  }
}

@keyframes phase-reveal {
  to { opacity: 1; transform: translateY(0); }
}

/* Score bar fill animation */
@supports (animation-timeline: view()) {
  .score-bar-fill {
    animation: bar-fill 1s var(--ease-spring) both;
    animation-timeline: view();
    animation-range: entry 0% entry 100%;
  }
}

@keyframes bar-fill {
  from { width: 0; }
}

/* Logo strip infinite scroll */
@keyframes scroll-logos {
  to { transform: translateX(-50%); }
}

/* Hero mockup phase sequence (page load, not scroll) */
@keyframes phase-type-in {
  from { opacity: 0; transform: translateX(-8px); }
  to { opacity: 1; transform: translateX(0); }
}

@keyframes score-count {
  from { opacity: 0; }
  to { opacity: 1; }
}
```

- [ ] **Step 2: Verify**

```bash
npx svelte-check --tsconfig ./tsconfig.json 2>&1 | tail -3
```

- [ ] **Step 3: Commit**

```bash
git add src/lib/styles/content-animations.css
git commit -m "feat(landing): add pipeline scroll, logo strip, and score bar animation keyframes"
```

---

## Task 3: Rewrite the landing page

This is the main task — a complete rewrite of `src/routes/(landing)/+page.svelte`.

**Files:**
- Modify: `frontend/src/routes/(landing)/+page.svelte` — complete rewrite

**Important context for the implementer:**
- Read the spec: `docs/superpowers/specs/2026-03-17-landing-consolidation-design.md` — all section content is defined there
- Read the brand guidelines skill at `.claude/skills/brand-guidelines` for design tokens, typography, color system, zero-effects directive
- Read `src/app.css` for CSS custom properties (all `--color-*`, `--font-*`, `--ease-*`, `--duration-*` tokens)
- Read `src/lib/styles/content-animations.css` for animation classes (`data-reveal`, `pipeline-phase`, `score-bar-fill`, `scroll-logos`)
- Read the CURRENT `+page.svelte` to understand the existing patterns (Navbar/Footer imports, `data-animate` observer, scoped `<style>`)

- [ ] **Step 1: Write the complete page**

The page has 6 sections. Here is the full structure:

**Script block:**
- Import Navbar, Footer (from `$lib/components/landing/`)
- Import `base` from `$app/paths`
- Set up IntersectionObserver for `data-animate` elements (same pattern as current page — needed for hero load animations)
- No other imports — all sections are inline. (`APP_VERSION` is NOT used in the page — Footer handles it.)

**CRITICAL scroll container context:** The scroll container is `.landing-root` (the `<div>` in `+layout.svelte` with `overflow-y: auto`), NOT the viewport. `html` and `body` have `overflow: hidden; height: 100vh` from `app.css`. All `position: sticky` and `animation-timeline: scroll()` references resolve against `.landing-root`. This is how the existing page works — do not change it.

**Intentional removals:** The current page has a "Social Proof Bar" (fabricated metrics like "14,200+ Prompts Optimized") and a "Testimonials" section (3 fictional customer quotes). Both are intentionally removed and NOT carried forward. They are replaced by Section 3 (Live Example with real data).

**Template — Section 1: Hero** (`id="hero"`)
- `aria-labelledby="hero-heading"`
- Headline: "Prompts In." + line break + gradient span "Better Prompts Out." — Syne, uppercase, `letter-spacing: 0.1em`, `clamp(24px, 4vw, 40px)`
- Subheading: "AI-powered prompt optimization pipeline. Analyze, rewrite, and score — with or without an API key. Self-hosted. Open source. Measurably better."
- Two CTAs: "View on GitHub" (primary, `target="_blank"`, GitHub SVG icon) + "See It Work" (ghost, `href="#example"`)
- Product mockup: animated pipeline visualization showing 3 phases (ANALYZE/OPTIMIZE/SCORE) with sequential `animation-delay` on page load. Each phase: colored badge + description text. Score phase shows overall 8.4 with 5 mini bars. Use `@keyframes phase-type-in` with delays 800ms/1300ms/1800ms.
- Grid layout: text left, mockup right on desktop. Stacks on mobile.

**Template — Section 2: Pipeline Deep-Dive** (`id="pipeline"`)
- `aria-labelledby="pipeline-heading"`
- Section heading: "THREE PHASES. ZERO GUESSWORK." — section-heading class
- On desktop (≥768px): `height: 300vh` wrapper with `position: sticky` inner container. 3 phase panels positioned at 0vh, 100vh, 200vh. Each panel uses `pipeline-phase` class for scroll-driven reveal.
- On mobile (<768px): 3 stacked panels with `data-reveal` fade-up (no sticky).
- Phase 1 (ANALYZE, cyan): description + visual cues (task type badge, weakness tags)
- Phase 2 (OPTIMIZE, purple): description + visual cues (strategy badge, structure additions)
- Phase 3 (SCORE, green): description + visual cues (5 dimension bars, delta badges)
- Each phase panel: icon/number + heading (Syne uppercase) + description text (text-secondary) + visual element on the right

**Template — Section 3: Live Example** (`id="example"`)
- `aria-labelledby="example-heading"`
- Section heading: "BEFORE AND AFTER."
- Before panel: mockup container (bg-input, text-dim, font-mono) with `Build a REST API for a todo app`. Below it: analyzer overlay showing task_type: coding, 6 weaknesses, strategy: structured-output, confidence: 0.92
- After panel: mockup container (bg-card, text-primary) with the full optimized prompt from the spec (## Task, ## Endpoints, ## Constraints, ## Output sections). The `##` headers rendered in neon-cyan.
- Score comparison below: 5 rows, each with dimension name (70px) + before bar (dim) + after bar (neon colored, `score-bar-fill` class) + delta badge. Use the exact values from the spec table.
- Below scores: one-line methodology summary in text-dim.
- Desktop: side by side. Mobile: stacked.

**Template — Section 4: Works Everywhere** (`id="integrations"`)
- `aria-labelledby="integrations-heading"`
- Section heading: "NO VENDOR LOCK-IN. NO API KEY REQUIRED."
- 3 tier cards in a row (stacks on mobile): Zero Config (cyan icon), Your IDE Your LLM (purple icon), Codebase-Aware (green icon). Each: icon + heading (font-sans weight 600) + description (text-secondary). No code snippets.
- Below Tier 2: logo strip. Duplicate a row of 6 IDE name labels (`font-mono`, `text-dim`): Claude Code, Cursor, Windsurf, VS Code, Zed, JetBrains. CSS `animation: scroll-logos 30s linear infinite`. Container has `overflow: hidden`.

**Template — Section 5: Get Started + Trust** (`id="trust"`)
- `aria-labelledby="cta-heading"`
- Background: `bg-secondary` with gradient top border (`border-image: linear-gradient(135deg, #00e5ff 0%, #7c3aed 50%, #a855f7 100%) 1`)
- Mission line: "Built by engineers who got tired of vague prompts. Apache 2.0 licensed. No telemetry. No cloud dependency. Your prompts never leave your infrastructure."
- Trust badges: 4 inline badges, each with SVG icon + label + link to legal page. Use `base` import for hrefs.
  - Lock icon → "Encrypted at rest" → `/security`
  - Eye-off icon → "Zero telemetry" → `/privacy`
  - Scale icon → "Apache 2.0" → `/terms`
  - Server icon → "Self-hosted" → `/privacy`
- CTA: gradient heading "STOP GUESSING. START MEASURING." + sub text + "View on GitHub" button

**Template — Footer:**
- Import Footer component. No changes needed here — Footer is updated in Task 4.

**Style block:**
All styles scoped. Use CSS custom properties from `app.css`. Key patterns:
- Hero: 2-column grid on desktop, stacks on mobile
- Pipeline: 300vh wrapper with sticky on desktop, stacked with gap on mobile (`@media max-width: 768px`)
- Example: 2-column grid for before/after on desktop, stacks on mobile
- Works Everywhere: 3-column grid, stacks on mobile
- Trust: centered text, horizontal badge row, wraps on mobile
- Score bars: grid `name (70px) | before-bar (1fr) | after-bar (1fr) | delta (50px)`
- Logo strip: `overflow: hidden`, inner flex with `animation: scroll-logos`
- All interactive elements: hover transitions 200ms, border-subtle → border-accent
- Pipeline mobile: `@media (max-width: 768px) { .pipeline-section { height: auto; } .pipeline-sticky { position: static; height: auto; } }`
- Pipeline fallback: `@supports not (animation-timeline: scroll()) { .pipeline-section { height: auto; } .pipeline-sticky { position: static; height: auto; } .pipeline-phase { opacity: 1; transform: none; } }` — desktop browsers without scroll-timeline get stacked layout with `data-reveal` fade-up

- [ ] **Step 2: Verify**

```bash
npx svelte-check --tsconfig ./tsconfig.json 2>&1 | tail -3
npx vite build 2>&1 | tail -3
```
Both must pass with 0 errors.

- [ ] **Step 3: Commit**

```bash
git add src/routes/\(landing\)/+page.svelte
git commit -m "feat(landing): rewrite as single-scroll with pipeline deep-dive, live example, integrations"
```

---

## Task 4: Update Footer + Navbar

**Files:**
- Modify: `frontend/src/lib/components/landing/Footer.svelte`
- Modify: `frontend/src/lib/components/landing/Navbar.svelte`

- [ ] **Step 1: Rewrite Footer — 2 columns + meta row**

Read current Footer.svelte. Replace the 4-column structure with 2 columns:

Column 1 — Product:
- Pipeline → `#pipeline` (anchor)
- Live Example → `#example` (anchor)
- Integrations → `#integrations` (anchor)
- Changelog → `${base}/changelog` (route)

Column 2 — Legal:
- Privacy → `${base}/privacy`
- Terms → `${base}/terms`
- Security → `${base}/security`

Meta row: copyright + APP_VERSION + GitHub link (`https://github.com/project-synthesis/ProjectSynthesis`)

- [ ] **Step 2: Update Navbar anchor links**

Read current Navbar.svelte. Update `navLinks` to match the new sections:

```typescript
const navLinks = $derived([
  { label: 'Pipeline', href: `${anchorPrefix}#pipeline` },
  { label: 'Example', href: `${anchorPrefix}#example` },
  { label: 'Integrations', href: `${anchorPrefix}#integrations` },
]);
```

- [ ] **Step 3: Verify**

```bash
npx svelte-check --tsconfig ./tsconfig.json 2>&1 | tail -3
```

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/landing/Footer.svelte src/lib/components/landing/Navbar.svelte
git commit -m "feat(landing): trim footer to 2 columns, update navbar anchors for consolidated page"
```

---

## Task 5: Build verification

- [ ] **Step 1: Type check**

```bash
cd frontend && npx svelte-check --tsconfig ./tsconfig.json 2>&1 | tail -5
```
Expected: 0 errors, 0 warnings

- [ ] **Step 2: Production build (normal)**

```bash
npx vite build 2>&1 | tail -3
```
Expected: Build succeeds

- [ ] **Step 3: Production build (GitHub Pages)**

```bash
GITHUB_PAGES=true npx vite build 2>&1 | tail -3
```
Expected: Build succeeds

- [ ] **Step 4: Verify 4 remaining slugs**

```bash
npx tsx -e "import { getAllSlugs } from './src/lib/content/pages.ts'; console.log('Slugs:', getAllSlugs().sort().join(', '), '— count:', getAllSlugs().length)"
```
Expected: `Slugs: changelog, privacy, security, terms — count: 4`

- [ ] **Step 5: Final commit + push**

```bash
git add -A
git status
# If clean, push:
git push origin main
```
