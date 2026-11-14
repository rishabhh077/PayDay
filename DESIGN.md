---
name: PayDay
description: Late-invoice reminders for freelancers, drawn as a flat guide map.
colors:
  land: "#8ED462"
  sun: "#F5E211"
  coral: "#FF705D"
  sky: "#2BA0FF"
  lilac: "#EBC1FF"
  water: "#F5F1E4"
  sheet: "#FFFFFF"
  ink: "#2C2E2A"
  ink-2: "#55584F"
  placeholder: "#6B6E64"
  line: "rgb(44 46 42 / 0.14)"
  error: "#B3261E"
typography:
  display:
    fontFamily: "Bricolage Grotesque, Avenir Next, Segoe UI, sans-serif"
    fontSize: "clamp(3rem, 8vw, 6rem)"
    fontWeight: 500
    lineHeight: 0.95
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "Bricolage Grotesque, Avenir Next, Segoe UI, sans-serif"
    fontSize: "clamp(1.25rem, 2.4vw, 1.75rem)"
    fontWeight: 500
    lineHeight: 1.25
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Bricolage Grotesque, Avenir Next, Segoe UI, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 500
    lineHeight: 1.5
    letterSpacing: "-0.03em"
  body:
    fontFamily: "Bricolage Grotesque, Avenir Next, Segoe UI, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 500
    lineHeight: 1.5
  label:
    fontFamily: "Bricolage Grotesque, Avenir Next, Segoe UI, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.4
rounded:
  field: "16px"
  sheet: "22px"
  capsule: "999px"
spacing:
  gutter: "clamp(16px, 4vw, 48px)"
  control-gap: "12px"
  cell: "20px"
  section: "48px"
  headland-gap: "120px"
components:
  capsule:
    backgroundColor: "{colors.sun}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.capsule}"
    padding: "6px 6px 6px 18px"
    height: "44px"
  capsule-chip:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.sun}"
    rounded: "{rounded.capsule}"
    size: "32px"
  capsule-land:
    backgroundColor: "{colors.land}"
    textColor: "{colors.ink}"
  capsule-sky:
    backgroundColor: "{colors.sky}"
    textColor: "{colors.ink}"
  capsule-lilac:
    backgroundColor: "{colors.lilac}"
    textColor: "{colors.ink}"
  capsule-coral:
    backgroundColor: "{colors.coral}"
    textColor: "{colors.ink}"
  capsule-line:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.capsule}"
    padding: "6px 18px"
    height: "44px"
  capsule-line-hover:
    backgroundColor: "{colors.sheet}"
  tab-current:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.water}"
    rounded: "{rounded.capsule}"
    padding: "6px 18px"
  tag:
    backgroundColor: "{colors.sun}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.capsule}"
    padding: "3px 12px"
  tag-coral:
    backgroundColor: "{colors.coral}"
    textColor: "{colors.ink}"
  flash:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.water}"
    rounded: "{rounded.capsule}"
    padding: "6px 20px 6px 6px"
  sheet:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sheet}"
  input:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.field}"
    padding: "10px 16px"
    height: "48px"
---

# Design System: PayDay

## Overview

**Creative North Star: "The Guide Map"**

PayDay is drawn like the fold-out map handed over at a garden gate: cream water, one green headland, and a handful of flat-colour markers that say where to go next. The system grew from the catalog world Gardens Guide Map (`aww2-zoo-gardens-guide-map`). Every page opens on the headland, a single organic green lobe whose coast leaves the frame at the top and left. The page heading and one plain sentence sit on that land; the working data sits below it on white sheets.

Colour is flat. There are no gradients, no shadows, and no textures. Hierarchy comes from size alone, because the one typeface is set at one weight throughout. Controls are capsules, and the ones that act carry a round ink chip that slides on hover with a small overshoot. That slide is the system's only motion gesture.

Density is that of a working tool: tables and definition lists, generous row height, no cards inside cards, no metric tiles.

**Key Characteristics:**
- One green headland per page, carrying the heading and a single sentence.
- Flat colour only; depth is stated by ground colour (cream, green, white).
- One grotesk, one weight (500); scale does all the hierarchy work.
- Capsule controls with a round ink chip on the travelling edge.
- White sheets with a 22px corner hold tables, facts, and forms.
- Numbers are tabular everywhere money or dates appear.

## Colors

A cream ground, one land green, near-black ink, and four flat marker colours used only as capsule and tag fills.

### Primary
- **Land Green** (`land`): the headland lobe behind each page heading. Also the fill of the "Mark as paid" capsule and the chip in the confirmation flash. It means settled ground.

### Secondary
- **Sun Yellow** (`sun`): the default capsule and tag fill, so the main action on any screen (New invoice, Save invoice). Also the text-selection colour, and the row hover wash at 16% opacity.

