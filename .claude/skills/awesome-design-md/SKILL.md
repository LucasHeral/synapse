---
name: awesome-design-md
description: "73 curated brand DESIGN.md design system files."
version: 0.1.0
author: Hermes
metadata:
  hermes:
    tags: [Design, Design-Tokens, UI, Aesthetics, Design-Systems]
---

# Awesome DESIGN.md

A curated collection of 73 production-grade `DESIGN.md` design system files extracted from real developer-focused and high-craft websites (Linear, Raycast, Vercel, Supabase, Stripe, Mistral AI, etc.). Built on the Google Stitch DESIGN.md standard, it gives AI coding agents exact color palettes, typography scales, spacing, component architecture, and anti-slop rules.

## When to Use

- When building or redesigning a web interface and needing exact design tokens from top brands (Linear, Vercel, Apple, Stripe, etc.).
- When creating or refining a project's root `DESIGN.md` specification file.
- When pairing with `taste-skill` and `popular-web-designs` to produce ultra-premium UI without generic AI aesthetic slop.

## Prerequisites

- Access to GitHub repository `voltagent/awesome-design-md` or local cached design-md files.
- `gh` CLI configured if fetching upstream updates (`gh api repos/voltagent/awesome-design-md/contents/design-md`).

## How to Run

Query or extract design systems via the `terminal` tool using GitHub API:

```bash
gh api repos/voltagent/awesome-design-md/contents/design-md/<brand>/DESIGN.md --jq '.content' | base64 --decode
```

Read or patch local project `DESIGN.md` files using `read_file`, `write_file`, and `patch`.

## Quick Reference

| Brand | Canvas | Primary Accent | Typographic Style |
|---|---|---|---|
| **Linear** | `#010102` / `#08090a` | `#5e6ad2` (Lavender Indigo) | Inter `cv01, ss03`, negative tracking |
| **Vercel** | `#000000` / `#0a0a0a` | `#0070f3` / Monochrome | Geist Sans & Geist Mono |
| **Raycast** | `#0b0d0e` / `#131618` | `#ff6363` (Vibrant Red) | JetBrains Mono & Inter |
| **Supabase** | `#121212` / `#1c1c1c` | `#3ecf8e` (Emerald) | Circular Grotesk |
| **Stripe** | `#ffffff` / `#0a2540` | `#635bff` (Stripe Blurple) | Sohne / Source Sans 3 |
| **Mistral AI** | `#0d0f12` | `#f54e00` / `#fa5252` | Editorial Grotesk |

## Procedure

1. **Identify the Visual Language**:
   Determine the target aesthetic (e.g. Linear's near-black software-craft canvas vs Vercel's stark monochrome precision).
2. **Retrieve the Token Spec**:
   Fetch the brand's `DESIGN.md` using `gh api` or read from local templates.
3. **Drop or Update Project `DESIGN.md`**:
   Write a `DESIGN.md` at the project root defining:
   - `colors`: canvas, surfaces, borders, text, single accent.
   - `typography`: headline scales, negative tracking, monospace pairings.
   - `components`: double-bezel card structure, haptic button states, tactile interactions.
   - `rules`: em-dash ban, anti-slop restrictions, accessibility guidelines.
4. **Enforce in Implementation**:
   Check HTML/CSS against the `DESIGN.md` rules before delivering.

## Pitfalls

- **Unpackaged Repository Structure**: `voltagent/awesome-design-md` is a curated directory of markdown design systems, not a standalone single-file `SKILL.md`. Fetch individual system tokens directly via GitHub API or use pre-bundled templates.
- **Copying Entire Foreign Brand Assets**: Extract tokens, scales, and component mechanics; do not pirate proprietary logos or trademarked brand names.

## Verification

Verify available design systems in the upstream repository:

```bash
gh api repos/voltagent/awesome-design-md/contents/design-md --jq '.[].name' | grep -E "linear|vercel|raycast|supabase"
```
