import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { DataTable } from '@/components/ui/DataTable';
import { Badge } from '@/components/ui/Badge';
import Spinner from '@/components/ui/Spinner';
import Pagination from '@/components/ui/Pagination';
import Modal from '@/components/ui/Modal';
import { useToast } from '@/contexts/ToastContext';
import { useApi } from '@/hooks/useApi';
import { apiClient } from '@/lib/apiClient';
import type { PendingItem } from '@/types';

export default function InboxPage() {
  const { showToast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  
  // Filters from URL (survive F5 refresh)
  const [page, setPage] = useState(Number(searchParams.get('page')) || 1);
  const [limit] = useState(20);
  const [typeFilter, setTypeFilter] = useState<string>(searchParams.get('kind') || 'all');
  const [workerFilter, setWorkerFilter] = useState<string>(searchParams.get('worker') || '');
  const [dateFrom, setDateFrom] = useState<string>(searchParams.get('date_from') || '');
  const [dateTo, setDateTo] = useState<string>(searchParams.get('date_to') || '');
  
  const [items, setItems] = useState<PendingItem[]>([]);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkAction, setBulkAction] = useState<'approve' | 'reject' | null>(null);

  // Update URL when filters change
  useEffect(() => {
    const params: Record<string, string> = {};
    if (page > 1) params.page = page.toString();
    if (typeFilter !== 'all') params.kind = typeFilter;
    if (workerFilter) params.worker = workerFilter;
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    setSearchParams(params, { replace: true });
  }, [page, typeFilter, workerFilter, dateFrom, dateTo, setSearchParams]);

  // Fetch pending items with filters
  const { loading, error, execute: fetchItems } = useApi(
    async (page: number, limit: number) => {
      const filters: Record<string, any> = {};
      if (typeFilter !== 'all') filters.kind = typeFilter;
      if (workerFilter) filters.worker = workerFilter;
      if (dateFrom) filters.date_from = dateFrom;
      if (dateTo) filters.date_to = dateTo;
      
      const response = await apiClient.getPendingItems(page, limit, filters);
      const itemsArray: PendingItem[] = response.items || [];
      setItems(itemsArray);
      setTotalPages(response.pages || 1);
      setTotalItems(response.total || 0);
      
      return response;
    },
    { showErrorToast: true }
  );

  useEffect(() => {
    // Reset selection when filters or page change
    setSelectedIds([]);
    fetchItems(page, limit);
  }, [page, limit, typeFilter, workerFilter, dateFrom, dateTo]);

  const handleBulkApprove = async () => {
    try {
      await apiClient.bulkApprovePendingItems(selectedIds);
      showToast(`${selectedIds.length} items approved`, 'success');
      setSelectedIds([]);
      setBulkAction(null);
      fetchItems(page, limit);
    } catch (error: any) {
      showToast(error.message || 'Failed to approve items', 'error');
    }
  };

  const handleBulkReject = async () => {
    try {
      await apiClient.bulkRejectPendingItems(selectedIds);
      showToast(`${selectedIds.length} items rejected`, 'success');
      setSelectedIds([]);
      setBulkAction(null);
      fetchItems(page, limit);
    } catch (error: any) {
      showToast(error.message || 'Failed to reject items', 'error');
    }
  };

  const handleClearFilters = () => {
    setTypeFilter('all');
    setWorkerFilter('');
    setDateFrom('');
    setDateTo('');
    setPage(1);
  };

  const toggleSelection = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const toggleSelectAll = () => {
    if (selectedIds.length === items.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(items.map((item) => item.id));
    }
  };

  const columns = [
    {
      key: 'select',
      label: (
        <input
          type="checkbox"
          checked={selectedIds.length === items.length && items.length > 0}
          onChange={toggleSelectAll}
        />
      ),
      render: (item: PendingItem) => (
        <input
          type="checkbox"
          checked={selectedIds.includes(item.id)}
          onChange={() => toggleSelection(item.id)}
        />
      ),
      sortable: false,
    },
    { key: 'id', label: 'ID', sortable: true },
    {
      key: 'type',
      label: 'Type',
      render: (item: PendingItem) => <Badge variant="status" value={item.type} />,
    },
    {
      key: 'description',
      label: 'Description',
      render: (item: PendingItem) => (
        <span style={{ fontSize: '0.875rem', color: '#374151' }}>
          {item.description || '—'}
        </span>
      ),
    },
    { key: 'worker_name', label: 'Worker' },
    { key: 'created_at', label: 'Created At' },
  ];

  if (loading && items.length === 0) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
        <Spinner size="large" text="Loading pending items..." />
      </div>
    );
  }

  if (error && items.length === 0) {
    return (
      <div style={{ padding: '3rem', textAlign: 'center' }}>
        <div
          style={{
            background: '#fef2f2',
            border: '1px solid #fecaca',
            padding: '1.5rem',
            borderRadius: '0.5rem',
            maxWidth: '600px',
            margin: '0 auto',
          }}
        >
          <div style={{ fontSize: '1.125rem', fontWeight: '600', color: '#991b1b', marginBottom: '0.5rem' }}>
            Failed to load pending items
          </div>
          <div style={{ color: '#dc2626', marginBottom: '1rem' }}>{error}</div>
          <button
            onClick={() => fetchItems(page, limit)}
            style={{
              padding: '0.5rem 1rem',
              background: '#dc2626',
              color: 'white',
              border: 'none',
              borderRadius: '0.375rem',
              cursor: 'pointer',
              fontWeight: '500',
            }}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <h1>Inbox (Moderation)</h1>
        <p style={{ color: '#6b7280', marginTop: '0.5rem' }}>
          Review and approve/reject pending tasks and expenses
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
            Type
          </label>
          <select
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value);
              setPage(1);
            }}
            style={{
              padding: '0.5rem',
              borderRadius: '0.375rem',
              border: '1px solid #d1d5db',
              minWidth: '120px',
            }}
          >
            <option value="all">All Types</option>
            <option value="task">Tasks</option>
            <option value="expense">Expenses</option>
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: '500' }}>
            Worker
          </label>
          <input
            type="text"
            value={workerFilter}
            onChange={(e) => {
              setWorkerFilter(e.target.value);
              setPage(1);
            }}
            placeholder="Filter by worker..."
            style={{
              padding: '0.5rem',
              borderRadius: '0.375rem',
              border: '1px solid #d1d5db',
              minWidth: '180px',
            }}
          />
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
              borderRadius: '0.375rem',
              border: '1px solid #d1d5db',
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
              borderRadius: '0.375rem',
              border: '1px solid #d1d5db',
            }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <button
            onClick={handleClearFilters}
            style={{
              padding: '0.5rem 1rem',
              borderRadius: '0.375rem',
              border: '1px solid #d1d5db',
              background: 'white',
              cursor: 'pointer',
              fontSize: '0.875rem',
            }}
          >
            Clear Filters
          </button>
        </div>
      </div>

      {selectedIds.length > 0 && (
        <div
          style={{
            marginBottom: '1rem',
            padding: '1rem',
            background: '#f3f4f6',
            borderRadius: '0.375rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span style={{ fontWeight: '500' }}>
            {selectedIds.length} item{selectedIds.length > 1 ? 's' : ''} selected (current page only)
          </span>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button
              onClick={() => setBulkAction('approve')}
              style={{
                padding: '0.5rem 1rem',
                background: '#10b981',
                color: 'white',
                borderRadius: '0.375rem',
                border: 'none',
                cursor: 'pointer',
                fontWeight: '500',
              }}
            >
              ✓ Approve Selected
            </button>
            <button
              onClick={() => setBulkAction('reject')}
              style={{
                padding: '0.5rem 1rem',
                background: '#ef4444',
                color: 'white',
                borderRadius: '0.375rem',
                border: 'none',
                cursor: 'pointer',
                fontWeight: '500',
              }}
            >
              ✕ Reject Selected
            </button>
          </div>
        </div>
      )}

      <DataTable
        columns={columns}
        data={items}
        keyExtractor={(item) => item.id}
        emptyMessage="No pending items match the current filters"
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

      {/* Bulk Approve Confirmation */}
      <Modal
        isOpen={bulkAction === 'approve'}
        onClose={() => setBulkAction(null)}
        title="Confirm Bulk Approval"
        size="medium"
        footer={
          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
            <button
              onClick={() => setBulkAction(null)}
              style={{
                padding: '0.5rem 1rem',
                background: '#e5e7eb',
                borderRadius: '0.375rem',
                border: 'none',
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleBulkApprove}
              style={{
                padding: '0.5rem 1rem',
                background: '#10b981',
                color: 'white',
                borderRadius: '0.375rem',
                border: 'none',
                cursor: 'pointer',
                fontWeight: '500',
              }}
            >
              Approve {selectedIds.length} Items
            </button>
          </div>
        }
      >
        <p>
          Are you sure you want to approve <strong>{selectedIds.length}</strong> pending item
          {selectedIds.length > 1 ? 's' : ''}? This action cannot be undone.
        </p>
      </Modal>

      {/* Bulk Reject Confirmation */}
      <Modal
        isOpen={bulkAction === 'reject'}
        onClose={() => setBulkAction(null)}
        title="Confirm Bulk Rejection"
        size="medium"
        footer={
          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
            <button
              onClick={() => setBulkAction(null)}
              style={{
                padding: '0.5rem 1rem',
                background: '#e5e7eb',
                borderRadius: '0.375rem',
                border: 'none',
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleBulkReject}
              style={{
                padding: '0.5rem 1rem',
                background: '#ef4444',
                color: 'white',
                borderRadius: '0.375rem',
                border: 'none',
                cursor: 'pointer',
                fontWeight: '500',
              }}
            >
              Reject {selectedIds.length} Items
            </button>
          </div>
        }
      >
        <p>
          Are you sure you want to reject <strong>{selectedIds.length}</strong> pending item
          {selectedIds.length > 1 ? 's' : ''}? This action cannot be undone.
        </p>
      </Modal>
    </div>
  );
}
