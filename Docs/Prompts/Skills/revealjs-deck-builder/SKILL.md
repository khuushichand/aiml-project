---
name: revealjs-deck-builder
description: Create, edit, and package Reveal.js slide decks (HTML/JS/CSS). Use for new slide decks, improving existing Reveal.js pages, theme customization, fragment and speaker notes creation, and exporting offline ZIP bundles with local Reveal.js assets.
---

# Revealjs Deck Builder

## Overview

Build Reveal.js presentations end-to-end: outline content, generate slide markup, apply themes and fragments, and export an offline ZIP bundle with local assets.

## Workflow

1. Clarify the request: topic, audience, tone, slide count, and preferred theme.
2. Produce a deck outline: title slide, section headers, content slides, and a closing slide.
3. Build slides in HTML sections with consistent headings and concise bullet content.
4. Add fragments and speaker notes where gradual reveal or extra detail is needed.
5. Apply theme and optional custom CSS.
6. Export as an offline ZIP bundle with local Reveal.js assets and license/notice files.

## Quick Start

1. Copy `assets/index.html` and replace placeholders (`{{title}}`, `{{theme}}`, `{{settings_json}}`, `{{custom_css_link}}`). Use `<link rel="stylesheet" href="assets/custom.css">` or an empty string for `{{custom_css_link}}`.
2. Insert slide `<section>` blocks between `<!-- SLIDES_START -->` and `<!-- SLIDES_END -->`. Use optional templates in `assets/` for title/section slides.
3. Add fragments via `class="fragment"` and speaker notes via `<aside class="notes">`.
4. Place Reveal.js dist files under `assets/reveal/` and add `assets/custom.css` if needed.
5. Zip the bundle using the layout in `references/revealjs-guide.md`.

## Editing Existing Decks

When asked to improve a Reveal.js page:
- Tighten slide titles, reduce text density, and standardize heading levels.
- Move verbose content to speaker notes.
- Add fragments to reveal key points progressively.
- Keep slide structure consistent and update theme/custom CSS only when requested.

## Resources

- `references/revealjs-guide.md`: slide structure, fragments, speaker notes, themes, bundle layout, and plugin patterns.
- `assets/index.html`: starter template with placeholders and slide insertion markers.
- `assets/custom.css`: typography/layout helpers (optional starter).
- `assets/title-slide-minimal.html`: title slide variant.
- `assets/title-slide-hero.html`: title slide variant with dark background.
- `assets/section-separator-minimal.html`: section divider with title and subtitle.
- `assets/section-separator-kicker.html`: section divider with section number kicker.
- `assets/vertical-stack-2.html`: vertical stack with two slides.
- `assets/vertical-stack-3.html`: vertical stack with three slides.
- `assets/agenda-slide-minimal.html`: minimal agenda slide.
- `assets/metrics-slide.html`: metrics/data slide template.
