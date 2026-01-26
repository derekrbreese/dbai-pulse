# Design Refresh Brief: Avoiding "AI Slop"

**Created:** 2026-01-26
**Goal:** Modernize dbAI Pulse UI to look professional, trustworthy, and distinct.

## The "AI Slop" Diagnosis
Current UI traits that read as "generic generated":
- **Excessive Glassmorphism:** `backdrop-filter: blur(24px)` everywhere. It's muddy and hard to read.
- **Unmotivated Gradients:** Borders and text using `linear-gradient` without semantic meaning.
- **Generic Glows:** `box-shadow: 0 0 40px ...` creates visual noise.
- **Floating/Drifting Layout:** Elements feel unanchored.

## Proposed Directions

### Direction 1: "The Quant Terminal" (Recommended)
*Inspiration: Linear, Bloomberg, Vercel*
- **Philosophy:** Data is beautiful. Precision over decoration.
- **Backgrounds:** Solid, deep blacks (`#050505` or `#0A0A0A`). No blur filters.
- **Borders:** Subtle, 1px solid (`#333`). No glow.
- **Typography:**
  - Headers: Inter (tight tracking).
  - Data: Geist Mono or JetBrains Mono (tabular nums).
- **Color:**
  - Monochrome base (Grays).
  - Semantic accents only (Green = Good, Red = Bad, Purple = AI).
  - High contrast white text.

### Direction 2: "The Sports Editorial"
*Inspiration: The Athletic, ESPN+, New York Times*
- **Philosophy:** Narrative and context.
- **Typography:**
  - Headers: Bold Serif (Merriweather or Playfair).
  - Body: Clean Sans.
- **Visuals:** High-quality player cutouts (if available), bold color blocks (Team colors).
- **Layout:** Magazine-style columns.

### Direction 3: "The Bento Grid"
*Inspiration: Apple, Linear (Bento)*
- **Philosophy:** Modular and organized.
- **Layout:** Strict grid of "cards".
- **Surface:** Soft gray cards (`#1A1A1A`) on black background.
- **Corner Radius:** standardized (e.g., `12px` everywhere).
- **Icons:** Consistent set (Lucide or Heroicons).

## Immediate Action Items (De-Slop)
1.  **Kill the Blur:** Remove `backdrop-filter` from cards. Use solid hex colors with 95-100% opacity.
2.  **Flatten Borders:** Replace gradient borders with solid 1px borders.
3.  **Standardize Type:** Import a high-quality font (Inter/Geist) via Google Fonts.
4.  **Fix Contrast:** Ensure all text passes WCAG AAA (as we did with the dropdown).
5.  **Grid Alignment:** Align search, cards, and charts to a strict central column or grid.
