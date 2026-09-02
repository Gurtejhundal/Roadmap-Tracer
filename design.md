# Design System — Traqo Document Workspace

## Product intent

Traqo turns unstructured plans into living, editable roadmaps. It must work equally well for an 18-day study plan, a Docker checklist, a reading queue, or a long personal project. The interface should feel like a focused document editor: content first, tools revealed in context, and no repeated controls that the user did not ask for.

The visual language is inspired by the clarity and progressive disclosure of modern document tools. It is not a pixel copy of Notion.

## Direction

- Style: flat monochrome utility UI.
- Palette: white, warm neutral grays, and near-black only for primary product UI.
- Density: 8/10. Long roadmaps must remain scannable without becoming cramped.
- Motion: 2/10. Opacity and background transitions only.
- Elevation: borders and surface contrast; shadows are limited to floating menus.
- Content hierarchy: roadmap → section → task → optional blocks.

## Principles

1. A task starts simple. Notes, counters, bookmarks, revision tracking, and other blocks appear only after insertion.
2. Imported structure remains structure. Headings become sections, table rows become tasks, supporting cells become properties or blocks, and prose/callouts do not become fake tasks.
3. Large roadmaps use progressive disclosure: index first, one focused section when needed, search always available.
4. Controls stay near the content they affect and expose text labels in menus.
5. The same interaction model applies to roadmaps and ordinary task lists.

## Foundations

### Color

- Canvas: `#FFFFFF`
- Sidebar/subtle surface: `#F7F7F5`
- Hover/selected surface: `#F1F1EF`
- Strong text: `#191919`
- Secondary text: `#5F5E5B`
- Tertiary text: `#787774`
- Hairline: `#E9E9E7`
- Strong border: `#D3D3D1`
- Inverse action: `#191919` on `#FFFFFF`
- Destructive text: `#B42318`; destructive surface: `#FFF4F2`
- Success: `#287A49`; never the only completion indicator.

No blue or orange UI accents. Product controls and brand artwork stay monochrome.

### Brand mark

- The Traqo mark preserves the original `T + terminal dot` idea as flat black vector geometry inside a single rounded document frame.
- Use the SVG mark with the `Traqo` text wordmark; do not rasterize, add gradients, shadows, or dimensional effects.
- The navigation link provides the accessible brand name. The mark is decorative in that lockup and must not be announced twice.
- Minimum rendered mark size: 24px. Keep at least 25% of the mark width as clear space around standalone uses.

### Typography

- Interface and document text: `Inter`, `ui-sans-serif`, `-apple-system`, `BlinkMacSystemFont`, `"Segoe UI"`, sans-serif.
- Code and counters: `"SFMono-Regular"`, Consolas, monospace.
- Page title: `clamp(1.75rem, 4vw, 2.5rem)`, 700, `-0.035em`.
- Section title: `1.05rem`, 650.
- Body/task: `0.95rem`, 400–550.
- Metadata: `0.75rem`, 500.
- No remote font dependency.

### Geometry and spacing

- Base spacing: 4px; scale: 4, 8, 12, 16, 20, 24, 32, 48.
- Document width: 900px; wide roadmap shell: 1280px.
- Controls: 32–36px desktop; 42px minimum touch target on coarse pointers.
- Radius: 4px controls, 6px menus, 8px major panels.
- Borders: 1px. Do not simulate depth with multiple shadows.

## Shell

- Desktop navigation is a quiet top bar with logo, Library, New, and local-state metadata.
- Page content begins immediately below the bar and uses a centered document column.
- Roadmap contents live in a flat side rail on wide screens and an accessible drawer on small screens.
- The active route uses text weight and a subtle neutral fill, not a moving indicator.

## Components

### Buttons

- Primary: near-black fill, white text, 6px radius.
- Secondary: white or transparent fill, 1px border, near-black text.
- Quiet: transparent, neutral hover background.
- Destructive: explicit label when space permits; red text plus icon.
- Pressed/selected state must include text, icon, or `aria-pressed`; color alone is insufficient.

### Inputs

- Persistent visible labels on forms.
- White background, 1px hairline, 6px radius.
- Focus: 2px near-black outline with 2px offset.
- Errors appear next to the field and in an `aria-live` region where appropriate.

### Roadmap and task rows

- Sections use a compact heading, task count, and progress text.
- A task row contains checkbox, editable title, a quiet `+` block button, and overflow actions.
- Task blocks stack beneath the title and indent to the title column.
- Imported properties render as compact labeled rows, not a wall of pills.
- Completion de-emphasizes the row but preserves readable text contrast.

### Block inserter

- The `+` button is visible on keyboard focus and pointer hover; on touch it remains visible.
- The menu lists icon, name, and concise purpose for Note, Counter, Bookmark, Revision, and Revisit.
- Inserted blocks are independently editable and removable.
- Revision and revisit are optional blocks. They are never synthesized for every task.
- Escape closes the menu; focus returns to the trigger.

### Import

- File and paste are simple source tabs in one document panel.
- The PDF flow states what will be preserved: sections, task tables, notes, links, counters, and revision metadata.
- Import progress and parsing errors are visible, truthful states.
- Ambiguous prose stays attached as a note rather than becoming a task.

## Responsive rules

- 360–767px: single document column, full-width actions, contents drawer, task actions never hover-only.
- 768–1023px: compact navigation, two-column library only when cards remain at least 280px wide.
- 1024px+: contents rail plus document; focused roadmap section stays within readable width.
- No horizontal page scroll. Wide imported metadata wraps or scrolls inside its own region.

## Motion and feedback

- Timing: 120–180ms, ease-out.
- Allowed: opacity, background color, small menu scale from `0.98` to `1`.
- Forbidden: page slides, bouncing navigation, hover lift, floating decoration, looping motion.
- Respect `prefers-reduced-motion: reduce`.
- Every async mutation shows pending or failure feedback and does not silently discard edits.

## Accessibility

- WCAG 2.2 AA text contrast.
- Logical heading order and semantic lists/buttons/forms.
- Visible `:focus-visible` outline on every interactive element.
- Icon-only controls have names; menus are keyboard-operable.
- Checkboxes and block counters expose their state in accessible text.
- 200% zoom and 360px layout retain all primary actions.

## Forbidden patterns

Neumorphic shadows, gradients, glass blur, decorative particles, oversized marketing heroes, blue/orange control accents, excessive pills, duplicate revision/revisit controls, hover-only critical actions, placeholder-only form labels, and arbitrary animation.

## Implementation map

- Global tokens/layout: `frontend/src/index.css`
- Navigation: `frontend/src/components/Navbar.jsx`
- Task block UI: `frontend/src/components/TaskBlocks.jsx`
- Library/import/editor: `frontend/src/pages`
- Roadmap scale and document interactions: `frontend/src/pages/RoadmapView.jsx`
- Parser/API persistence: `backend`

## Acceptance checklist

- [x] Supplied five-page PDF imports as meaningful sections and tasks.
- [x] Callouts, prose, and repository layout do not become garbage tasks.
- [x] Revision/revisit controls appear only when imported or inserted.
- [x] Note, Counter, Bookmark, Revision, and Revisit blocks persist after reload.
- [x] Large roadmap overview, focus, search, and navigation remain functional.
- [x] Library, import, edit, and roadmap views share one monochrome system.
- [x] Keyboard, 360/768/1024/1440px, reduced-motion, console, lint, build, and backend tests pass.
