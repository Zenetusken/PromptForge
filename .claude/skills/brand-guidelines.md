# PromptForge Brand Guidelines

## Brand Identity

### Name & Concept
- **Name:** PromptForge
- **Tagline:** "AI-Powered Prompt Optimization"
- **Concept:** A forge that refines raw prompts into precision-engineered instructions through a 4-stage AI pipeline (Analyze, Strategy, Optimize, Validate)

### Brand Personality
| Trait | Expression |
|-------|------------|
| Cyberpunk | Dark interfaces, sharp neon accents, glass morphism, flat solid edges |
| Intelligent | Data-driven pipeline, scored results, strategy recommendations |
| Precise | Numeric scores, structured output, measurable improvements |
| Bold | High-contrast neon palette, solid gradients, pure neon UI elements |
| Technical | Monospace data, terminal aesthetic, developer-first voice |

### Design Density
- **Philosophy:** Ultra-compact analytical dashboard — VS Code density with Excel's data-rich information hierarchy
- **Density rule:** Maximize information per pixel. Padding, gaps, and radii skew toward the smaller end of each scale.
- **Radius rule:** Smaller radii signal precision. Hero-level rounding (12px+) is reserved for rare modal/dialog containers.
- **Padding rule:** Most panels use p-2 (8px). Only dialog/hero contexts exceed p-3 (12px).

### Licensing & Distribution

| Attribute | Value |
|-----------|-------|
| **Type** | Open Source Web Application |
| **Licensing** | MIT License |
| **Deployment** | Self-hosted (Docker or local dev) |
| **Domain** | zenresources.net |

### Support & Contact

| Purpose | Contact |
|---------|---------|
| Brand inquiries | brand@zenresources.net |
| General support | support@zenresources.net |
| Legal matters | legal@zenresources.net |
| Security issues | security@zenresources.net |

---

## Color System

### Primary Brand Accent
- **Neon Cyan:** `#00e5ff`
- Usage: Primary actions, focus states, brand identity, links, active indicators

### Neon Palette (10 Colors)

| Token | Hex | CSS Variable | Primary Usage |
|-------|-----|-------------|---------------|
| neon-cyan | `#00e5ff` | `--color-neon-cyan` | Primary accent, focus rings, scrollbars |
| neon-purple | `#a855f7` | `--color-neon-purple` | Secondary accent, version panels, gradients |
| neon-green | `#22ff88` | `--color-neon-green` | Success, tags, context fields |
| neon-red | `#ff3366` | `--color-neon-red` | Danger, errors, destructive actions |
| neon-yellow | `#fbbf24` | `--color-neon-yellow` | Warnings, recommendations, forge sparks |
| neon-orange | `#ff8c00` | `--color-neon-orange` | Alerts, attention states |
| neon-blue | `#4d8eff` | `--color-neon-blue` | Info, analysis indicators |
| neon-pink | `#ff6eb4` | `--color-neon-pink` | Creative accents |
| neon-teal | `#00d4aa` | `--color-neon-teal` | Extraction, secondary success |
| neon-indigo | `#7b61ff` | `--color-neon-indigo` | Reasoning, special indicators |

### Background Hierarchy

| Token | Hex | CSS Variable | Purpose |
|-------|-----|-------------|---------|
| bg-primary | `#06060c` | `--color-bg-primary` | Page background (deepest dark) |
| bg-input | `#0a0a14` | `--color-bg-input` | Input fields, recessed wells |
| bg-secondary | `#0c0c16` | `--color-bg-secondary` | Glass panels, secondary surfaces |
| bg-card | `#11111e` | `--color-bg-card` | Cards, elevated panels |
| bg-hover | `#16162a` | `--color-bg-hover` | Hover states, active surfaces |
| bg-glass | `rgba(12, 12, 22, 0.7)` | `--color-bg-glass` | Glass morphism overlay |

### Text Hierarchy

| Token | Hex | CSS Variable | Purpose |
|-------|-----|-------------|---------|
| text-primary | `#e4e4f0` | `--color-text-primary` | Headlines, body text, values |
| text-secondary | `#8b8ba8` | `--color-text-secondary` | Descriptions, secondary labels |
| text-dim | `#7a7a9e` | `--color-text-dim` | Timestamps, metadata, disabled text |

