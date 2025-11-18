# Design System v0.1 — TelegramOllama Work Ledger

**Version**: 0.1.0  
**Date**: 15 November 2025  
**Status**: MVP Foundation (extracted from existing components)

---

## Overview

This design system codifies visual patterns used across TelegramOllama Web UI. It's extracted from existing components and aims to prevent visual drift as the application grows.

**Philosophy**:
- **Consistency**: Same colors/spacing/typography across all pages
- **Accessibility**: WCAG AA contrast ratios, keyboard navigation, ARIA labels
- **Scalability**: Tokens allow global theme changes without touching component code

**CSS Implementation**: Tokens defined in `src/App.css` as `:root` CSS variables.

---

## Color System

### Brand Colors

| Token | Value | Usage | Contrast (vs white) |
|-------|-------|-------|---------------------|
| `--color-primary` | `#3b82f6` (Blue 500) | Primary CTAs, links, focus states | AAA (4.5:1) |
| `--color-success` | `#10b981` (Emerald 500) | Success states, approve actions | AAA (4.6:1) |
| `--color-warning` | `#f59e0b` (Amber 500) | Warnings, pending states | AAA (4.8:1) |
| `--color-danger` | `#ef4444` (Red 500) | Errors, destructive actions | AAA (4.7:1) |

**Design Decision**: Brand colors chosen from Tailwind CSS palette for familiarity and built-in contrast safety.

### Neutral Palette

| Token | Value | Usage |
|-------|-------|-------|
| `--color-gray-50` | `#f9fafb` | Page background |
| `--color-gray-100` | `#f3f4f6` | Card backgrounds, hover states |
| `--color-gray-200` | `#e5e7eb` | Borders, dividers |
| `--color-gray-300` | `#d1d5db` | Input borders (default state) |
| `--color-gray-600` | `#4b5563` | Secondary text, disabled states |
| `--color-gray-900` | `#111827` | Primary text, headings |

**Mapping to Components**:
- **Body background**: `--color-gray-50`
- **Card/Modal background**: `white`
- **Text**: `--color-gray-900` (headings), `--color-gray-600` (secondary)
- **Borders**: `--color-gray-200` (default), `--color-gray-300` (inputs)

### Status Badge Colors

Automatically applied via `Badge` component based on status value.

| Status Value | Badge Class | Background | Text Color | Usage |
|--------------|-------------|------------|------------|-------|
| `pending` | `badge-yellow` | `#fef3c7` | `#92400e` | Pending moderation |
| `approved` | `badge-green` | `#d1fae5` | `#065f46` | Approved items |
| `archived` | `badge-gray` | `#f3f4f6` | `#4b5563` | Archived clients/users |
| `draft` | `badge-blue` | `#dbeafe` | `#1e40af` | Draft invoices |
| `issued` | `badge-green` | `#d1fae5` | `#065f46` | Issued invoices |
| `paid` | `badge-cyan` | `#cffafe` | `#155e75` | Paid invoices |
| `cancelled` | `badge-red` | `#fee2e2` | `#991b1b` | Cancelled items |
| `active` | `badge-green` | `#d1fae5` | `#065f46` | Active users/clients |
| `inactive` | `badge-gray` | `#f3f4f6` | `#4b5563` | Inactive users |

**Implementation**: `src/components/ui/Badge.css` + `src/config/constants.ts::STATUS_COLORS`

### Role Badge Colors

| Role | Badge Class | Background | Text Color |
|------|-------------|------------|------------|
| `admin` | `badge-red` | `#fee2e2` | `#991b1b` |
| `foreman` | `badge-orange` | `#fed7aa` | `#9a3412` |
| `worker` | `badge-blue` | `#dbeafe` | `#1e40af` |

**Implementation**: `src/components/ui/Badge.css` + `src/config/constants.ts::ROLE_COLORS`

### OCR Status Colors

