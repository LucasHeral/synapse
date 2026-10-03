# DESIGN.md — SYNAPSE Design System Specification

> Design system specification for **SYNAPSE** (Tech Watch & Intelligence Hub).
> Conforms to the Google Stitch `DESIGN.md` standard, combining the **Linear software-craft dark canvas**, **Vercel Web Interface Guidelines**, and **Leonxlnx Taste-Skill** anti-slop directives.

---

## 1. Visual Theme & Atmosphere

SYNAPSE is an **Operate & Monitor** technical intelligence platform. The visual medium is an OLED-deep dark canvas (`#050506`) where content emerges from darkness with high-contrast typographic hierarchy and tactile machined-hardware surfaces.

### Core Philosophy
- **Machined Hardware Surfaces**: Components use the **Double-Bezel (Doppelrand)** nested architecture — an outer shell with subtle translucent borders (`rgba(255, 255, 255, 0.05)`) enclosing an inner core with an inner highlight (`shadow-[inset_0_1px_1px_rgba(255,255,255,0.09)]`).
- **Achromatic Discipline**: Near-black backgrounds with neutral silver-white text. No gratuitous rainbow gradients or "AI-purple" background meshes.
- **Single Brand Accent**: Linear Indigo (`#6366f1` / `#818cf8`) for primary CTAs and active states, paired with functional Emerald (`#10b981`) for positive sentiment and Rose (`#f43f5e`) for negative warnings.
- **Ambient Depth**: Subtle, high-dispersion radial glows (`filter: blur(80px)`) positioned at the top and bottom of the viewport to establish atmosphere without visual clutter.

---

## 2. Color Palette & Roles

```yaml
colors:
  # Background Canvas
  canvas: "#050506"
  panel: "#0b0c0e"
  surface-elevated: "#111215"
  card-inner: "#0e0f12"

  # Text & Ink
  text-hero: "#ffffff"
  text-primary: "#f2f3f5"
  text-secondary: "#9ea3ae"
  text-muted: "#656a76"

  # Borders & Dividers
  border-outer: "rgba(255, 255, 255, 0.05)"
  border-inner: "rgba(255, 255, 255, 0.08)"
  border-highlight: "rgba(255, 255, 255, 0.18)"

  # Brand & Status Accents
  brand-primary: "#6366f1"
  brand-hover: "#4f46e5"
  status-positive: "#10b981"
  status-negative: "#f43f5e"
  status-warning: "#f59e0b"
```

---

## 3. Typography Rules

### Primary Font Stack
- **Headings & Body**: `Plus Jakarta Sans` or `Inter` with OpenType `cv01, ss03` enabled globally.
- **Monospace (Data & Dates)**: `JetBrains Mono` with `font-variant-numeric: tabular-nums` for all scores, counts, dates, and technical tags.

### Typographic Hierarchy
| Role | Size | Weight | Tracking | Purpose |
|---|---|---|---|---|
| Display | 24px–32px | 700 / 800 | `-0.03em` | Main titles & entity names |
| Section Header | 14px–16px | 600 | `-0.02em` | Card & view titles |
| Body | 12px–13px | 400 | `-0.01em` | Summaries, article excerpts |
| Micro / Eyebrow | 9.5px–10px | 600 | `+0.18em` | Category tags, uppercase labels (mono) |

### Punctuation & Copy Standards (Vercel Guidelines)
- Use real horizontal ellipses (`…` / `&hellip;`) instead of three dots (`...`).
- Non-breaking spaces for shortcuts: `⌘&nbsp;K`.
- **ZERO EM-DASHES (`—`)**: strictly banned across all headlines, pills, copy, and buttons. Use regular hyphens (`-`) or colons (`:`).
- `text-wrap: balance` on all modal headers and card titles.

---

## 4. Component Architecture

### The Double-Bezel Hardware Card
```html
<div class="double-bezel-card group">
  <div class="double-bezel-inner">
    <!-- Card Content -->
  </div>
</div>
```
- Outer shell: `padding: 5px`, `border-radius: 20px`, `border: 1px solid rgba(255,255,255,0.05)`.
- Inner core: `border-radius: 15px`, `background: #0e0f12`, `box-shadow: inset 0 1px 1px rgba(255,255,255,0.09)`.

### Tactile Action Buttons
- **Primary**: Gradient indigo with specular top highlight (`inset 0 1px 1px rgba(255,255,255,0.35)`).
- **Ghost**: Subtle dark tint (`rgba(255,255,255,0.035)`) with hover elevation.
- **Haptic feedback**: `active:scale-[0.98]` on all interactive buttons.

---

## 5. Accessibility & Performance Guardrails

- **Focus rings**: Use `focus-visible:ring-1 focus-visible:ring-indigo-500` instead of bare `outline-none`.
- **Aria labels**: Every icon-only button must have an explicit `aria-label` attribute.
- **Dialogs**: All modals feature `role="dialog" aria-modal="true"` and `overscroll-behavior: contain`.
- **Async status**: Toast notifications wrapped in `aria-live="polite"` and `role="status"`.
- **Reduced motion**: `@media (prefers-reduced-motion: reduce)` short-circuits all animation durations to zero.