### Border Colors

| Token | Value | CSS Variable | Purpose |
|-------|-------|-------------|---------|
| border-subtle | `rgba(74, 74, 106, 0.15)` | `--color-border-subtle` | Default card/input borders |
| border-accent | `rgba(0, 229, 255, 0.12)` | `--color-border-accent` | Divider accent, accent borders |

### Glass Morphism

```css
/* Standard glass panel */
.glass {
  background: color-mix(in srgb, var(--color-bg-secondary) 92%, transparent);
}

/* Collapsible sections */
background: color-mix(in srgb, var(--color-bg-card) 50%, transparent);

/* Backdrop blur (used on version panels, delete bars) */
backdrop-filter: blur(4px);  /* light blur */
backdrop-filter: blur(8px);  /* medium blur */
```

### Gradient Signatures

```css
/* Primary brand gradient — buttons, hero text */
linear-gradient(135deg, #00e5ff 0%, #7c3aed 50%, #a855f7 100%)

/* Divider accent */
linear-gradient(90deg, transparent, var(--color-border-accent), transparent)

/* Card top accent line (hover) */
linear-gradient(90deg, transparent, rgba(0, 229, 255, 0.3), transparent)

/* Project header gradient */
linear-gradient(90deg, transparent, var(--color-neon-cyan), var(--color-neon-purple), transparent)
```

---

## Strategy Color Mapping

Each of the 10 optimization strategies has a unique neon color for visual identification across bars, badges, borders, and buttons.

| Strategy | Color Name | Hex | Raw RGBA |
|----------|-----------|-----|----------|
| Chain of Thought | neon-cyan | `#00e5ff` | `rgba(0, 229, 255, 0.35)` |
| CO-STAR | neon-purple | `#a855f7` | `rgba(168, 85, 247, 0.35)` |
| RISEN | neon-green | `#22ff88` | `rgba(34, 255, 136, 0.35)` |
| Role-Task-Format | neon-red | `#ff3366` | `rgba(255, 51, 102, 0.35)` |
| Few-Shot | neon-yellow | `#fbbf24` | `rgba(251, 191, 36, 0.35)` |
| Step by Step | neon-orange | `#ff8c00` | `rgba(255, 140, 0, 0.35)` |
| Structured Output | neon-blue | `#4d8eff` | `rgba(77, 142, 255, 0.35)` |
| Constraint Injection | neon-pink | `#ff6eb4` | `rgba(255, 110, 180, 0.35)` |
| Context Enrichment | neon-teal | `#00d4aa` | `rgba(0, 212, 170, 0.35)` |
| Persona Assignment | neon-indigo | `#7b61ff` | `rgba(123, 97, 255, 0.35)` |

**Source:** `frontend/src/lib/utils/strategies.ts` (`STRATEGY_COLOR_META`)

---

## Task Type Color Mapping

Each of the 14 classified task types has a neon color assignment. Primary types use full-opacity colors; secondary types use dimmed variants.

| Task Type | Color Name | CSS Color | Raw RGBA |
|-----------|-----------|-----------|----------|
| coding | neon-cyan | `#00e5ff` | `rgba(0, 229, 255, 0.35)` |
| analysis | neon-blue | `#4d8eff` | `rgba(77, 142, 255, 0.35)` |
| reasoning | neon-indigo | `#7b61ff` | `rgba(123, 97, 255, 0.35)` |
| math | neon-purple | `#a855f7` | `rgba(168, 85, 247, 0.35)` |
| writing | neon-green | `#22ff88` | `rgba(34, 255, 136, 0.35)` |
| creative | neon-pink | `#ff6eb4` | `rgba(255, 110, 180, 0.35)` |
| extraction | neon-teal | `#00d4aa` | `rgba(0, 212, 170, 0.35)` |
| classification | neon-orange | `#ff8c00` | `rgba(255, 140, 0, 0.35)` |
| formatting | neon-yellow | `#fbbf24` | `rgba(251, 191, 36, 0.35)` |
| medical | neon-red | `#ff3366` | `rgba(255, 51, 102, 0.35)` |
| legal | neon-red (dim) | `rgba(255, 51, 102, 0.7)` | `rgba(255, 51, 102, 0.25)` |
| education | neon-teal (dim) | `rgba(0, 212, 170, 0.7)` | `rgba(0, 212, 170, 0.25)` |
| general | neon-cyan (dim) | `rgba(0, 229, 255, 0.6)` | `rgba(0, 229, 255, 0.20)` |
| other | text-dim | `rgba(255, 255, 255, 0.4)` | `rgba(255, 255, 255, 0.10)` |