### Tertiary
- **Coral** (`coral`): overdue and destructive. The Overdue count tag and the confirmed Delete capsule.
- **Sky Blue** (`sky`): the Edit capsule.
- **Lilac** (`lilac`): the Archive capsule.

### Neutral
- **Cream Water** (`water`): the page ground, and the text colour on ink fills (current tab, flash).
- **Sheet White** (`sheet`): the ground for tables, fact lists, forms, and inputs; the hover fill of outlined capsules.
- **Ink** (`ink`): all primary text, the chip, outlined capsule and input borders, the current tab fill.
- **Ink 2** (`ink-2`): secondary text on white or cream only: column heads, relative dates, descriptions, field hints, fact labels.
- **Placeholder** (`placeholder`): input placeholder text.
- **Line** (`line`): 1px row dividers inside sheets (ink at 14%).
- **Error Red** (`error`): invalid-field border and the error message under it. Appears nowhere else.

### Named Rules
**The Ink On Colour Rule.** Text on any marker colour, on the land, and on the sun is always Ink. Marker colours are fills; they are never used as text colours.

**The One Meaning Rule.** Each marker colour holds one job: sun acts, land settles, sky edits, lilac archives, coral warns. A new action picks the nearest existing meaning before a new colour is added.

## Typography

**Display Font:** Bricolage Grotesque (with Avenir Next, Segoe UI, sans-serif)
**Body Font:** the same family

**Character:** One slightly quirky grotesk does everything. Tight tracking at large sizes gives the headings their sign-painted mass; the same face at reading size stays plain and legible in tables.

### Hierarchy
- **Display** (500, clamp(3rem, 8vw, 6rem), 0.95, -0.04em, balanced wrap): the single page heading on the headland.
- **Headline** (500, clamp(1.25rem, 2.4vw, 1.75rem), 1.25, -0.02em): the one sentence under the heading, held to 30ch. Money inside it never breaks across lines.
- **Title** (500, 1.5rem, -0.03em): section headings above a sheet, optionally followed by a count tag. The brand wordmark is a sibling at 1.625rem, -0.04em.
- **Body** (500, 1.0625rem, 1.5): table cells, facts, labels, capsule text. Amounts in tables step up to 1.125rem. Empty-state copy runs at 1.25rem/1.3, max 44ch.
- **Label** (500, 0.875rem): column heads, relative dates, hints, tags. Sentence case, no tracking.

### Named Rules
**The One Weight Rule.** Everything is weight 500. Headings, `strong`, and table heads are reset to 500 and font synthesis is off. Emphasis is made with size or with Ink versus Ink 2, never with bold or italics.

**The Tabular Rule.** Any element showing money or dates uses tabular figures.

## Layout

A single centred column, max 1160px, with a fluid side gutter of clamp(16px, 4vw, 48px) and 96px of bottom padding. The top bar sits outside the column at the same gutter: wordmark, text nav, and the New invoice capsule pushed to the right.

Each page starts with the headland block (heading, sentence, and on the detail page a back capsule above the heading). The lobe behind it is an SVG path stretched to the block: it starts 220px above the block and half a viewport to the left, and extends 96px below the content. The block is followed by 120px of clear cream (112px on narrow screens) before the first control or sheet. Three coast shapes exist, one each for list, detail, and form pages.

Below the headland, sections stack: a title 48px below the previous sheet and 14px above its own. Action rows wrap with 12px gaps; the primary action sits left and the rest are pushed right. Forms are held to 640px.

At 720px and below: the text nav hides and the New invoice capsule stays; tables become stacked rows (client and amount on the first line, date and relative date on the second, description on the third) with the column heads visually hidden; fact lists drop to one column with the label above its value; the paired amount and currency fields keep two columns.

## Elevation & Depth

There is none. No box-shadow is used for depth anywhere, and there are no gradients. Depth is stated by three flat grounds: cream water, green land, white sheet. The only uses of `box-shadow` are as drawn lines: the 1.5px inset ring on outlined capsules, the 2px underline on the current nav item, and the 1px inner ring that thickens an invalid field's border.

### Named Rules
**The Flat Map Rule.** A surface is distinguished by its fill colour and its corner, never by a shadow, blur, or gradient. Hover and focus change colour or position; they do not lift.

## Shapes

Two shapes carry the system. The capsule (fully rounded, 999px) is every control, tag, and status message, and the circle is the chip inside it. The soft rectangle is every container: sheets at 22px, form fields at 16px. Nothing has a square corner.

Borders are rare and always Ink: 1.5px on inputs and outlined capsules. Sheets have no border; rows inside them are separated by a 1px Line. The headland is the one organic silhouette, a filled lobe with no outline, and it always bleeds off the top and left edges.

Icons are 16px line drawings in a 24px box, 2.4px stroke, round caps and joins, drawn in the colour of the capsule they sit on. Four exist: arrow, back arrow, plus, check.

