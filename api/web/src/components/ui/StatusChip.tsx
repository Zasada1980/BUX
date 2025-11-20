/**
 * StatusChip — Unified Visual Status System (UX-V2-B1)
 * 
 * Purpose: Single source of truth for status visualization across all tables
 * 
 * Domains: user, shift, expense, invoice, inbox
 * 
 * Features:
 * - Consistent color mapping (success/warning/danger/info/neutral)
 * - Icon support (emoji for quick visual recognition)
 * - Accessible (ARIA labels, high contrast colors)
 * - Type-safe (TypeScript unions for all valid statuses)
 * 
 * Usage:
 * ```tsx
 * <StatusChip domain="user" status="active" />
 * <StatusChip domain="shift" status="open" />
 * <StatusChip domain="expense" status="approved" />
 * <StatusChip domain="invoice" status="paid" />
 * <StatusChip domain="inbox" status="task" />
 * ```
 */

// Type definitions for each domain
type UserStatus = 'active' | 'inactive';
type ShiftStatus = 'open' | 'completed' | 'cancelled';
type ExpenseStatus = 'pending' | 'approved' | 'rejected';
type InvoiceStatus = 'draft' | 'sent' | 'paid' | 'overdue';
type InboxType = 'task' | 'expense' | 'shift_start' | 'shift_end';

// Props interface
interface StatusChipProps {
  domain: 'user' | 'shift' | 'expense' | 'invoice' | 'inbox';
  status: UserStatus | ShiftStatus | ExpenseStatus | InvoiceStatus | InboxType;
  size?: 'small' | 'medium';
}

// Visual configuration for each status
interface StatusConfig {
  label: string;      // Display text
  icon: string;       // Emoji icon
  color: string;      // Text color (high contrast)
  background: string; // Background color
  variant: 'success' | 'warning' | 'danger' | 'info' | 'neutral';
}

// Status dictionary: domain → status → visual config
const STATUS_MAP: Record<string, Record<string, StatusConfig>> = {
  user: {
    active: {
      label: 'Active',
      icon: '✓',
      color: '#065f46',      // Green 900
      background: '#d1fae5', // Green 100
      variant: 'success',
    },
    inactive: {
      label: 'Inactive',
      icon: '○',
      color: '#6b7280',      // Gray 600
      background: '#f3f4f6', // Gray 100
      variant: 'neutral',
    },
  },
  shift: {
    open: {
      label: 'Open',
      icon: '🟢',
      color: '#1e40af',      // Blue 800
      background: '#dbeafe', // Blue 100
      variant: 'info',
    },
    completed: {
      label: 'Completed',
      icon: '✅',
      color: '#065f46',      // Green 900
      background: '#d1fae5', // Green 100
      variant: 'success',
    },
    cancelled: {
      label: 'Cancelled',
      icon: '✕',
      color: '#991b1b',      // Red 900
      background: '#fee2e2', // Red 100
      variant: 'danger',
    },
  },
  expense: {
    pending: {
      label: 'Pending',
      icon: '⏳',
      color: '#92400e',      // Yellow 900
      background: '#fef3c7', // Yellow 100
      variant: 'warning',
    },
    approved: {
      label: 'Approved',
      icon: '✓',
      color: '#065f46',      // Green 900
      background: '#d1fae5', // Green 100
      variant: 'success',
    },
    rejected: {
      label: 'Rejected',
      icon: '✕',
      color: '#991b1b',      // Red 900
      background: '#fee2e2', // Red 100
      variant: 'danger',
    },
  },
  invoice: {
    draft: {
      label: 'Draft',
      icon: '📝',
      color: '#1e40af',      // Blue 800
      background: '#dbeafe', // Blue 100
      variant: 'info',
    },
    sent: {
      label: 'Sent',
      icon: '📤',
      color: '#0891b2',      // Cyan 700
      background: '#cffafe', // Cyan 100
      variant: 'info',
    },
    paid: {
      label: 'Paid',
      icon: '✓',
      color: '#065f46',      // Green 900
      background: '#d1fae5', // Green 100
      variant: 'success',
    },
    overdue: {
      label: 'Overdue',
      icon: '⚠',
      color: '#991b1b',      // Red 900
      background: '#fee2e2', // Red 100
      variant: 'danger',
    },
  },
  inbox: {
    task: {
      label: 'Task',
      icon: '📋',
      color: '#1e40af',      // Blue 800
      background: '#dbeafe', // Blue 100
      variant: 'info',
    },
    expense: {
      label: 'Expense',
      icon: '💰',
      color: '#92400e',      // Yellow 900
      background: '#fef3c7', // Yellow 100
      variant: 'warning',
    },
    shift_start: {
      label: 'Shift Start',
      icon: '🟢',
      color: '#065f46',      // Green 900
      background: '#d1fae5', // Green 100
      variant: 'success',
    },
    shift_end: {
      label: 'Shift End',
      icon: '🔴',
      color: '#991b1b',      // Red 900
      background: '#fee2e2', // Red 100
      variant: 'danger',
    },
  },
};

/**
 * StatusChip component
 * 
 * Renders a status badge with consistent styling across all domains
 */
export function StatusChip({ domain, status, size = 'medium' }: StatusChipProps) {
  const config = STATUS_MAP[domain]?.[status];

  // Fallback for unknown status (should never happen with proper typing)
  if (!config) {
    console.warn(`[StatusChip] Unknown status: domain="${domain}", status="${status}"`);
    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.25rem',
          padding: size === 'small' ? '0.125rem 0.375rem' : '0.25rem 0.5rem',
          borderRadius: '0.25rem',
          fontSize: size === 'small' ? '0.6875rem' : '0.75rem',
          fontWeight: '500',
          color: '#6b7280',
          background: '#f3f4f6',
        }}
      >
        {status}
      </span>
    );
  }

  return (
    <span
      role="status"
      aria-label={`${domain} status: ${config.label}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.25rem',
        padding: size === 'small' ? '0.125rem 0.375rem' : '0.25rem 0.5rem',
        borderRadius: '0.25rem',
        fontSize: size === 'small' ? '0.6875rem' : '0.75rem',
        fontWeight: '500',
        color: config.color,
        background: config.background,
        whiteSpace: 'nowrap',
      }}
      data-variant={config.variant}
      data-domain={domain}
      data-status={status}
    >
      <span aria-hidden="true">{config.icon}</span>
      <span>{config.label}</span>
    </span>
  );
}

/**
 * Helper function to get status config (for external use)
 * 
 * Useful for conditional logic based on status variant
 */
export function getStatusConfig(
  domain: string,
  status: string
): StatusConfig | undefined {
  return STATUS_MAP[domain]?.[status];
}

/**
 * Helper function to get all statuses for a domain
 * 
 * Useful for filter dropdowns
 */
export function getDomainStatuses(domain: string): string[] {
  return Object.keys(STATUS_MAP[domain] || {});
}
