---
name: Kautilya AI
colors:
  surface: '#f9f9ff'
  surface-dim: '#d3daea'
  surface-bright: '#f9f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f0f3ff'
  surface-container: '#e7eefe'
  surface-container-high: '#e2e8f8'
  surface-container-highest: '#dce2f3'
  on-surface: '#151c27'
  on-surface-variant: '#464553'
  inverse-surface: '#2a313d'
  inverse-on-surface: '#ebf1ff'
  outline: '#777584'
  outline-variant: '#c8c4d5'
  surface-tint: '#544fc0'
  primary: '#1f108e'
  on-primary: '#ffffff'
  primary-container: '#3730a3'
  on-primary-container: '#a9a7ff'
  inverse-primary: '#c3c0ff'
  secondary: '#4648d4'
  on-secondary: '#ffffff'
  secondary-container: '#6063ee'
  on-secondary-container: '#fffbff'
  tertiary: '#511c00'
  on-tertiary: '#ffffff'
  tertiary-container: '#752c00'
  on-tertiary-container: '#fe9562'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e2dfff'
  primary-fixed-dim: '#c3c0ff'
  on-primary-fixed: '#0f0069'
  on-primary-fixed-variant: '#3b35a7'
  secondary-fixed: '#e1e0ff'
  secondary-fixed-dim: '#c0c1ff'
  on-secondary-fixed: '#07006c'
  on-secondary-fixed-variant: '#2f2ebe'
  tertiary-fixed: '#ffdbcc'
  tertiary-fixed-dim: '#ffb694'
  on-tertiary-fixed: '#351000'
  on-tertiary-fixed-variant: '#7a3003'
  background: '#f9f9ff'
  on-background: '#151c27'
  surface-variant: '#dce2f3'
typography:
  h1:
    fontSize: 2.25rem
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  h2:
    fontSize: 1.5rem
    fontWeight: '600'
    lineHeight: '1.3'
    letterSpacing: -0.01em
  body-lg:
    fontSize: 1.125rem
    fontWeight: '400'
    lineHeight: '1.75'
  body-md:
    fontSize: 1rem
    fontWeight: '400'
    lineHeight: '1.6'
  code:
    fontFamily: monospace
    fontSize: 0.875rem
    fontWeight: '400'
    lineHeight: '1.5'
  label-sm:
    fontSize: 0.75rem
    fontWeight: '500'
    lineHeight: 1rem
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 0.5rem
  sm: 1rem
  md: 1.5rem
  lg: 2.5rem
  xl: 4rem
  container-max: 800px
---

## Brand & Style

The visual identity of this design system centers on "Intellectual Fluidity." It bridges the gap between high-utility document editing and the dynamic, reactive nature of modern LLMs. The brand persona is authoritative yet accessible—modeled after a sophisticated digital advisor.

The design style is a calibrated mix of **Minimalism** and **Glassmorphism**. We utilize the expansive whitespace and typographic rigor of minimalist design to ensure that long-form AI outputs remain the focal point. This is layered with translucent, blurred surfaces to provide a sense of depth and modernity, mimicking the "living" nature of AI intelligence. The result is a workspace that feels calm, focused, and technologically advanced.

## Colors

The palette is anchored by a sophisticated **Deep Indigo**, used strategically for primary actions and focus states to convey trust and depth. 

- **Light Mode:** Prioritizes high legibility with soft gray backgrounds (`#F9FAFB`) and pure white surfaces. This creates a "paper-like" feel for AI responses, encouraging long-form reading.
- **Dark Mode:** Replaces pure blacks with deep charcoals and navy-tints (`#111827`) to reduce eye strain. Subtle borders serve as the primary method of separation rather than aggressive drop shadows.
- **Semantic Logic:** Success, warning, and error states use slightly desaturated tones to maintain the professional aesthetic while providing clear status indicators.

## Typography

This design system utilizes **Inter** for its exceptional legibility and neutral, systematic character. The typographic scale is optimized for reading speed and comprehension.

- **Readability:** Body copy uses a generous `1.6` to `1.75` line height to prevent fatigue during long AI interactions. 
- **Hierarchy:** Headlines use tighter tracking and heavier weights to provide clear entry points into the content. 
- **Monospaced elements:** Technical snippets and AI-generated code blocks use a standard monospace font with a distinct background surface to separate logic from prose.

## Layout & Spacing

The layout follows a **Hybrid Fluid Grid**. While the shell of the application (sidebars, headers) expands to fill the viewport, the core chat and document content is constrained to a `800px` max-width container. This ensures line lengths remain optimal for reading.

A 4px baseline grid governs all spatial relationships. Sidebars utilize significant internal padding (`1.5rem`) to maintain the minimalist aesthetic, while the main chat feed uses dynamic vertical spacing to group user prompts and AI responses as distinct units of conversation.

## Elevation & Depth

Visual hierarchy is established through **Glassmorphism** and **Tonal Layering**.

- **Sidebars & Navigation:** Use a high-quality backdrop blur (20px+) with a semi-transparent surface color (`primary-indigo` at 5% opacity in dark mode, or `white` at 70% in light mode). This creates a sense of the interface floating over the background.
- **Main Content:** Sits on the lowest elevation tier to feel grounded.
- **Interactive Elements:** Modals and popovers use "Ambient Shadows"—soft, diffused shadows with a subtle tint of the primary indigo to create depth without harsh edges.
- **Borders:** In dark mode, borders are the primary separators, set at a low opacity (`white` at 10%) to define shapes subtly.

## Shapes

The shape language is modern and approachable, utilizing a **Rounded (Level 2)** system. 

- **Standard Components:** Buttons, input fields, and chips use a base radius of `0.5rem` (8px).
- **Surface Containers:** Large cards, chat bubbles, and modal containers use `1rem` (16px) or `1.5rem` (24px) for a softer, more organic feel.
- **Consistency:** All rounded corners must be concentric when nested to maintain visual harmony.

## Components

- **Input Fields:** The primary chat input is a "Refined Input" surface. It features a subtle internal shadow in light mode and a faint indigo glow (`0px 0px 12px rgba(99, 102, 241, 0.2)`) when focused. The transition between active and inactive states should be fluid.
- **Buttons:**
    - *Primary:* Solid deep indigo with white text.
    - *Secondary:* Ghost style with a subtle border and indigo text.
    - *Actionable Icons:* High-contrast icons with a circular hover state.
- **Chat Bubbles:** AI responses should not look like bubbles; they should appear as "Document Blocks" with clean margins and no background fill (or a very subtle gray tint). User prompts are encapsulated in soft-rounded containers to distinguish them as "sent" messages.
- **Sidebars:** Persistent glass panels with integrated navigation links. Active states in the sidebar use a vertical indicator bar and a slight tonal shift.
- **Chips:** Used for suggested prompts or tags, utilizing a pill-shape with a low-opacity primary background.
- **Code Blocks:** Dark-themed syntax highlighting even in Light Mode to provide high contrast for logic-based content.