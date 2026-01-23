# COMPONENTS KNOWLEDGE BASE

**Generated:** 2026-01-22 04:35:26 EST
**Commit:** 35260ea
**Branch:** master

## OVERVIEW
Feature components for search, cards, charts, and modal workflows. Each component has a paired CSS file in this directory.

## WHERE TO LOOK
| Component | File | Notes |
|----------|------|-------|
| PlayerSearch | frontend/src/components/PlayerSearch.jsx | Autocomplete search + dropdown |
| EnhancedCard | frontend/src/components/EnhancedCard.jsx | Projection, flags, and context |
| PerformanceChart | frontend/src/components/PerformanceChart.jsx | Recharts trend chart |
| PulseButton | frontend/src/components/PulseButton.jsx | Fetches Pulse + opens modal |
| PulseModal | frontend/src/components/PulseModal.jsx | Renders Gemini analysis |
| FlagsBrowser | frontend/src/components/FlagsBrowser.jsx | Trends/flags modal |
| ComparisonView | frontend/src/components/ComparisonView.jsx | Comparison modal + API call |
| ComparisonResult | frontend/src/components/ComparisonResult.jsx | Winner/result rendering |
| PlayerSlot | frontend/src/components/PlayerSlot.jsx | Slot search for comparison |

## CONVENTIONS
- CSS is colocated with the component name (e.g., `PulseModal.jsx` + `PulseModal.css`).
- Modals render via `createPortal(..., document.body)`.
- Components expect backend response shapes (player, projection, flags).

## ANTI-PATTERNS (THIS PROJECT)
- None documented.

## NOTES
- Emoji icons are used inline for quick visual affordances.
