# Design Principles for Presentations

Merged from: anthropics/skills/pptx (color palettes, typography, layout, avoid list), claude-office-skills/pptx (html2pptx design, visual details), financial-services-plugins/pitch-deck (formatting-standards, slide hierarchy)

For complete technical details, reference the full source files in `skill-sources/`.

---

## Color Palette Selection

**Don't default to blue.** Choose colors that match the topic.

| Theme | Primary | Secondary | Accent |
|-------|---------|-----------|--------|
| Midnight Executive | `1E2761` | `CADCFC` | `FFFFFF` |
| Forest & Moss | `2C5F2D` | `97BC62` | `F5F5F5` |
| Coral Energy | `F96167` | `F9E795` | `2F3C7E` |
| Ocean Gradient | `065A82` | `1C7293` | `21295C` |
| Charcoal Minimal | `36454F` | `F2F2F2` | `212121` |
| Teal Trust | `028090` | `00A896` | `02C39A` |
| Cherry Bold | `990011` | `FCF6F5` | `2F3C7E` |
| Sage & Terracotta | `87A96B` | `E07A5F` | `F4F1DE` |
| Black & Gold | `BF9A4A` | `000000` | `F4F6F6` |

**Rules:**
- One dominant color (60-70%), 1-2 supporting, one accent
- Dark backgrounds for title + conclusion ("sandwich structure")
- Light backgrounds for content slides

## Typography

| Header Font | Body Font |
|-------------|-----------|
| Georgia | Calibri |
| Arial Black | Arial |
| Cambria | Calibri |
| Impact | Arial |

| Element | Size |
|---------|------|
| Slide title | 36-44pt bold |
| Section header | 20-24pt bold |
| Body text | 14-16pt |
| Captions | 10-12pt muted |
| Table header | 10-12pt bold |
| Table body | 9-11pt |
| Footnotes | 8-9pt italic |

**Chinese fonts**: 微軟正黑體, Noto Sans CJK TC, or available CJK font

## Layout Options

- Two-column (text + illustration)
- Icon + text rows
- 2x2 or 2x3 grid
- Half-bleed image with content overlay
- Large stat callouts (60-72pt numbers)
- Timeline or process flow

## AVOID (Common Mistakes)

- **Don't repeat the same layout** — vary across slides
- **Don't center body text** — left-align; center only titles
- **Don't default to blue** — match topic
- **Don't create text-only slides** — add visual elements
- **Don't use accent lines under titles** — hallmark of AI slides
- **Don't use low-contrast** — text AND icons need strong contrast
- **Don't forget text box padding** — set margin: 0 when aligning with shapes

## IB-Grade Standards (from pitch-deck)

- **Bullet symbols**: ✓ (included), × (excluded), • (neutral), 1.2.3. (sequence), – (sub-bullets)
- **Max density**: 6-7 bullets per box, 2 lines per bullet
- **Font consistency**: Same-level boxes MUST match font size
- **Tables**: ALWAYS actual table objects (NEVER pipe/tab text)
- **Charts**: Fill designated area completely, never thumbnail-sized
- **Footnotes**: "Sources: [Source] (Year). Notes: (1) [Note]; (2) [Note]."