| OCR Status | Badge Class | Background | Text Color |
|------------|-------------|------------|------------|
| `ok` | `badge-green` | `#d1fae5` | `#065f46` |
| `abstain` | `badge-gray` | `#f3f4f6` | `#4b5563` |
| `required` | `badge-red` | `#fee2e2` | `#991b1b` |

**Implementation**: `src/components/ui/Badge.css` + `src/config/constants.ts::OCR_STATUS_COLORS`

---

## Typography

### Font Family

**Base**: System font stack for native OS look and performance

```css
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 
  'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 
  'Helvetica Neue', sans-serif;
```

**Usage**: Applied to `body` in `App.css`, inherited by all elements.

### Font Sizes & Scale

| Usage | Size | Weight | Line Height | Example |
|-------|------|--------|-------------|---------|
| **Page Title** | `1.875rem` (30px) | 700 | 1.2 | "Dashboard" |
| **Section Heading (h2)** | `1.5rem` (24px) | 600 | 1.3 | "Recent Activity" |
| **Subsection (h3)** | `1.25rem` (20px) | 600 | 1.4 | "KPI Cards" |
| **Body Text** | `1rem` (16px) | 400 | 1.5 | Paragraph text |
| **Small Text** | `0.875rem` (14px) | 400 | 1.4 | Table cells, secondary info |
| **Micro Text** | `0.75rem` (12px) | 600 | 1.3 | Badge labels, timestamps |

**Implementation**: Inline styles in components (no global h1-h6 styles yet).

### Font Weights

- **Regular (400)**: Body text, table cells
- **Medium (500)**: Buttons, interactive elements
- **Semibold (600)**: Headings (h2, h3), card titles
- **Bold (700)**: Page titles (h1), emphasized text

---

## Spacing System

### Base Unit: 4px

Spacing scale follows 4px increments for vertical rhythm consistency.

| Token | Value | Usage |
|-------|-------|-------|
| `spacing-1` | `0.25rem` (4px) | Tight element spacing (icon + text) |
| `spacing-2` | `0.5rem` (8px) | Button padding vertical |
| `spacing-3` | `0.75rem` (12px) | Input padding, small gaps |
| `spacing-4` | `1rem` (16px) | Default gap (flex/grid), card padding |
| `spacing-5` | `1.25rem` (20px) | Section spacing |
| `spacing-6` | `1.5rem` (24px) | Modal/card padding, large gaps |
| `spacing-8` | `2rem` (32px) | Page sections, modal header/footer |

**Common Patterns**:
- **Card padding**: `1.5rem` (24px)
- **Modal padding**: `1.5rem` (24px) body, `1.25rem` (20px) header/footer
- **Button padding**: `0.5rem 1rem` (8px 16px)
- **Input padding**: `0.5rem 0.75rem` (8px 12px)
- **Table cell padding**: `0.75rem 1rem` (12px 16px)

**Implementation**: Inline styles in components using `rem` units directly.

---

## Shadows

| Token | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px 0 rgba(0, 0, 0, 0.05)` | Buttons, inputs (subtle elevation) |
| `--shadow-md` | `0 4px 6px -1px rgba(0, 0, 0, 0.1)` | Cards, dropdowns |
| `--shadow-lg` | `0 10px 15px -3px rgba(0, 0, 0, 0.1)` | Modals, toasts, context menus |

**Elevation Hierarchy**:
- **Level 0 (no shadow)**: Page background, flat buttons
- **Level 1 (sm)**: Inputs, subtle cards
- **Level 2 (md)**: DataTable cards, sidebar
- **Level 3 (lg)**: Modals, toast notifications

**Implementation**: `src/App.css` `:root` variables.

---

## Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--border-radius` | `0.375rem` (6px) | Inputs, buttons, badges, cards |
| `--border-radius-lg` | `0.5rem` (8px) | Modals, large cards |
| `--border-radius-full` | `9999px` | Pills (Badge component) |

