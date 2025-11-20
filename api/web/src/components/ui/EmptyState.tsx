/**
 * EmptyState — Unified empty state for table pages (UX-V2-C1)
 * 
 * Pattern:
 * - Consistent messaging for no data scenarios
 * - Optional suggestion to clear filters
 * - Centered layout with icon
 * - Optional CTA button (e.g., "Clear filters", "Add first item")
 * 
 * Usage:
 * ```tsx
 * {items.length === 0 && !loading && (
 *   <EmptyState
 *     message="No expenses found"
 *     suggestion="Try adjusting your filters or add a new expense"
 *     action={{ label: "Clear Filters", onClick: handleClearFilters }}
 *   />
 * )}
 * ```
 */

interface EmptyStateAction {
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'secondary';
}

interface EmptyStateProps {
  message: string;
  suggestion?: string;
  icon?: string;
  action?: EmptyStateAction;
}

export function EmptyState({
  message,
  suggestion,
  icon = '📭',
  action,
}: EmptyStateProps) {
  return (
    <div
      style={{
        textAlign: 'center',
        padding: '3rem 1rem',
        background: '#f9fafb',
        borderRadius: '0.5rem',
        border: '1px solid #e5e7eb',
      }}
    >
      <div style={{ fontSize: '3rem', marginBottom: '1rem' }} aria-hidden="true">
        {icon}
      </div>
      <p style={{ fontSize: '1rem', fontWeight: '500', color: '#374151', marginBottom: '0.5rem' }}>
        {message}
      </p>
      {suggestion && (
        <p style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: action ? '1.5rem' : '0' }}>
          {suggestion}
        </p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          style={{
            padding: '0.5rem 1rem',
            fontSize: '0.875rem',
            fontWeight: '500',
            color: 'white',
            background: action.variant === 'secondary' ? '#6b7280' : '#3b82f6',
            border: 'none',
            borderRadius: '0.375rem',
            cursor: 'pointer',
            transition: 'background 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = action.variant === 'secondary' ? '#4b5563' : '#2563eb';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = action.variant === 'secondary' ? '#6b7280' : '#3b82f6';
          }}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
