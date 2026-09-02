# Traqo — Master Design System

> Page-specific files under `design-system/pages/` may add constraints but may not reintroduce color accents, neumorphism, or permanent per-task tools.

**Product:** local document and roadmap workspace  
**Direction:** flat monochrome minimalism  
**Density:** 8/10  
**Motion:** 2/10

## Tokens

| Role | Value |
|---|---|
| Canvas | `#FFFFFF` |
| Subtle surface | `#F7F7F5` |
| Hover/selected | `#F1F1EF` |
| Foreground | `#191919` |
| Secondary text | `#5F5E5B` |
| Tertiary text | `#787774` |
| Border | `#E9E9E7` |
| Strong border | `#D3D3D1` |
| Destructive | `#B42318` |
| Success | `#287A49` |

- Font: local system sans; monospace only for code/counters.
- Spacing: 4px base; dense, readable document rhythm.
- Radius: 4px controls, 6px menus, 8px panels.
- Shadow: none except `0 8px 24px rgba(15,15,15,.12)` on floating menus.
- Focus: 2px solid `#191919` with 2px offset.
- Brand: flat black `T + terminal dot` vector inside one rounded document frame; pair with the Traqo text wordmark and never add color, depth, or animation.

## Interaction rules

1. Preserve imported hierarchy instead of flattening text.
2. Reveal task tools through an inline `+` inserter.
3. Keep notes, counters, bookmarks, revision, and revisit as optional persistent blocks.
4. Use neutral fills and typography for state; no blue or orange accents.
5. Keep large roadmaps navigable through index, focus mode, search, and progress.
6. All critical actions remain reachable by keyboard and touch.

## Components

- Primary button: black fill, white label, 6px radius.
- Secondary button: white/transparent, neutral border, black label.
- Card/panel: white with a hairline; no lift on hover.
- Input: persistent label, white surface, neutral border, visible black focus outline.
- Task: checkbox + title + optional blocks; block controls never appear by default.
- Menu: white floating surface, one restrained shadow, icon/name/description per item.

## Motion

120–180ms opacity/background transitions only. Menu may scale from `.98`. Disable nonessential motion under `prefers-reduced-motion`.

## Anti-patterns

- Neumorphism, glass, gradients, colored action accents.
- Repeated revision/revisit controls on every task.
- Pills for ordinary metadata.
- Hover lift, bouncing, scroll reveals, or decorative animation.
- Placeholder-only inputs, invisible focus, or hover-only critical controls.

## Verification

- 360, 768, 1024, and 1440px.
- Keyboard menu and form navigation.
- 200% zoom and reduced motion.
- No page-level horizontal scroll.
- No console errors; lint, build, and backend tests pass.