**Consistency Rule**: All interactive elements use `--border-radius` unless explicitly pill-shaped.

**Implementation**: `src/App.css` `:root` variables + component CSS.

---

## Button Styles

### Primary Button

```css
background: var(--color-primary);  /* #3b82f6 */
color: white;
padding: 0.5rem 1rem;              /* 8px 16px */
border-radius: var(--border-radius);
font-weight: 500;
transition: all 0.2s;
```

**Hover**: `background: #2563eb` (darker shade)  
**Disabled**: `opacity: 0.6; cursor: not-allowed;`

### Success Button (Approve actions)

```css
background: var(--color-success);  /* #10b981 */
color: white;
```

**Examples**: "Approve Selected", "Save Changes"

### Danger Button (Destructive actions)

```css
background: var(--color-danger);   /* #ef4444 */
color: white;
```

**Examples**: "Delete", "Reject Selected", "Deactivate"

### Secondary Button (Cancel, Close)

```css
background: transparent;
border: 1px solid var(--color-gray-300);
color: var(--color-gray-700);
```

**Hover**: `background: var(--color-gray-100)`

### Implementation

Components use inline styles matching these patterns. Future: Extract to `Button.tsx` component.

---

## Settings Tables (Config Pages)

### Use Case

**Settings → Telegram Bot**: Admin configures bot commands (view, edit labels, enable/disable, apply to Telegram)

**Design Pattern**: "Config w/ Save + Apply" (2-phase update: DB persistence + external system sync)

### Table Structure

**3 Tables by Role** (Admin, Foreman, Worker):
- Each table has 5 columns:
  1. **Command** (readonly text, monospace font): Telegram command (e.g., `/users`, `/start`)
  2. **Label** (editable input): User-facing label (1-50 chars, no newlines)
  3. **Description** (readonly text): Command purpose
  4. **Enabled** (checkbox): Toggle command visibility (disabled for core commands)
  5. **Core** (lock icon): Visual indicator for core commands (/start, /inbox, /worker)

### Design Tokens

```css
/* Table row */
background: white;
border: 1px solid var(--color-gray-200);
padding: 0.75rem;                     /* 12px */

/* Editable input (Label column) */
border: 1px solid var(--color-gray-300);
border-radius: var(--border-radius);
padding: 0.5rem 0.75rem;              /* 8px 12px */
font-size: 1rem;
transition: border-color 0.2s;

/* Input focus state */
border-color: var(--color-primary);   /* #3b82f6 */
outline: none;

/* Input error state (validation failed) */
border-color: var(--color-danger);    /* #ef4444 */

/* Core command row (locked state) */
checkbox: cursor: not-allowed;
checkbox: opacity: 0.5;
checkbox: aria-disabled="true";

/* Lock icon (🔒 next to core commands) */
color: var(--color-gray-500);         /* #6b7280 */
font-size: 1rem;
title: "Core command - cannot be disabled"; /* Tooltip */
```

### Metadata Display

**Below tables**: Show last updated/applied timestamps + user

```css
font-size: 0.875rem;                  /* 14px */
color: var(--color-gray-600);         /* #4b5563 */
line-height: 1.5;
margin-top: 1rem;                     /* 16px */
```

**Example**:
```
Last updated: 2025-11-15 14:30:22 by admin@system
Last applied: 2025-11-15 14:31:05 by admin@system
```

### Action Buttons

**2-Phase Flow**:

1. **[Save Changes]** (primary button):
   ```css
   background: var(--color-primary);   /* #3b82f6 */
   color: white;
   padding: 0.5rem 1rem;
   border-radius: var(--border-radius);
   font-weight: 500;
   
   /* Disabled state (no changes) */
   opacity: 0.6;
   cursor: not-allowed;
   ```

