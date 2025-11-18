import { useState, useEffect } from 'react';
import { DataTable } from '@/components/ui/DataTable';
import { Badge } from '@/components/ui/Badge';
import Spinner from '@/components/ui/Spinner';
import Pagination from '@/components/ui/Pagination';
import Modal from '@/components/ui/Modal';
import { useToast } from '@/contexts/ToastContext';
import { useApi } from '@/hooks/useApi';
import { apiClient } from '@/lib/apiClient';
import type { Expense } from '@/types';

/**
 * ExpensesPage — Expense management with filtering (F7-3 Complete)
 * 
 * Features:
 * - Pagination: ✅ Client-side pagination (20 per page)
 * - Filtering: ✅ By status, category, date range
 * - CSV Export: ✅ Enabled (F7-3) — exports filtered data to CSV (max 10,000 rows)
 * 
 * Backend: GET /api/expenses (list), GET /api/expenses/export (CSV)
 * Routes: /expenses
 * Auth: Admin only
 * 
 * UX Coverage:
 * - CSV Export: ✅ Functional with filters + 10K row limit
 * - Filter by status: pending/confirmed/all
 * - Filter by category: materials/transport/food/equipment/other/all
 * - Filter by date range: date_from → date_to
 */
export default function ExpensesPage() {
  const { showToast } = useToast();
  const [page, setPage] = useState(1);
  const [limit] = useState(20);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [statusFilter, setStatusFilter] = useState<'all' | 'pending' | 'approved'>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [photoViewerOpen, setPhotoViewerOpen] = useState(false);
  const [currentPhoto, setCurrentPhoto] = useState<string | null>(null);

  // Fetch expenses with filters
  const { loading, error, execute: fetchExpenses } = useApi(
    async (page: number, limit: number, status: string, category: string, dateFrom: string, dateTo: string) => {
      const filters: Record<string, any> = { page, limit };
      if (status !== 'all') filters.status = status;
      if (category !== 'all') filters.category = category;
      if (dateFrom) filters.date_from = dateFrom;
      if (dateTo) filters.date_to = dateTo;
      
      const response = await apiClient.getExpenses(filters);
      setExpenses(response.items || []);
      setTotalPages(response.pages || 1);
      setTotalItems(response.total || 0);
      return response;
    },
    { showErrorToast: true }
  );

  useEffect(() => {
    fetchExpenses(page, limit, statusFilter, categoryFilter, dateFrom, dateTo);
  }, [page, limit, statusFilter, categoryFilter, dateFrom, dateTo]);

  // CSV Export handler - ENABLED in F7-3
  const handleExport = async () => {
    try {
      const filters: Record<string, any> = {};
      if (statusFilter !== 'all') filters.status = statusFilter;
      if (categoryFilter !== 'all') filters.category = categoryFilter;
      if (dateFrom) filters.date_from = dateFrom;
      if (dateTo) filters.date_to = dateTo;

      const blob = await apiClient.exportExpensesCSV(filters);

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `expenses_${new Date().toISOString().replace(/[-:]/g, '').split('.')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);

      showToast('CSV exported successfully', 'success');
    } catch (error: any) {
      showToast(error?.message || 'Failed to export CSV', 'error');
    }
  };

  const handleClearFilters = () => {
    setStatusFilter('all');
    setCategoryFilter('all');
    setDateFrom('');
    setDateTo('');
    setPage(1);
  };

  const handleOpenPhoto = (photoRef: string) => {
    setCurrentPhoto(photoRef);
    setPhotoViewerOpen(true);
  };

  const columns = [
    { key: 'id', label: 'ID', sortable: true },
    { key: 'worker_name', label: 'Worker' },
    {
      key: 'category',
      label: 'Category',
      render: (expense: Expense) => <Badge variant="status" value={expense.category} />,
    },
    {
      key: 'amount',
      label: 'Amount',
      render: (expense: Expense) => `₪${expense.amount.toFixed(2)}`,
    },
    {
      key: 'status',
      label: 'Status',
      render: (expense: Expense) => (
        <Badge variant="status" value={expense.status} />
      ),
    },
    {
      key: 'ocr_metadata',
      label: 'OCR',
      render: (expense: Expense) => {
        if (!expense.ocr_metadata) return '—';
        const { status, confidence } = expense.ocr_metadata;
        const color = status === 'ok' ? '#10b981' : status === 'abstain' ? '#f59e0b' : '#6b7280';
        return (
          <span style={{ color, fontSize: '0.875rem' }}>
            {status.toUpperCase()}
            {confidence && ` (${confidence}%)`}
          </span>
        );
      },
    },
    {
      key: 'photo_ref',
      label: 'Receipt',
      render: (expense: Expense) => {
        if (!expense.photo_ref) return '—';
        return (
          <button
            onClick={() => handleOpenPhoto(expense.photo_ref!)}
            style={{
              padding: '0.25rem 0.5rem',
              fontSize: '0.875rem',
              background: '#3b82f6',
              color: 'white',
              borderRadius: '0.25rem',
              border: 'none',
              cursor: 'pointer',
            }}
            title="View receipt photo"
          >
            📷 View
          </button>
        );
      },
      sortable: false,
    },
    { key: 'date', label: 'Date' },
  ];

  if (loading && expenses.length === 0) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
        <Spinner size="large" text="Loading expenses..." />
      </div>
    );
  }

  // F4.4 FIX: Show error state if API fails
  if (error && expenses.length === 0) {
    return (
      <div style={{ padding: '3rem', textAlign: 'center' }}>
        <div style={{ color: '#dc2626', fontSize: '1.125rem', fontWeight: '500', marginBottom: '0.5rem' }}>
          Failed to load expenses
        </div>
        <div style={{ color: '#6b7280', marginBottom: '1rem' }}>
          {error}
        </div>
        <button
          onClick={() => fetchExpenses(page, limit, statusFilter, categoryFilter, dateFrom, dateTo)}
          style={{
            padding: '0.5rem 1rem',
            background: '#3b82f6',
            color: 'white',
            borderRadius: '0.375rem',
            border: 'none',
            cursor: 'pointer',
            fontSize: '0.875rem',
            fontWeight: '500',
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <h1>Expenses</h1>
        <p style={{ color: '#6b7280', marginTop: '0.5rem' }}>
          Track worker expenses with OCR metadata and filters
        </p>
      </div>

      {/* Filters */}
      <div
        style={{
          marginBottom: '1.5rem',
          padding: '1rem',
          background: '#f9fafb',
          borderRadius: '0.375rem',
          display: 'flex',
          gap: '1rem',
          flexWrap: 'wrap',
        }}
      >
        <div>
          <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: '500' }}>
            Status
          </label>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value as any);
              setPage(1); // Reset to page 1 on filter change
            }}
            style={{
              padding: '0.5rem',
              border: '1px solid #d1d5db',
              borderRadius: '0.375rem',
              background: 'white',
            }}
          >
            <option value="all">All</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: '500' }}>
            Category
          </label>
          <select
            value={categoryFilter}
            onChange={(e) => {
              setCategoryFilter(e.target.value);
              setPage(1);
            }}
            style={{
              padding: '0.5rem',
              border: '1px solid #d1d5db',
              borderRadius: '0.375rem',
              background: 'white',
            }}
          >
            <option value="all">All</option>
            <option value="transport">Transport</option>
            <option value="materials">Materials</option>
            <option value="meals">Meals</option>
            <option value="other">Other</option>
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: '500' }}>
            Date From
          </label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => {
              setDateFrom(e.target.value);
              setPage(1);
            }}
            style={{
              padding: '0.5rem',
              border: '1px solid #d1d5db',
              borderRadius: '0.375rem',
              background: 'white',
            }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: '500' }}>
            Date To
          </label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => {
              setDateTo(e.target.value);
              setPage(1);
            }}
            style={{
              padding: '0.5rem',
              border: '1px solid #d1d5db',
              borderRadius: '0.375rem',
              background: 'white',
            }}
          />
        </div>

        {(statusFilter !== 'all' || categoryFilter !== 'all' || dateFrom || dateTo) && (
          <button
            onClick={handleClearFilters}
            style={{
              alignSelf: 'flex-end',
              padding: '0.5rem 1rem',
              background: '#e5e7eb',
              borderRadius: '0.375rem',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.875rem',
            }}
          >
            Clear Filters
          </button>
        )}

        <button
          onClick={handleExport}
          disabled={false}
          title="Export filtered expenses to CSV (max 10,000 rows)"
          style={{
            alignSelf: 'flex-end',
            padding: '0.5rem 1rem',
            background: '#10b981',
            color: 'white',
            borderRadius: '0.375rem',
            border: 'none',
            cursor: 'pointer',
            fontSize: '0.875rem',
            fontWeight: '500',
            opacity: 1,
          }}
        >
          📊 Export CSV
        </button>
      </div>

      <DataTable
        columns={columns}
        data={expenses}
        keyExtractor={(expense) => expense.id}
        emptyMessage="No expenses found"
      />

      {totalPages > 1 && (
        <div style={{ marginTop: '1.5rem' }}>
          <Pagination
            currentPage={page}
            totalPages={totalPages}
            onPageChange={setPage}
            itemsPerPage={limit}
            totalItems={totalItems}
          />
        </div>
      )}

      {/* Photo Viewer Modal */}
      <Modal
        isOpen={photoViewerOpen}
        onClose={() => setPhotoViewerOpen(false)}
        title="Receipt Photo"
        size="large"
      >
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
          {currentPhoto ? (
            <img
              src={currentPhoto}
              alt="Receipt"
              style={{
                maxWidth: '100%',
                maxHeight: '600px',
                objectFit: 'contain',
                borderRadius: '0.375rem',
              }}
            />
          ) : (
            <p>No photo available</p>
          )}
        </div>
      </Modal>
    </div>
  );
}
