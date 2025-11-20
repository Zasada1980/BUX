import React, { ReactNode } from 'react';

/**
 * TableFilters — Unified filter panel for table pages
 * 
 * Pattern:
 * - Consistent spacing and layout
 * - Filters organized left-to-right: Status → Type/Role/Category → Worker/Client → Date From/To
 * - Clear filters button aligned to bottom-right
 * - Responsive grid layout (4 columns on desktop, collapses on mobile)
 * 
 * Usage:
 * ```tsx
 * <TableFilters>
 *   <FilterField label="Status" htmlFor="status">
 *     <select id="status" value={status} onChange={...}>...</select>
 *   </FilterField>
 *   <FilterField label="Date From" htmlFor="dateFrom">
 *     <input type="date" id="dateFrom" value={dateFrom} onChange={...} />
 *   </FilterField>
 *   <ClearFiltersButton onClick={handleClear} />
 * </TableFilters>
 * ```
 */

interface TableFiltersProps {
  children: ReactNode;
}

export function TableFilters({ children }: TableFiltersProps) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: '1rem',
        marginBottom: '1.5rem',
        padding: '1rem',
        background: '#f9fafb',
        borderRadius: '0.5rem',
        border: '1px solid #e5e7eb',
      }}
    >
      {children}
    </div>
  );
}

interface FilterFieldProps {
  label: string;
  htmlFor?: string;
  children: ReactNode;
  fullWidth?: boolean;
}

export function FilterField({ label, htmlFor, children, fullWidth }: FilterFieldProps) {
  return (
    <div style={{ gridColumn: fullWidth ? '1 / -1' : 'auto' }}>
      <label
        htmlFor={htmlFor}
        style={{
          display: 'block',
          marginBottom: '0.375rem',
          fontSize: '0.875rem',
          fontWeight: '500',
          color: '#374151',
        }}
      >
        {label}
      </label>
      {children}
    </div>
  );
}

interface ClearFiltersButtonProps {
  onClick: () => void;
  visible?: boolean;
}

export function ClearFiltersButton({ onClick, visible = true }: ClearFiltersButtonProps) {
  if (!visible) return null;

  return (
    <div style={{ display: 'flex', alignItems: 'flex-end' }}>
      <button
        onClick={onClick}
        style={{
          padding: '0.5rem 1rem',
          borderRadius: '0.375rem',
          border: '1px solid #d1d5db',
          background: 'white',
          cursor: 'pointer',
          fontSize: '0.875rem',
          fontWeight: '500',
          color: '#6b7280',
          transition: 'all 0.15s',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = '#f3f4f6';
          e.currentTarget.style.borderColor = '#9ca3af';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'white';
          e.currentTarget.style.borderColor = '#d1d5db';
        }}
      >
        Clear Filters
      </button>
    </div>
  );
}

// Shared input styles for consistency
export const filterInputStyles: React.CSSProperties = {
  width: '100%',
  padding: '0.5rem',
  borderRadius: '0.375rem',
  border: '1px solid #d1d5db',
  background: 'white',
  fontSize: '0.875rem',
};

export const filterSelectStyles: React.CSSProperties = {
  ...filterInputStyles,
  cursor: 'pointer',
};