**Source:** `frontend/src/lib/utils/taskTypes.ts` (`TASK_TYPE_COLOR_META`)

---

## Complexity Colors

3-tier system with alias normalization (simple/low, moderate/medium, complex/high).

| Level | Aliases | Color Name | Hex | Raw RGBA |
|-------|---------|-----------|-----|----------|
| Low | simple, low | neon-green | `#22ff88` | `rgba(34, 255, 136, 0.35)` |
| Medium | moderate, medium | neon-yellow | `#fbbf24` | `rgba(251, 191, 36, 0.35)` |
| High | complex, high | neon-red | `#ff3366` | `rgba(255, 51, 102, 0.35)` |

**Source:** `frontend/src/lib/utils/complexity.ts`

---

## Typography

### Font Stack

| Purpose | Font | Fallback | CSS Variable |
|---------|------|----------|-------------|
| UI Text | Geist | Inter, ui-sans-serif, system-ui, sans-serif | `--font-sans` |
| Code / Data | Geist Mono | JetBrains Mono, ui-monospace, monospace | `--font-mono` |
| Display / Headings | Syne | Geist, ui-sans-serif, system-ui, sans-serif | `--font-display` |

### Type Scale

| Class | Size | Weight | Font | Use |
|-------|------|--------|------|-----|
| Section heading | 12px | 700 | Syne (display) | Section labels, uppercase, `letter-spacing: 0.1em` |
| Body | 14px | 400 | Geist (sans) | Standard UI text |
| Badge | 10px | 500 | Geist Mono (mono) | Badges, chips, metadata |
| Badge (small) | 9px | 500 | Geist Mono (mono) | Compact badges |
| Chip | 10px | 500 | Geist Mono (mono) | Pill labels, tags |
| Input field | 14px | 400 | Geist (sans) | Form inputs |
| Select field | 11px | 500 | Geist (sans) | Dropdown selects |
| Score circle | 10px | 700 | Geist Mono (mono) | Score display (20px circle) |

### Typography Rules

- **Section headings:** Always use `font-display`, uppercase, `letter-spacing: 0.1em`, `font-weight: 700`
- **Monospace data:** Use `font-mono` for scores, badges, chips, tags, metadata values
- **Body text:** Use `font-sans` at 14px for standard content
- **Gradient text:** Use `.text-gradient-forge` class for hero/brand text (cyan → purple gradient with `background-clip: text`)

---

## Animations

### Keyframe Animations