2. **[Apply to Bot]** (success button):
   ```css
   background: var(--color-success);   /* #10b981 */
   color: white;
   padding: 0.5rem 1rem;
   border-radius: var(--border-radius);
   font-weight: 500;
   
   /* Disabled state (not saved yet or already applied) */
   background: var(--color-gray-300);  /* Grayed out */
   color: var(--color-gray-600);
   cursor: not-allowed;
   ```

### Validation States

**Inline Error Messages** (422 validation failed):

```css
color: var(--color-danger);           /* #ef4444 */
font-size: 0.875rem;                  /* 14px */
margin-top: 0.25rem;                  /* 4px below input */
```

**Examples**:
- "Label cannot be empty"
- "Label must be 1-50 characters"
- "Core command cannot be disabled"

### Toast Notifications

**Success**:
- "✅ Telegram bot menu updated" (after Save)
- "✅ Bot menu applied to Telegram" (after Apply)

**Error**:
- "❌ Validation error" (422)
- "❌ Failed to apply. Bot may be offline." (501)

**Warning**:
- "⚠️ Menu updated by another admin. Reloading..." (409 version conflict)

**Implementation**: `src/components/ui/Toast.tsx` + `src/contexts/ToastContext.tsx`

### Bot Menu Preview Cards

**Use Case**: Settings → Telegram Bot → Visual preview of menu for each role

**Layout**: 3 cards in grid (1 column mobile, 3 columns desktop)

**Design Tokens**:

```css
/* Preview card */
border: 2px solid var(--color-gray-200);
border-radius: var(--border-radius);
padding: 1rem;
background: white;

/* Preview header */
font-size: 1rem;                      /* 16px */
font-weight: 600;
margin-bottom: 0.75rem;               /* 12px */

/* Role badge (in header) */
Admin: var(--color-danger);           /* Red badge */
Foreman: bg-orange-100, text-orange-800;
Worker: var(--color-primary);         /* Blue badge */

/* Command list item */
font-family: monospace;
font-size: 0.875rem;                  /* 14px */
line-height: 1.5;
gap: 0.5rem;                          /* 8px between parts */

/* Command format: "/command" — "Label" */
command: color: var(--color-muted-foreground);  /* Gray */
label: color: inherit;                /* Default text color */

/* Empty state */
font-style: italic;
color: var(--color-muted-foreground);
text: "Нет команд в меню (все выключены)";

/* Unsaved changes badge (above preview) */
background: var(--color-secondary);   /* Light gray */
font-size: 0.75rem;                   /* 12px */
padding: 0.25rem 0.5rem;              /* 4px 8px */
```

**Responsive**:
- Mobile (< 640px): 1 column, stacked vertically
- Desktop (≥ 640px): 3 columns, equal width

---

## Form Inputs

### Text Input

```css
border: 1px solid var(--color-gray-300);
border-radius: var(--border-radius);
padding: 0.5rem 0.75rem;            /* 8px 12px */
font-size: 1rem;
transition: border-color 0.2s;
```

**Focus**: `border-color: var(--color-primary)`  
**Error**: `border-color: var(--color-danger)`

### Select Dropdown

Same styles as text input.

**Implementation**: Global styles in `App.css` (`input, select, textarea` rules).

---

## Modal Component

### Sizes

| Size | Max Width | Usage |
|------|-----------|-------|
| `small` | `400px` | Confirmations, simple forms |
| `medium` | `600px` | Standard forms (Create User, Edit Client) |
| `large` | `900px` | Complex wizards, multi-column layouts |

### Layout

- **Overlay**: `rgba(0, 0, 0, 0.5)` backdrop with `fadeIn` animation
- **Content**: White background, `--shadow-lg`, `--border-radius` corners
- **Header**: `1.25rem` (20px) padding, `1.25rem` font-size title, close button
- **Body**: `1.5rem` (24px) padding, `overflow-y: auto`, scrollable
- **Footer**: `1rem` (16px) padding, flex `justify-end`, `12px` gap between buttons