## Components

### Buttons
Every control is a capsule: friendly, flat, and obviously pressable.
- **Shape:** fully rounded (999px), 44px minimum height, single line of text.
- **Primary:** Sun fill, Ink text, padding 6px 6px 6px 18px, with a 32px round Ink chip on the trailing edge holding an icon in the capsule's own colour.
- **Colour variants:** Land (mark as paid), Sky (edit), Lilac (archive), Coral (confirmed delete). Same shape; the chip icon takes the capsule colour.
- **Outlined:** transparent with a 1.5px inset Ink ring, no chip, padding 6px 18px. Used for lower-stakes moves (Cancel, the first Delete step, status tabs). Hover fills it Sheet White.
- **Leading chip:** for a backward move the chip sits on the leading edge and padding mirrors.
- **Hover / Focus:** the chip slides 4px in its direction of travel (0.4s, cubic-bezier(0.34, 1.56, 0.64, 1)); on press it settles to 1px and scales to 0.92. Removed under reduced motion.
- **Destructive:** Delete is two steps. An outlined Delete capsule is a disclosure that is replaced in place by a Coral "Delete this invoice" capsule.

### Chips
- **Tabs:** a row of outlined capsules with 8px gaps. The current one is filled Ink with Cream text and no ring.
- **Tags:** small capsules (3px 12px, Label size) that carry a count beside a section title. Sun by default, Coral for overdue.

### Cards / Containers
- **Corner Style:** 22px, content clipped to it.
- **Background:** Sheet White on Cream Water.
- **Shadow Strategy:** none; see Elevation & Depth.
- **Border:** none.
- **Internal Padding:** tables run edge to edge with 20px cell padding; fact lists and forms pad clamp(20px, 4vw, 36px); empty states pad 40px.
- Sheets are never nested.

### Tables
Fixed layout, tabular figures. Column heads are Label size in Ink 2; rows are 15px 20px with a 1px Line above each. Amounts are right-aligned and never wrap. The whole row is the link to the invoice: the client name's link stretches over the row, the row washes Sun at 16% on hover, and keyboard focus draws the ring on the row, inset.

### Fact list
Label and value pairs in two columns (label in Ink 2, sized to content), 14px vertical padding, a 1px Line between rows and none above the first.

### Inputs / Fields
- **Style:** Sheet White, 1.5px Ink border, 16px corner, 48px minimum height, padding 10px 16px, tabular figures. The label sits above at Body size with 6px gap; an optional hint follows it inline at Label size in Ink 2.
- **Focus:** the global focus ring at 2px offset, keeping the 16px corner.
- **Error:** border turns Error Red and thickens by a 1px inner ring; the message sits 6px below in Error Red at 0.9375rem and is tied to the field with `aria-describedby`.
- Fields stack 22px apart.

### Navigation
A plain bar: wordmark, text links at Body size with no underline, and the primary capsule at the far right. The current and hovered link take a 2px Ink underline. On narrow screens the text links hide.

### Flash
A confirmation is an Ink capsule with Cream text and a leading Land chip holding an Ink check, sized to its text, above the headland block. It uses `role="status"`.

### Headland (signature)
The green lobe behind each page's heading and sentence. One per page, behind content, decorative and hidden from assistive tech. Choose one of the three existing coasts by page type before drawing a new one.

## Do's and Don'ts

### Do:
- **Do** open every page on a headland with one Display heading and one Headline sentence, then leave 120px of cream before the working content.
- **Do** make every control a capsule at 44px minimum height; give forward actions a trailing Ink chip and backward moves a leading one.
- **Do** set all text at weight 500 in Bricolage Grotesque and build hierarchy from the five sizes in the ramp.
- **Do** keep text on Sun, Land, Coral, Sky, and Lilac in Ink.
- **Do** put tables, fact lists, and forms on a white sheet with a 22px corner.
- **Do** use tabular figures for money and dates.
- **Do** keep the chip slide as the only animated gesture and switch it off under reduced motion.

### Don't:
- **Don't** add shadows, gradients, blurs, or textures; a surface is its flat fill.
- **Don't** introduce a second weight, an italic, or a second typeface.
- **Don't** use a marker colour as text, or Ink 2 on anything but white or cream.
- **Don't** nest a sheet inside a sheet or square off a corner.
- **Don't** place more than one headland on a page or let it float clear of the top and left edges.
- **Don't** give a marker colour a second meaning; coral stays for overdue and delete.

## Open items

Recorded as work owed, not as rules.

- The typeface loads from Google Fonts. It should be self-hosted so the app runs with no external services.
- The focus ring is a 3px Ink outline at 3px offset. It was moved from Sky to Ink after Sky measured under 3:1 on cream, white, and the land. Sky no longer marks focus.