| Name | Duration | Easing | Effect | Use Case |
|------|----------|--------|--------|----------|
| `fade-in` | 400ms | `cubic-bezier(0.16, 1, 0.3, 1)` | Translate Y(10px) + fade | General entrance |
| `stagger-fade-in` | 350ms | `cubic-bezier(0.16, 1, 0.3, 1)` | Translate Y(8px) + fade | List item stagger |
| `slide-in-right` | 300ms | `cubic-bezier(0.16, 1, 0.3, 1)` | Translate X(20px) + fade | Toast entrance |
| `slide-out-right` | 300ms | `cubic-bezier(0.16, 1, 0.3, 1)` | Translate X(20px) + fade out | Toast exit |
| `slide-up-in` | 200ms | `cubic-bezier(0.16, 1, 0.3, 1)` | Translate Y(6px) + fade | Subtle upward entrance |
| `scale-in` | 300ms | `cubic-bezier(0.16, 1, 0.3, 1)` | Scale(0.95) + fade | Modal/panel entrance |
| `dialog-in` | 300ms | `cubic-bezier(0.16, 1, 0.3, 1)` | Scale(0.95) + fade (centered) | Dialog entrance |
| `dropdown-enter` | 200ms | `cubic-bezier(0.16, 1, 0.3, 1)` | Scale(0.96) + Y(4px) + fade | Dropdown open (downward) |
| `dropdown-enter-up` | 200ms | `cubic-bezier(0.16, 1, 0.3, 1)` | Scale(0.96) + Y(-4px) + fade | Dropdown open (upward) |
| `dropdown-exit` | 150ms | `cubic-bezier(0.4, 0, 1, 1)` | Scale(0.96) + Y(4px) + fade out | Dropdown close (downward) |
| `dropdown-exit-up` | 150ms | `cubic-bezier(0.4, 0, 1, 1)` | Scale(0.96) + Y(-4px) + fade out | Dropdown close (upward) |
| `section-expand` | 300ms | `cubic-bezier(0.16, 1, 0.3, 1)` | Max-height 0→500px + fade | Collapsible section |
| `copy-flash` | 600ms | `ease-out` | Green flash (`#22ff88`) | Copy-to-clipboard feedback |
| `shimmer` | 1500ms | `ease-in-out` (infinite) | Horizontal gradient sweep | Skeleton loading |
| `gradient-flow` | varies | linear (infinite) | Background position cycle | Animated gradient backgrounds |
| `status-pulse` | 3s | `ease-in-out` (3 iterations) | Green background pulse | Status dot indicators |
| `forge-spark` | varies | ease (infinite) | Yellow flash + scale(1.2) + rotation | Forge action sparks |

### Animation Conventions

- **Primary easing:** `cubic-bezier(0.16, 1, 0.3, 1)` — used for all entrances (spring-like overshoot)
- **Exit easing:** `cubic-bezier(0.4, 0, 1, 1)` — used for exits (accelerate out)
- **Fill mode:** `forwards` for one-shot animations, `both` for staggered
- **Reduced motion:** All animations collapse to `0.01ms` duration via `@media (prefers-reduced-motion: reduce)`

### Transition Timing

Hover and structural transitions use a separate timing system from keyframe animations.

| Duration | Easing | Use Case |
|----------|--------|----------|
| 150ms | `ease` | Micro-interactions: icon color, text color, tiny state flips |
| 200ms | `ease` / `cubic-bezier(0.16, 1, 0.3, 1)` | Standard hover: border-color, background, text-color, button states |
| 300ms | `ease` | Structural changes: focus rings, border-color + background on inputs, card reveals |
| 500ms | `ease` | Progress bar fills, complex container transitions |

**Multi-property transitions** always animate together in a single declaration. Never stagger `border-color` separately from `background-color` — they move as one:

```css
transition: border-color 0.3s ease, background-color 0.3s ease;           /* card-hover */
transition: background-color 0.15s, color 0.15s, border-color 0.15s; /* buttons */
transition: all 0.2s ease;                                           /* prompt-card */
transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);                 /* iteration timeline */
```

---

## Component Patterns

### Glass Effects

```css
/* Standard glass panel */
.glass {
  background: color-mix(in srgb, var(--color-bg-secondary) 92%, transparent);
}

/* Semi-transparent card */
background: color-mix(in srgb, var(--color-bg-card) 50%, transparent);

/* Delete confirmation bar */
background: color-mix(in srgb, var(--color-bg-card) 98%, var(--color-neon-red));
backdrop-filter: blur(8px);
```

### Button Styles

| Variant | Class | Background | Text | Border |
|---------|-------|------------|------|--------|
| Primary | `.btn-primary` | Transparent → `rgba(168, 85, 247, 0.1)` on hover | neon-purple | `1px solid neon-purple` |
| Outline Primary | `.btn-outline-primary` | `rgba(0, 229, 255, 0.05)` | neon-cyan | `rgba(0, 229, 255, 0.2)` |
| Outline Secondary | `.btn-outline-secondary` | Transparent | text-secondary | border-subtle |
| Outline Danger | `.btn-outline-danger` | `rgba(255, 51, 102, 0.05)` | neon-red | `rgba(255, 51, 102, 0.2)` |
| Ghost | `.btn-ghost` | Transparent | Inherited | None |
| Icon | `.btn-icon` | Transparent | text-dim → text-primary on hover | None |
| Icon Danger | `.btn-icon-danger` | Transparent | neon-red (50% → 100% on hover) | `rgba(255, 51, 102, 0.1)` |