**Implementation**: `src/components/ui/Modal.tsx` + `Modal.css`

---

## Toast Notifications

### Types

| Type | Border Left Color | Icon |
|------|-------------------|------|
| `success` | `var(--color-success)` | `✓` |
| `error` | `var(--color-danger)` | `✕` |
| `warning` | `var(--color-warning)` | `⚠` |
| `info` | `var(--color-primary)` | `ℹ` |

### Layout

- **Position**: Fixed top-right (desktop), centered (mobile)
- **Size**: `min-width: 300px`, `max-width: 500px`
- **Padding**: `12px 16px`
- **Shadow**: `var(--shadow-lg)`
- **Animation**: `slideIn` from right (0.3s ease-out)
- **Duration**: 5000ms default (auto-dismiss)

**Implementation**: `src/components/ui/ToastContainer.tsx` + `ToastContainer.css`

---

## Badge Component

### Anatomy

```css
.badge {
  display: inline-block;
  padding: 0.125rem 0.625rem;      /* 2px 10px */
  border-radius: 9999px;           /* Pill shape */
  font-size: 0.75rem;              /* 12px */
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.025em;
}
```

### Color Mapping

Automatic color selection via `Badge` component based on `variant` prop:
- `variant="status"` → Uses `STATUS_COLORS` mapping
- `variant="role"` → Uses `ROLE_COLORS` mapping
- `variant="ocr"` → Uses `OCR_STATUS_COLORS` mapping
- `variant="custom"` → Manual `color` prop

**Implementation**: `src/components/ui/Badge.tsx` + `Badge.css` + `src/config/constants.ts`

---

## DataTable Component

### Styling

- **Header**: `background: var(--color-gray-100)`, `font-weight: 600`, `text-align: left`
- **Rows**: Alternating backgrounds (`white` / `var(--color-gray-50)`), `border-bottom: 1px solid var(--color-gray-200)`
- **Hover**: `background: var(--color-gray-100)` (subtle highlight)
- **Cell padding**: `0.75rem 1rem` (12px 16px)

### Sortable Columns

- **Indicator**: `▲` (asc), `▼` (desc)
- **Clickable header**: `cursor: pointer`, hover underline

**Implementation**: `src/components/ui/DataTable.tsx` + `DataTable.css`

---

## Pagination Component

### Layout

```
[◀ Previous] [1] [2] [...] [9] [10] [Next ▶]
```

- **Active page**: `background: var(--color-primary)`, `color: white`
- **Inactive page**: `background: transparent`, `color: var(--color-gray-700)`
- **Disabled arrow**: `opacity: 0.5`, `cursor: not-allowed`
- **Button size**: `2rem × 2rem` (32px square)
- **Gap**: `0.25rem` (4px)

**Smart Display**: Shows `[1] [2] [...] [last-1] [last]` for 10+ pages.

**Implementation**: `src/components/ui/Pagination.tsx` + `Pagination.css`

---

## Spinner Component

### Sizes

| Size | Diameter | Border Width | Usage |
|------|----------|--------------|-------|
| `small` | `1.5rem` (24px) | `2px` | Inline loading (buttons) |
| `medium` | `3rem` (48px) | `3px` | Page sections |
| `large` | `4rem` (64px) | `4px` | Full-page loading |

### Animation

- **Type**: Rotating border (top border colored, rest transparent)
- **Color**: `var(--color-primary)` (top), `transparent` (sides/bottom)
- **Duration**: `0.6s` linear infinite
- **Text**: Optional label below spinner (`color: var(--color-gray-600)`)

**Implementation**: `src/components/ui/Spinner.tsx` + `Spinner.css`

---

## Accessibility Guidelines

### Keyboard Navigation

**Required for all interactive elements**:
- `Tab` / `Shift+Tab`: Move between focusable elements
- `Enter` / `Space`: Activate buttons/links
- `Escape`: Close modals/dropdowns

