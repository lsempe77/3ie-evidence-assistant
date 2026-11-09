---
version: alpha
name: 3ie-evidence-assistant-design
description: "A calm research tool in 3ie navy on white. The accent appears only on the main action, links, focus and citations. Poppins for headings (3ie's brand face), Inter for everything people read and scan. Medium density: answers are read closely, so line length and spacing matter more than packing the screen."

colors:
  primary: "#153a80"        # 3ie navy, RGB value in 3ie's logo and branding guidelines (2015)
  on-primary: "#ffffff"
  primary-hover: "#0f2c63"
  primary-tint: "#eaf3fb"   # selected rows, citation chips, active nav
  highlight: "#b4d2ee"      # 3ie light blue (guidelines): cited passage highlight in the PDF viewer only
  canvas: "#ffffff"
  surface-1: "#f7f8fa"      # sidebars, page background behind cards
  surface-2: "#eef1f5"      # hover on rows, code and quote blocks
  hairline: "#e2e6ec"
  ink: "#14171f"
  ink-muted: "#4a5363"
  ink-subtle: "#6b7484"     # 4.7:1 on white, the lightest text allowed
  semantic-success: "#1e7b4f"
  semantic-warning: "#9a6700"
  semantic-danger: "#b3261e"
  semantic-info: "#153a80"

typography:
  display:  { fontFamily: Poppins, fontSize: 32px, fontWeight: 600, lineHeight: 1.2, letterSpacing: -0.4px }
  title:    { fontFamily: Poppins, fontSize: 24px, fontWeight: 600, lineHeight: 1.25 }
  heading:  { fontFamily: Poppins, fontSize: 18px, fontWeight: 600, lineHeight: 1.35 }
  body-lg:  { fontFamily: Inter, fontSize: 16px, fontWeight: 400, lineHeight: 1.6 }   # answer text
  body:     { fontFamily: Inter, fontSize: 14px, fontWeight: 400, lineHeight: 1.5 }   # UI, lists, forms
  caption:  { fontFamily: Inter, fontSize: 12px, fontWeight: 500, lineHeight: 1.4 }
  mono:     { fontFamily: "Geist Mono", fontSize: 13px, fontWeight: 400, lineHeight: 1.5 }

spacing: { unit: 4px, scale: [4, 8, 12, 16, 24, 32, 48, 64] }
radius:  { sm: 4px, md: 8px, lg: 12px, pill: 9999px }
---

# 3ie Evidence Assistant: design system

Read this before any UI work. It wins over component-library defaults. When you add a component, add
it here too. Tokens are implemented in `frontend/src/app/globals.css` (Tailwind v4 `@theme`), mapped
onto the shadcn/ui variables (`--primary`, `--background`, `--border`, …) so existing components
inherit them.

## Overview

Who uses it: researchers, evidence-synthesis teams and policy staff, mostly on a laptop, sometimes on
a phone between meetings. They ask a question about development evidence and need an answer they can
**check**. Trust comes from sources that are one click away, not from decoration.

Two decisions define the look:

1. **The answer is the product.** The Ask screen gives the answer a readable column (max 760px, 16px
   text, 1.6 line height). Every claim carries a citation chip that opens the exact passage and page.
2. **3ie navy is scarce.** It marks the main action, links, focus and citations. Everything else is
   neutral, so a navy element always means "act here" or "this is a source".

Kind: work tool for reading. Density: medium.

## Vocabulary (user-facing words)

| Say | Never say in the UI |
| --- | --- |
| Collection | RAG, RAG project, knowledge base |
| Document, study | PDF record, doc |
| Passage | Chunk, vector chunk, embedding |
| Source | Citation object, retrieval result |
| Processing documents… | MinerU, Docling, Modal, vectorisation |
| Settings | LLM configuration, temperature |

Infrastructure names (R2, Supabase, Railway, Modal, Qdrant, model IDs) belong in the admin area only.

## Colours

### Brand and accent
Source: 3ie's "Logo and branding guidelines" PDF (version 1, 8 January 2015), kept outside git. Its
RGB logos use navy #153a80 and light blue #b4d2ee. Its green (#9cb33a) appears only as an example
mid-tone background behind the logo, and the app does not use it.