**Primary button interaction:**
- Hover: `translateY(-1px)` + sharp neon border
- Active: `translateY(0)` + muted neon border
- Disabled: `opacity: 0.4`, `cursor: not-allowed`

### Card Patterns

| Pattern | Class | Border Radius | Effect |
|---------|-------|---------------|--------|
| Card hover outline | `.card-outline` | Inherited | Cyan border contour on hover |
| Card top outline | `.card-top-outline`| Inherited | Cyan gradient line at top on hover |
| Prompt card | `.prompt-card` | 12px | Background shift + sharp cyan border on hover |
| Project header | `.project-header-card` | 16px | Cyan-to-purple gradient line at top on hover |
| Sidebar card | `.sidebar-card` | Inherited | 2px left accent border on hover/focus |

### Chips & Badges

| Variant | Class | Border Radius | Font | Size |
|---------|-------|---------------|------|------|
| Chip (pill) | `.chip` | 9999px | Geist Mono | 10px |
| Chip (rect) | `.chip.chip-rect` | 6px | Geist Mono | 10px |
| Badge | `.badge` | 6px | Geist Mono | 10px |
| Badge (small) | `.badge-sm` | 9999px | Geist Mono | 9px |
| Tag chip | `.tag-chip` | 9999px | Geist Mono | 10px |

**Tag chip colors:** neon-green at 60% opacity, with green-tinted background and border.

### Input Fields

| Pattern | Class | Focus Effect |
|---------|-------|-------------|
| Standard input | `.input-field` | Cyan border + sharp cyan contour |
| Select field | `.select-field` | Cyan border + sharp cyan contour |
| Context input | `.ctx-input` | Green border + sharp green contour |

### Score Circles

```css
.score-circle {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  box-shadow: inset 0 0 0 1.5px currentColor;
  background: color-mix(in srgb, currentColor 8%, transparent);
}
```

Small variant (`.score-circle-sm`): 20px, 10px font (same as standard in compact layout).

### Strategy Bar (Premium Glass)

```css
.strategy-bar-primary {
  box-shadow:
    inset 0 1px 0 0 rgba(255, 255, 255, 0.14),
    inset 0 -1px 0 0 rgba(0, 0, 0, 0.2),
    inset 0 0 0 1px var(--bar-accent);
  /* ::after pseudo-element adds top-half highlight gradient */
}
```

### Pipeline Timeline

- **Node:** 12px circle, `z-index: 1`
- **Connector:** 2px wide vertical line with gradient from `--pipeline-color-from` to `--pipeline-color-to`
- **Finding highlight:** 6px border-radius, tinted background with 5% opacity of highlight color, 1px box-shadow ring at 20%

### Sidebar Tabs (Pill Segment Control)

- Container: 8px radius, `color-mix(var(--color-bg-hover) 40%, transparent)`, 2px padding
- Tab: 6px radius, 11px font, 600 weight
- Active tab: `color-mix(var(--color-neon-cyan) 8%, transparent)` with sharp cyan border

---

## Absolute Edge & Neon System

**STRICT DIRECTIVE: There will be absolutely no "glow" effects or diffuse shadows anywhere in the UI.** No drop-shadows, no text-shadow blooms, no soft box-shadow radii.

The aesthetic relies exclusively on **clean, flat neon effects**—much like the crisp, bent glass of an "Iguana Bar" neon sign. Shadows and soft blooms are not only computationally taxing for budget setups, but they also cheapen the polished cyberpunk aesthetic and make the interface look muddy. Emulate hardware precision.

### Contour Intensity Tiers

Depth and interaction are communicated purely by solid border color shifts, border thickness, and bright background tints.

| Tier | Visual Cue | Use Case |
|------|-------------|----------|
| Micro | 1px border shift | Status dots, switch thumbs, sidebar tab active state |
| Small | 1px color border + faint inset background | Button hover, header toggles |
| Medium | 1px solid neon + opaque background (`/12`) | Focus states, recommendation buttons |
| Large | Sharp `inset 0 0 0 1px` inner contour | Card hover, prompt card focus |
| Hero | Pure solid vector highlighting + lift | Primary button resting/hover state |

