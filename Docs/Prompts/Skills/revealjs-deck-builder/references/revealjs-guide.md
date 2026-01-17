# Reveal.js Guide

## Slide Structure
- Each `<section>` is a slide.
- Nested `<section>` blocks create vertical stacks.

Example:
```html
<section>
  <h2>Section Title</h2>
  <p>Intro text</p>
</section>
<section>
  <section><h2>Vertical Slide A</h2></section>
  <section><h2>Vertical Slide B</h2></section>
</section>
```

## Templates
- Title slides: `assets/title-slide-minimal.html`, `assets/title-slide-hero.html`
- Section separators: `assets/section-separator-minimal.html`, `assets/section-separator-kicker.html`
- Vertical stacks: `assets/vertical-stack-2.html`, `assets/vertical-stack-3.html`
- Agenda: `assets/agenda-slide-minimal.html`
- Metrics: `assets/metrics-slide.html`
- CSS helpers: `assets/custom.css`

## Fragments
- Add `class="fragment"` to reveal items step-by-step.
- Use `data-fragment-index` to control order.
- Common fragment styles: `fade-in`, `fade-out`, `grow`, `shrink`, `strike`,
  `highlight-red`, `highlight-green`, `highlight-blue`.

Example:
```html
<ul>
  <li class="fragment">Point one</li>
  <li class="fragment" data-fragment-index="2">Point two</li>
  <li class="fragment" data-fragment-index="3">Point three</li>
</ul>
```

## Speaker Notes
```html
<aside class="notes">Detail for presenter view.</aside>
```

## Themes and Custom CSS
- Theme CSS path: `assets/reveal/theme/<theme>.css`.
- Supported themes: black, white, league, beige, sky, night, serif, simple,
  solarized, blood, moon, dracula.
- Put custom styles in `assets/custom.css` and link it from `index.html`.

## Bundle Layout (ZIP)
```
presentation.zip
├── index.html
├── LICENSE.revealjs.txt
├── NOTICE.revealjs.txt
└── assets/
    ├── custom.css
    └── reveal/
        ├── reveal.css
        ├── reveal.js
        ├── theme/
        │   └── black.css
        └── plugin/
            └── notes/
                └── notes.js
```

Optional plugin assets (if used):
```
assets/reveal/plugin/markdown/marked.js
assets/reveal/plugin/markdown/markdown.js
assets/reveal/plugin/highlight/highlight.js
assets/reveal/plugin/highlight/monokai.css
assets/reveal/plugin/zoom/zoom.js
```

## Settings Snippet
```json
{
  "hash": true,
  "slideNumber": true,
  "transition": "fade"
}
```

## Markdown Plugin
Include local plugin assets in `index.html`:
```html
<script src="assets/reveal/plugin/markdown/marked.js"></script>
<script src="assets/reveal/plugin/markdown/markdown.js"></script>
```

Inline markdown slide:
```html
<section data-markdown>
  <textarea data-template>
## Slide Title

- Bullet one
- Bullet two
  </textarea>
</section>
```

Initialize with:
```js
settings.plugins = [ RevealNotes, RevealMarkdown ];
```

## Highlight Plugin
Include local plugin assets and a CSS theme:
```html
<link rel="stylesheet" href="assets/reveal/plugin/highlight/monokai.css">
<script src="assets/reveal/plugin/highlight/highlight.js"></script>
```

Code block:
```html
<pre><code class="language-python">
def hello():
    print("hi")
</code></pre>
```

Initialize with:
```js
settings.plugins = [ RevealNotes, RevealHighlight ];
```

## Zoom Plugin
Include the local plugin asset:
```html
<script src="assets/reveal/plugin/zoom/zoom.js"></script>
```

Initialize with:
```js
settings.plugins = [ RevealNotes, RevealZoom ];
```

Usage: hold Alt (Option) and click to zoom.

## Optional Markdown
If you need Markdown slides, use `data-markdown` sections and include the
Reveal.js markdown plugin assets from your local `assets/reveal/plugin/markdown`
folder (if present in your Reveal.js dist).
