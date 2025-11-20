import React, { ReactNode } from 'react';

/**
 * TableActions — Unified action panel for table pages
 * 
 * Pattern:
 * - Displays summary info (e.g., "Showing X of Y items")
 * - Action buttons aligned to the right (Export CSV, Add New, etc.)
 * - Bulk action bar appears conditionally when items selected
 * 
 * Usage:
 * ```tsx
 * <TableActions
 *   totalItems={totalItems}
 *   currentCount={items.length}
 *   selectedCount={selectedIds.length}
 *   bulkActions={
 *     <>
 *       <BulkActionButton onClick={handleApprove} variant="success">
 *         ✓ Approve Selected
 *       </BulkActionButton>
 *       <BulkActionButton onClick={handleReject} variant="danger">
 *         ✗ Reject Selected
 *       </BulkActionButton>
 *     </>
 *   }
 * >
 *   <ActionButton onClick={handleExport}>📊 Export CSV</ActionButton>
 *   <ActionButton onClick={handleAdd} variant="primary">+ Add New</ActionButton>
 * </TableActions>
 * ```
 */

interface TableActionsProps {
  totalItems: number;
  currentCount: number;
  selectedCount?: number;
  bulkActions?: ReactNode;
  children?: ReactNode;
}

export function TableActions({
  totalItems,
  currentCount,
  selectedCount = 0,
  bulkActions,
  children,
}: TableActionsProps) {
  return (
    <>
      {/* Main action bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '1rem',
          padding: '0.75rem 0',
        }}
      >
        <div style={{ fontSize: '0.875rem', color: '#6b7280' }}>
          Showing <strong>{currentCount}</strong> of <strong>{totalItems}</strong> items
        </div>
        <div style={{ display: 'flex', gap: '0.75rem' }}>{children}</div>
      </div>

      {/* Bulk action bar (appears when items selected) */}
      {selectedCount > 0 && bulkActions && (
        <div
          style={{
            marginBottom: '1rem',
            padding: '1rem',
            background: '#f3f4f6',
            borderRadius: '0.5rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            border: '1px solid #e5e7eb',
          }}
        >
          <span style={{ fontWeight: '500', color: '#374151' }}>
            {selectedCount} item{selectedCount > 1 ? 's' : ''} selected
          </span>
          <div style={{ display: 'flex', gap: '0.75rem' }}>{bulkActions}</div>
        </div>
      )}
    </>
  );
}

interface ActionButtonProps {
  onClick: () => void;
  disabled?: boolean;
  variant?: 'default' | 'primary' | 'success' | 'danger';
  title?: string;
  children: ReactNode;
}

export function ActionButton({
  onClick,
  disabled = false,
  variant = 'default',
  title,
  children,
}: ActionButtonProps) {
  const variantStyles: Record<string, React.CSSProperties> = {
    default: {
      background: '#e5e7eb',
      color: '#374151',
    },
    primary: {
      background: '#3b82f6',
      color: 'white',
    },
    success: {
      background: '#10b981',
      color: 'white',
    },
    danger: {
      background: '#ef4444',
      color: 'white',
    },
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      style={{
        padding: '0.5rem 1rem',
        borderRadius: '0.375rem',
        border: 'none',
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontSize: '0.875rem',
        fontWeight: '500',
        opacity: disabled ? 0.5 : 1,
        transition: 'all 0.15s',
        ...variantStyles[variant],
      }}
    >
      {children}
    </button>
  );
}

export function BulkActionButton({
  onClick,
  variant = 'default',
  children,
}: {
  onClick: () => void;
  variant?: 'success' | 'danger' | 'default';
  children: ReactNode;
}) {
  return <ActionButton onClick={onClick} variant={variant}>{children}</ActionButton>;
}