`primary` (#153a80, 3ie navy) on: the one main button per view, links, the focus ring, citation chips
and the active navigation item. `primary-tint` for selected rows and chip backgrounds. `highlight`
(3ie light blue) only for the highlighted passage inside the PDF viewer. Navy is never a background
wash or a gradient.

### Logo
Files in `frontend/public/brand/`, rebuilt as vector SVG from the guidelines' RGB page:
`3ie-marque.svg` (the square "3ie" mark) and `3ie-logo-1line.svg` (mark plus "International
Initiative for Impact Evaluation"). The top bar uses the marque at 32px high, followed by "Evidence
Assistant" in Poppins. The marque is also the browser icon (`frontend/src/app/icon.svg`). Use these
versions on white or light backgrounds only. The guidelines have a reversed version with an outline
for dark backgrounds, which is not extracted yet. Never recolour, stretch or redraw the logo.

### Surface
`canvas` for the reading column and dialogs. `surface-1` for side panels and the page behind cards.
`surface-2` for row hover and quote blocks. Separate regions with `hairline` borders, not shadows.

### Text
`ink` for body and headings, `ink-muted` for secondary text and metadata, `ink-subtle` for captions
and placeholders. Nothing lighter than `ink-subtle`.

### Semantic
Success, warning and danger appear in status text, badges and destructive buttons, always with an
icon or word, never colour alone. Study-design badges (RCT, quasi-experimental, qualitative, review)
are neutral badges with text, not a rainbow.

## Typography

### Font family
Poppins (3ie's brand face) for display, titles and headings only. Inter for all UI and reading text,
with `font-variant-numeric: tabular-nums` wherever numbers sit in columns (effect sizes, counts,
years). Geist Mono for IDs and code only.

### Hierarchy
display 32 (landing hero only) / title 24 (page titles) / heading 18 (section and card titles) /
body-lg 16 (answers) / body 14 (UI) / caption 12 (metadata, badges).

### Principles
Headings name a thing ("Sources", "Documents"), not a mood. Headings use `text-wrap: balance`. Use
`…` not `...`. Sentence case for headings and buttons. British English throughout.

## Layout

### Spacing system
4px unit, steps 4, 8, 12, 16, 24, 32, 48, 64 only. Tight within a group (8–12), generous between
groups (24–32).

### Grid and container
App pages: container max 1280px, 24px side padding (16px on phones). Ask screen: three regions on
wide screens: history (256px, collapsible), answer column (fluid, max 760px), sources panel (360px).

### Whitespace philosophy
Space groups first. Add a border only where space is not enough. Never more than two boxes deep:
page, card, content.

## Elevation and depth
Hairline borders at rest. Shadows only for things that float: menus, popovers, dialogs, the mobile
drawer. Two levels: `shadow-sm` for menus and popovers, `shadow-lg` for dialogs and drawers.

## Shapes

### Border radius scale
sm 4px (badges, chips, inputs inside dense tables), md 8px (buttons, inputs, cards), lg 12px
(dialogs, drawers), pill for avatars and toggles only. Inner radius = outer radius minus padding.

## Components

### Buttons
- `button-primary`: bg primary, text on-primary, radius md, height 36px (44px on touch), padding 0 16px,
  hover primary-hover. **One per view.**
- `button-secondary`: bg canvas, text ink, 1px hairline border, same size.
- `button-ghost`: text ink-muted, no border, hover surface-2. For toolbars and icon buttons.
- `button-danger`: text semantic-danger, hairline border at rest. Destructive actions open a
  confirmation dialog that names what will be lost. No browser `alert()` or `confirm()`.
- Labels are a verb and an object: "Ask", "Upload documents", "Delete collection". Icon-only buttons
  carry an `aria-label`.

### Citation chip
Inline `[n]` in the answer: caption size, bg primary-tint, text primary, radius sm, min 20px wide.
Hover or focus shows a preview (study, page). Click opens the passage in the sources panel, and the
PDF at the exact page with `highlight` on the passage.

### Source card
In the sources panel: study title (heading), authors and year (body, ink-muted), badges for design
and country, the quoted passage (body, surface-2 block), and "Open page 12" as a link. Cards are not
nested inside another card.

### Answer block
body-lg on canvas, max 760px. Sections use heading size. Evidence-strength phrases ("3 RCTs in 2
countries") are plain text, not coloured. A quiet footer row: copy, export, "Show sources",
feedback. When the evidence is insufficient, the answer says so in a neutral info block and lists
the closest studies.

### Ask box
Single input with the placeholder naming the collection ("Ask about Poverty graduation
programmes…"), the primary "Ask" button and a settings icon button. Empty state centres it with 3–4
example questions as secondary chips. After the first answer it becomes the follow-up box at the
bottom of the answer column.

### Cards and containers
radius md, 1px hairline, padding 16–24, no shadow at rest. A clickable card lifts 1px and darkens its
border on hover. Collection cards show name, description, document count and last updated, with
"Open" as the primary action and a ghost overflow menu for the rest.

### Inputs and forms
Height 36px (44px on touch), radius md, hairline border, focus ring 2px primary with 2px offset.
Every input has a visible label. Errors appear under the field in semantic-danger with what to do.

### Navigation
Top bar on every signed-in page: the 3ie marque and "Evidence Assistant" on the left, "Collections" and
the current collection, account menu on the right. Back links say where they go ("All
collections"). Tabs inside a collection: Ask, Documents, Settings. Upload and processing live
under Documents.

### Tables and lists
Row height 40px, hairline separators, sticky header on long tables, numbers right-aligned with
tabular-nums, row hover surface-2.

### Empty, loading and error states
- Empty: what this place is for, plus one action ("No documents yet. Upload PDFs to start.").
- Loading: skeletons in the shape of the content. Answers stream in. Long steps say what is
  happening ("Searching 97 documents…", "Writing the answer…").
- Error: what went wrong and what to do next, with a retry button. Never a raw status code alone.

## Rules

### Do
- Keep one primary button per view.
- Put every claim within one click of its source and page.
- Use the vocabulary table above in all user-facing text.
- Show real numbers with tabular-nums and right alignment.
- Test every screen at 390px before calling it done.

### Avoid
- Gradients, glows, glassmorphism and emoji icons.
- Infrastructure, model names or temperatures outside the admin area.
- Cards nested inside cards.
- Colour as the only carrier of meaning.
- Motion beyond 2px of lift or longer than 250ms. Respect reduced motion.

## Responsive behaviour

### Breakpoints
390 (phone), 768 (tablet), 1024 (laptop), 1280 (wide), 1440 (desktop).

### Touch targets
44px minimum on touch devices. Primary buttons are full-width on phones.

### Collapsing strategy
- Below 1280: the sources panel becomes a "Sources" tab beside "Answer".
- Below 1024: the history sidebar becomes a drawer opened from the top bar.
- Below 768: one column. The ask box spans the width, and the top bar shows the logo, the collection
  name and the menu.
- No horizontal scrolling at any width down to 320px.

## Iteration guide
Change one screen at a time, in this order: Ask screen, collection pages (Documents, Settings),
dashboard, sign-in, landing page. Add each new component to Components with its tokens before
using it twice. Render at 1440 and 390 and check this file's rules before merging.

## Known gaps
- **Typeface.** The 2015 guidelines cover logos and colours only. Poppins comes from 3ieimpact.org's
  stylesheet and still needs confirming with 3ie's communications team.
- **Dark mode** is not designed. `globals.css` has shadcn's default dark variables. Leave dark mode
  off until it is designed.
- **Landing page.** Whether public visitors see one, or sign-in leads straight to the app, is
  undecided.
- **Charts** (effect-size plots, consensus bar) are not specified yet.
- **Multilingual layout** (long German or French labels, right-to-left scripts) is not specified.
- **Current code drift** (audit of 8 Nov 2026): fonts are Geist, colours are shadcn's neutral
  defaults, about 500 colour classes are written directly into components, 26 browser
  `alert()`/`confirm()` calls, several icon-only buttons without labels, and links wrapping buttons.
  Migrate these as each screen is redesigned.
- **Migration status** (9 Nov 2026): tokens and fonts are live in `globals.css` and `layout.tsx`.
  The Ask screen (`app/r/[ragId]`) and its workbench components follow this file. Next are the
  collection pages (Documents, Settings), then the dashboard, sign-in and landing page.
- **Example questions** on the empty Ask screen are generic. A collection should be able to set its
  own.
- **Search filters** were removed from the Ask screen because they were never sent to the API. Bring
  them back once the API applies them.
