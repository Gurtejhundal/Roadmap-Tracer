# Design System — Traqo Soft Workspace

## Product and objective

Traqo is a single-user learning roadmap workspace used for repeated, often long sessions. The redesign must make progress feel tactile and motivating while keeping imported plans, forms, task lists, and navigation immediately understandable.

## Direction

- Primary style: Neumorphism / Soft UI (70%).
- Secondary influence: Flat Design 2.0 utility UI (30%).
- Reason: progress controls, roadmap cards, and workspace navigation benefit from tactile depth. Dense roadmap content requires flatter, higher-contrast treatment.
- Main risk: low contrast and ambiguous controls. Every actionable surface therefore retains text/icon cues, strong focus rings, and adequate contrast.
- Strongest areas: shell, library cards, progress meters, source tabs, primary actions, empty states.
- Restrained areas: task rows, long-form text, editor inputs, table of contents, destructive actions.

## Principles

1. Soft depth communicates hierarchy, not decoration.
2. Raised means actionable; inset means selected, entered, or progressed.
3. Progress is the dominant brand signal.
4. Dense work remains flatter than overview screens.
5. Every state works without relying on shadow or color alone.

## Foundations

- Background/surface: `#E8EDF3`; elevated: `#EEF3F8`; inset: `#DFE5EC`.
- Text: `#243140`; secondary text: `#5D6A7A`; border: `rgba(113,130,151,.24)`.
- Brand: burnt orange `#C94E27`; hover orange `#AD3D1C`; secondary cyan `#19758A`.
- Semantic: success `#328A68`, warning `#A56A1D`, error `#B94C5B`, information `#376F9F`.
- Contrast target: WCAG 2.2 AA; shadows never carry meaning alone.
- Display/interface font: Space Grotesk. Metadata: Fira Code.
- Display: `clamp(2.5rem, 6vw, 5rem)`; H2 `2rem`; H3 `1.3rem`; body `1rem`; label `.82rem`.
- Base spacing: 4px. Scale: 4, 8, 12, 16, 24, 32, 40, 56, 72.
- Content max: 1240px. Grid: 12 columns; 20px desktop gutters, 12px mobile.
- Breakpoints: 360, 768, 1024, 1440px.
- Radii: 10px controls, 16px panels, 22px feature cards. Pills limited to status.

## Depth

- Raised: `10px 10px 24px #c6ccd4, -10px -10px 24px #fff`.
- Low raised: `5px 5px 12px #c8ced6, -5px -5px 12px #fff`.
- Inset: `inset 4px 4px 9px #cbd1d9, inset -4px -4px 9px #fff`.
- Pressed/selected: inset depth plus visible text/icon change.
- Large-area blur and backdrop filters are forbidden.

## Components and states

- Primary button: orange raised surface; darker hover; inset pressed state; white label.
- Secondary button: background-colored raised surface; orange hover text; inset active state.
- Inputs: inset surface, persistent label, orange focus ring, textual validation.
- Cards: raised 22px surface; selected cards add orange outline; progress remains inset.
- Navigation: raised rail with inset active item and icon-plus-label.
- Task rows: low raised default, visible checkbox, flatter done state.
- Disabled: reduced opacity, no lift. Loading: label plus spinner. Error/destructive: textual label plus semantic color.
- Icons: Lucide outline, 1.75–2px stroke, 16/20/24px. Icon-only actions require accessible names and 42px targets.

## Motion

- Fast 160ms; standard 240ms; ease-out.
- Hover lift is maximum 2px. Pressed state moves inward without bounce.
- Page transition uses subtle opacity only. No floating loops or decorative particles.
- `prefers-reduced-motion` disables nonessential animation.

## Accessibility

- Focus ring: 3px translucent orange with 3px offset.
- Minimum touch target: 42px.
- Semantic HTML, persistent form labels, readable errors, keyboard-operable drawers and menus.
- Color, inset shadow, or elevation is never the sole state cue.

## Responsive and page rules

- Library: three columns desktop, two tablet, one mobile. Hero action becomes full-width on mobile.
- Import: centered raised workspace panel; inset fields; source control remains two columns.
- Roadmap: contents sidebar is raised on desktop and a drawer on mobile; tasks use restrained depth.
- Editor: dense controls stay semi-flat; destructive controls use explicit labels where space allows.
- Navigation: brand/status first row and full-width navigation rail below at tablet/mobile.
- Modals/drawers: raised panels with overlay; actions remain visible without scrolling when practical.

## Forbidden patterns

Low-contrast text, unlabeled embossed controls, shadow-only selected states, glass blur, large gradients, glowing borders, excessive pills, decorative particles, hover-only critical actions, and deeply embossed long-form content.

## Implementation

- Tokens and shared styles: `frontend/src/index.css`.
- Components/pages: `frontend/src/components` and `frontend/src/pages`.
- Icons: Lucide React. Motion: Framer Motion, restrained.
- Tests: `npm run lint`, `npm run build`, and browser QA at 360, 768, 1024, 1440px.

## QA checklist

- [x] Four target widths visually tested
- [x] Keyboard navigation and focus tested
- [x] Contrast and zoom checked
- [x] Form, loading, empty, success, and error states checked
- [x] Reduced motion supported
- [x] Lint and build pass after implementation
- [x] Console clean
- [x] No horizontal overflow
- [x] Existing behavior preserved