### Inset Contours (Active States)

Instead of radiating shadows, active states use crisp pixel-perfect inset rings.

```css
/* Active timeline item */
box-shadow: inset 0 0 0 1px rgba(0, 229, 255, 0.4);

/* Strategy bar premium glass — 3-layer rigid inset */
box-shadow:
  inset 0 1px 0 0 rgba(255, 255, 255, 0.14),   /* top highlight */
  inset 0 -1px 0 0 rgba(0, 0, 0, 0.2),         /* bottom rim */
  inset 0 0 0 1px var(--bar-accent);           /* color border */
```

### Elevation Without Shadows

DO NOT use `0 10px 15px rgba(...)`. Objects elevate via background opacity/lightness shifts and overlapping sharp borders, never via soft ambient occlusion.

```css
/* Card Elevation */
border: 1px solid var(--color-border-subtle);
background: color-mix(in srgb, var(--color-bg-card) 98%, white 2%);

/* Primary button — physical elevation without bloom */
transform: translateY(-2px);
border: 1px solid var(--color-neon-cyan);
```

---

## Border Radius System

6-tier system aligned to ultra-compact dashboard density.

| Tier | Radius | Token | Use Cases |
|------|--------|-------|-----------|
| Micro | `4px` | `rounded` | Forge action buttons, inline micro-controls |
| XS | `6px` | `rounded-md` | Badges, skeleton, sidebar tabs, prompt content wells, iteration items, sidebar action buttons |
| Small | `8px` | `rounded-lg` | Buttons, input fields, cards, panels, project header, prompt cards, filter bar, version panel |
| Medium | `10px` | `rounded-[10px]` | Primary CTA button, collapsible section content |
| Large | `12px` | `rounded-xl` | Dialog/modal containers, pipeline progress (rare, hero-level only) |
| Full | `9999px` | `rounded-full` | Chips, badges, tag chips, pills |

**Convention:** Border radius increases with visual importance. Most cards and panels use 8px (Small). Interactive micro-controls use 4-6px. 10px+ is reserved for CTA buttons and rare hero containers. Pill shapes use full rounding.

---

## Opacity Tiers

Standardized opacity values used across backgrounds, borders, and text.

### Background Opacity

| Tailwind Modifier | Opacity | Use Case |
|-------------------|---------|----------|
| `/5` | 5% | Faint tints (finding highlights) |
| `/6` | 6% | Resting button background, tag chip bg |
| `/8` | 8% | Active tab, light chip, score circle bg |
| `/10` | 10% | Standard button background (outline variants) |
| `/12` | 12% | Selected/active states, template chip active |
| `/15` | 15% | Hover backgrounds, filter active state |
| `/20` | 20% | Strong hover (button bg intensification) |

### Border Opacity

| Tailwind Modifier | Opacity | Use Case |
|-------------------|---------|----------|
| `/10` | 10% | Faint borders (danger icon resting) |
| `/12` | 12% | Tag chip border |
| `/15` | 15% | Card hover borders |
| `/20` | 20% | Outline button borders, accent borders |
| `/25` | 25% | Hover border intensification |
| `/30` | 30% | Input focus borders, strong accent borders |

### Text Opacity

| Tailwind Modifier | Opacity | Use Case |
|-------------------|---------|----------|
| `/50` | 50% | Danger icon resting text, placeholder mixing |
| `/60` | 60% | Dimmed neon text (secondary task types, tag chips) |
| `/70` | 70% | Dimmed task type variants (legal, education) |
| `/80` | 80% | Near-full neon text |
| `/90` | 90% | High complexity text (neon-red) |

**Pattern:** Opacity increases on hover by one tier (e.g., `/10` bg → `/15` on hover, `/20` border → `/30` on hover).

---

## Hover State Recipes

Multi-property hover choreography patterns. All properties animate together — never stagger individual channels.

### Recipe A: Card Hover (Border + Background)

Used by sidebar cards (HistoryEntry, ProjectItem).