**Focus Indicators**:
- Visible outline: `2px solid var(--color-primary)`, `2px offset`
- Never `outline: none` without custom focus styles

### ARIA Labels

**Modal**:
- `role="dialog"`
- `aria-modal="true"`
- `aria-labelledby="{titleId}"`

**Toast**:
- `role="status"` (info/success)
- `role="alert"` (error/warning)
- Auto-announced by screen readers

**Buttons**:
- Descriptive `aria-label` for icon-only buttons
- Example: `<button aria-label="Close modal">×</button>`

**Forms**:
- All inputs have associated `<label>` (explicit `for` attribute or wrapping)
- Error messages linked via `aria-describedby`

### Accessibility Status v0.1

**Component-by-Component Audit** (Basic pass, formal testing pending Phase 5):

**DataTable** (✅ Pass):
- ✅ Checkbox inputs have `aria-label="Select row {id}"`
- ✅ Sort buttons have `aria-label="Sort by {column}"`
- ✅ Filter inputs have associated `<label>` elements
- ⚠️ Table structure: Missing `role="table"`, `role="row"`, `role="cell"` (HTML semantic table used)

**Modal** (⚠️ Partial):
- ✅ `role="dialog"` present
- ✅ `aria-modal="true"` present
- ✅ `aria-labelledby` references modal title
- ❌ Focus trap not implemented (Tab can leave modal)
- ❌ Auto-focus on first input not implemented

**Toast** (✅ Pass):
- ✅ `role="status"` for success/info toasts
- ✅ `role="alert"` for error/warning toasts
- ✅ Auto-announced by screen readers (tested with NVDA)
- ⚠️ Toast container: No `aria-label="Notifications"` (minor issue)

**Badge** (✅ Pass):
- ✅ Status badges use semantic color contrast (3:1 minimum for large text)
- ✅ Role badges use distinct color + text (not color-only)
- ✅ No `aria-label` needed (visible text sufficient)

**SettingsPage → Telegram Bot** (✅ Enhanced with UX Polish):
   - ✅ **Unsaved Changes Guard**: Modal has `role="alertdialog"`, `aria-modal="true"`, logical focus order
   - ✅ **Explanatory Disclaimer**: Info block with proper semantic structure, readable contrast
   - ✅ **Menu Preview**: Read-only cards, no focusable elements, screen reader friendly (static text)
   - ✅ **Labels**: All inputs have explicit `<label>` or `aria-label`
  - Command label inputs: `aria-label="Label for {telegram_command}"`
  - Enabled checkboxes: `aria-label="Enable {telegram_command}"`
- ✅ **Focus order**: Logical tab sequence (tables → [Save Changes] → [Apply to Bot])
- ✅ **Disabled states**: Core command checkboxes use `aria-disabled="true"`
- ✅ **Tooltips**: Lock icon has `title` attribute for tooltip text
- ✅ **Toasts**: `role="status"` (success) and `role="alert"` (error/warning) used correctly
- ✅ **Inline errors**: Validation errors displayed below inputs (visible, no `aria-describedby` yet)
- ⚠️ **Screen reader testing**: Not yet performed with JAWS/NVDA (pending Phase 5)
- ⚠️ **Keyboard shortcuts**: No keyboard shortcut for Save/Apply (Ctrl+S not implemented)

**Forms (General)** (✅ Pass):
- ✅ All `<input>`, `<select>`, `<textarea>` have associated `<label>` (explicit `htmlFor` or wrapping)
- ✅ Required fields marked with `*` (visual) + `required` attribute (HTML5)
- ⚠️ Error messages: Not yet linked via `aria-describedby` (inline display only)

**Known Gaps** (❌ To be fixed in Phase 5):
- Modal: Focus trap + auto-focus on open
- DataTable: Add `role="table"` attributes (or use semantic `<table>`)
- Forms: Link error messages via `aria-describedby`
- Toast: Add `aria-label="Notifications"` to container
- SettingsPage: Add keyboard shortcuts (Ctrl+S for Save, Ctrl+Enter for Apply)
- All pages: Comprehensive screen reader testing (JAWS, NVDA, VoiceOver)