```
/* Resting */
border: 1px solid var(--color-border-subtle);
background: transparent;

/* Hover — 2 simultaneous changes */
hover:border-border-accent            /* border shifts to sharp cyan */
hover:bg-bg-hover/40                  /* background lightens */
transition: 200ms                     /* all properties together */
```

### Recipe B: Accent Button Hover (Border Contour + Background)

Used by header toggles, action buttons, outline buttons.

```
/* Resting */
bg-neon-cyan/8

/* Hover — opacity increase + sharp border appears */
hover:bg-neon-cyan/15
hover:border-neon-cyan
transition: 200ms
```

### Recipe C: Chip/Filter Hover (Border + Text Brightening)

Used by template chips, filter chips, context fields.

```
/* Resting */
border-border-subtle text-text-dim

/* Hover — border takes accent color, text brightens */
hover:border-neon-green/25
hover:text-neon-green/80
transition: 200ms
```

### Recipe D: Full Contrast Hover (Border + Background + Text)

Used by recommendation buttons, insight actions — the most elaborate hover.

```
/* Resting */
border-neon-yellow/20 bg-neon-yellow/[0.06] text-neon-yellow/80

/* Hover — all 3 channels intensify to flat neon */
hover:border-neon-yellow
hover:bg-neon-yellow/[0.12]
hover:text-neon-yellow
transition: 200ms
```

### Recipe E: Lift Hover (Transform + Border)

Used only by `.btn-primary`.

```
/* Hover — physical lift + sharp neon border */
hover:translateY(-1px)
hover:border-neon-cyan

/* Active — settle back */
active:translateY(0)
active:border-neon-cyan/50
transition: 250ms cubic-bezier(0.16, 1, 0.3, 1)
```

---

## Spacing System

### Padding Scale

| Value | Pixels | Use Case |
|-------|--------|----------|
| `p-1.5` | 6px | Sidebar cards, compact list items, prompt card content |
| `p-2` | 8px | Standard cards, panels, project header, filter bar, action groups |
| `p-2.5` | 10px | Dialog content, form sections, collapsible section content |
| `p-3` | 12px | Larger content areas (max common padding) |
| `p-4` | 16px | Hero sections, pipeline progress (rare) |

### Gap Scale

| Value | Pixels | Use Case |
|-------|--------|----------|
| `gap-1` | 4px | Icon + text tight pairs, status indicators |
| `gap-1.5` | 6px | Icon-label combinations, metadata separators |
| `gap-2` | 8px | Button groups, small section spacing, dialog actions |
| `gap-2.5` | 10px | Insight grid items, medium sections |
| `gap-3` | 12px | Card internal sections, header layout |
| `gap-4` | 16px | Pipeline entries, major layout divisions |

### Vertical Rhythm

| Class | Pixels | Use Case |
|-------|--------|----------|
| `space-y-1` | 4px | Tight lists (metadata lines) |
| `space-y-1.5` | 6px | Sidebar list items (history, projects) |
| `space-y-2` | 8px | Section stacking, form field groups |
| `space-y-3` | 12px | Card groups, major section stacking |
| `space-y-4` | 16px | Page-level section separation |

---

## Icon Sizing

6-tier system matching element importance.

| Size (px) | Use Cases |
|-----------|-----------|
| 10 | Inline validation icons, clear/close buttons in compact contexts |
| 12 | Button icons, action icons, chevrons, copy/edit/delete |
| 13 | Search icons, provider selector icons |
| 14 | Navigation icons, sidebar toggle, header actions |
| 16 | Large action icons, checkmarks, info/help icons |
| 24 | Empty state illustrations, hero icons |

**Convention:** Icons inherit color from their parent text class. Never hardcode icon colors — use `text-text-dim`, `text-neon-cyan`, etc.

---

## Z-Index Layering

9-layer stacking system from base content to accessibility escape hatches.

| Z-Index | Layer Name | Elements |
|---------|-----------|----------|
| 0 | Base | Main content, cards at rest |
| 1 | Elevated | Pipeline nodes (above connector line), sidebar cards on hover |
| 2 | Card overlay | Delete confirmation bars on sidebar cards |
| 10 | Sidebar overlay | Hover action menus on sidebar cards |
| 20 | Confirm overlay | Final delete confirmation buttons |
| 30 | Sticky | Header bar (sticky top) |
| 50 | Modal | Dialog overlays, select dropdown content, tooltip content |
| 100 | Popover | Popover content (above selects) |
| 9999 | Emergency | Skip link (accessibility focus target) |

**Convention:** Content layers (0–2) for in-flow elements. UI layers (10–30) for sticky/overlay chrome. Modal layers (50–100) for focus-trapping surfaces. Never use arbitrary z-index values outside this scale.

---

## Color-Mix Patterns

`color-mix(in srgb, ...)` is the primary tool for dynamic tinting — preferred over hardcoded `rgba()` when mixing with CSS variables.

### Standard Recipes

```css
/* Glass panel — 92% surface, 8% transparent */
color-mix(in srgb, var(--color-bg-secondary) 92%, transparent)

/* Semi-transparent card — 50% surface */
color-mix(in srgb, var(--color-bg-card) 50%, transparent)

/* Accent-tinted surface — 98% surface + 2% accent color */
color-mix(in srgb, var(--color-bg-card) 98%, var(--color-neon-red))

/* Depth well — mix two surfaces for inset effect */
color-mix(in srgb, var(--color-bg-primary) 60%, var(--color-bg-card))

/* Dynamic accent border (hover) — accent at 25% */
color-mix(in srgb, var(--toggle-accent, var(--color-text-dim)) 25%, transparent)

/* Dimmed placeholder text — 50% of dim color */
color-mix(in srgb, var(--color-text-dim) 50%, transparent)

/* Tag chip hierarchy — color at 6%/12%/60% for bg/border/text */
color-mix(in srgb, var(--color-neon-green) 6%, transparent)   /* background */
color-mix(in srgb, var(--color-neon-green) 12%, transparent)  /* border */
color-mix(in srgb, var(--color-neon-green) 60%, transparent)  /* text */
```

**When to use `color-mix` vs Tailwind opacity modifiers:** Use `color-mix` in CSS custom properties and `app.css` class definitions where you need to mix with CSS variables. Use Tailwind `/N` modifiers (e.g., `bg-neon-cyan/10`) in component markup for static opacity on known colors.

---

## Scrollbar

```css
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(0, 229, 255, 0.2); border-radius: 999px; }
::-webkit-scrollbar-thumb:hover { background: rgba(0, 229, 255, 0.5); }

/* Firefox */
scrollbar-width: thin;
scrollbar-color: rgba(0, 229, 255, 0.2) transparent;
```

---

## Selection

```css
::selection {
  background: rgba(0, 229, 255, 0.2);
  color: #fff;
}
```

---

## Voice & Tone

### Writing Principles

| Principle | Do | Don't |
|-----------|-------|--------|
| Be technical | "Scored 8.2/10 on clarity" | "Your prompt is pretty clear!" |
| Be confident | "Optimized using Chain of Thought" | "We tried to improve your prompt..." |
| Be concise | "Forge" (button label) | "Click to optimize your prompt" |
| Be precise | "4-stage pipeline: Analyze, Strategy, Optimize, Validate" | "Our AI will make your prompt better" |

### Terminology

| Use | Avoid |
|-----|-------|
| Forge / Optimize | Submit / Process |
| Strategy | Method / Technique |
| Pipeline | Workflow / Steps |
| Score (1-10) | Rating / Grade |
| Prompt | Query / Input |

---

## Accessibility

### Focus Rings

```css
:focus-visible {
  outline: 1px solid rgba(0, 229, 255, 0.3);
  outline-offset: 2px;
}
```

### Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

### Screen Reader Support

```css
.sr-only {
  position: absolute;
  width: 1px; height: 1px;
  padding: 0; margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}
```

### Skip Link

- Hidden off-screen by default, slides into view on focus
- Styled with `bg-card`, cyan border, 8px radius
- Focus: `top: 8px` with `outline: 2px solid rgba(0, 229, 255, 0.6)`

---

## Contact

| Purpose | Contact |
|---------|---------|
| Brand inquiries | brand@zenresources.net |
| General support | support@zenresources.net |
| Legal matters | legal@zenresources.net |
| Security issues | security@zenresources.net |