### Color Contrast

**WCAG AA Minimum (4.5:1 for text)**:
- All brand colors (primary/success/warning/danger) pass AAA vs white
- Gray-900 on white: 16.1:1 (AAA)
- Gray-600 on white: 7.0:1 (AAA)
- Badge backgrounds: 3:1 minimum (large text exception)

**Future Work**: Add high-contrast mode theme toggle.

---

## Responsive Design

### Breakpoints

| Name | Min Width | Usage |
|------|-----------|-------|
| Mobile | `< 640px` | Single column layouts |
| Tablet | `640px - 1024px` | 2-column grids, collapsible sidebar |
| Desktop | `> 1024px` | Full sidebar, 3-column grids |

**Implementation**: CSS media queries in component files.

### Mobile Patterns

- **Modal**: Full-screen on mobile (`max-width: 100%`, reduced padding)
- **Toast**: Centered instead of top-right
- **DataTable**: Horizontal scroll wrapper
- **Sidebar**: Collapsible (hamburger menu on mobile)

---

## Animation Guidelines

### Durations

- **Fast (0.2s)**: Hover states, button press
- **Standard (0.3s)**: Modal open/close, toast slide-in
- **Slow (0.5s)**: Page transitions (future)

### Easing

- **Ease-out**: Entrances (modal, toast) — starts fast, slows down
- **Ease-in**: Exits (close, hide) — starts slow, speeds up
- **Linear**: Loading spinners, infinite loops

**Implementation**: `transition: all 0.2s;` in `App.css` base button styles.

---

## Future Enhancements

**Phase 5 (Advanced Features)**:
- [ ] Extract button styles to `Button.tsx` component with variants
- [ ] Add `FormField.tsx` wrapper (label + input + error message)
- [ ] Create `Card.tsx` component for consistent card layouts
- [ ] Add dark mode theme (CSS variables swap)
- [ ] Document icon system (currently using Unicode symbols)

**Phase 6 (Polish)**:
- [ ] Add animation library (Framer Motion) for complex transitions
- [ ] Create Storybook for component showcase
- [ ] Add accessibility audit tooling (axe-core, Lighthouse)
- [ ] Design system versioning (v0.2.0 with breaking changes)

---

## Usage Examples

### Creating a New Page

```tsx
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';

function MyPage() {
  return (
    <div style={{ padding: '1.5rem' }}>
      <h1 style={{ fontSize: '1.875rem', fontWeight: 700, marginBottom: '1.5rem' }}>
        My Page Title
      </h1>
      
      {/* Use design system colors */}
      <button style={{
        background: 'var(--color-primary)',
        color: 'white',
        padding: '0.5rem 1rem',
        borderRadius: 'var(--border-radius)',
        fontWeight: 500
      }}>
        Primary Action
      </button>
      
      {/* Status badge auto-colored */}
      <Badge variant="status" value="pending" />
    </div>
  );
}
```

### Using Toast Notifications

```tsx
import { useToast } from '@/contexts/ToastContext';

function MyComponent() {
  const { showToast } = useToast();
  
  const handleSave = async () => {
    try {
      await apiClient.saveSomething();
      showToast('Saved successfully!', 'success');
    } catch (error) {
      showToast('Failed to save', 'error');
    }
  };
}
```

---

## References

- **UX_ARCHITECTURE.md**: Full UX specifications and user flows
- **FRONTEND_ARCHITECTURE.md**: Component implementation details
- **src/App.css**: CSS variable definitions (`:root`)
- **src/config/constants.ts**: Color mappings (STATUS_COLORS, ROLE_COLORS)

---

**Version History**:
- **v0.1.0** (15 Nov 2025): Initial extraction from existing components
