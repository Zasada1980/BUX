import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { DataTable } from '@/components/ui/DataTable';
import Spinner from '@/components/ui/Spinner';
import Pagination from '@/components/ui/Pagination';
import Modal from '@/components/ui/Modal';
import { useToast } from '@/contexts/ToastContext';
import { useApi } from '@/hooks/useApi';
import { apiClient } from '@/lib/apiClient';
import { formatDate } from '@/utils/format';
import type { Shift } from '@/types';
import { exportToCsv, getCurrentDateForFilename } from '@/lib/exportCsv';

export default function ShiftsPage() {
  const { showToast } = useToast();
  const [page, setPage] = useState(1);
  const [limit] = useState(50);
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [isViewModalOpen, setIsViewModalOpen] = useState(false);
  const [selectedShift, setSelectedShift] = useState<Shift | null>(null);

  // Fetch shifts with useApi hook
  const { loading, error, execute: fetchShifts } = useApi(
    async () => {
      const filters: Record<string, any> = {};
      if (dateFrom) filters.date_from = dateFrom;
      if (dateTo) filters.date_to = dateTo;
      
      const response = await apiClient.getShifts(filters);
      setShifts(response.items || []);
      setTotalPages(response.pages || 1);
      setTotalItems(response.total || 0);
      return response;
    },
    { showErrorToast: true }
  );

  // F5.2 FIX: Remove fetchShifts from deps to prevent infinite loop
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    fetchShifts();
  }, [dateFrom, dateTo]);

  const formatDuration = (hours?: number): string => {
    if (!hours) return '—';
    const h = Math.floor(hours);
    const m = Math.round((hours - h) * 60);
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  };

  const formatTime = (datetime?: string): string => {
    if (!datetime) return '—';
    const date = new Date(datetime);
    return date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  };

  const formatDateTime = (datetime?: string): string => {
    if (!datetime) return '—';
    const date = new Date(datetime);
    return date.toLocaleString('en-GB', { 
      year: 'numeric', 
      month: '2-digit', 
      day: '2-digit', 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  const handleExportCSV = () => {
    try {
      exportToCsv(
        shifts,
        [
          { key: 'id', label: 'ID' },
          { key: 'user_id', label: 'Worker ID' },
          { key: 'created_at', label: 'Start Time', format: (val) => formatDateTime(val) },
          { key: 'ended_at', label: 'End Time', format: (val) => formatDateTime(val) },
          { key: 'duration_hours', label: 'Duration (hours)' },
          { key: 'status', label: 'Status' },
          { key: 'work_address', label: 'Work Address' },
        ],
        `shifts_${getCurrentDateForFilename()}`
      );
      showToast('CSV exported successfully', 'success');
    } catch (error: any) {
      showToast(error?.message || 'Failed to export CSV', 'error');
    }
  };

  const columns = [
    { key: 'id', label: 'ID', sortable: true },
    { 
      key: 'user_id', 
      label: 'Worker', 
      render: (shift: any) => shift.user_id || '—',
      sortable: true 
    },
    {
      key: 'created_at',
      label: 'Start',
      render: (shift: any) => formatDateTime(shift.created_at),
    },
    {
      key: 'ended_at',
      label: 'End',
      render: (shift: any) => formatDateTime(shift.ended_at),
    },
    {
      key: 'duration_hours',
      label: 'Duration',
      render: (shift: any) => formatDuration(shift.duration_hours),
      sortable: true,
    },
    {
      key: 'status',
      label: 'Status',
      render: (shift: any) => (
        <span style={{
          padding: '0.25rem 0.5rem',
          borderRadius: '0.25rem',
          fontSize: '0.75rem',
          fontWeight: '500',
          background: shift.status === 'open' ? '#dbeafe' : '#d1fae5',
          color: shift.status === 'open' ? '#1e40af' : '#065f46',
        }}>
          {shift.status === 'open' ? '🟢 Open' : '✅ Closed'}
        </span>
      ),
      sortable: true,
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (shift: any) => (
        <button
          onClick={() => {
            setSelectedShift(shift);
            setIsViewModalOpen(true);
          }}
          style={{
            padding: '0.25rem 0.75rem',
            fontSize: '0.875rem',
            background: '#3b82f6',
            color: 'white',
            borderRadius: '0.25rem',
            border: 'none',
            cursor: 'pointer',
          }}
        >
          View
        </button>
      ),
      sortable: false,
    },
  ];

  if (loading && shifts.length === 0) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
        <Spinner size="large" text="Loading shifts..." />
      </div>
    );
  }

  if (error && shifts.length === 0) {
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
            Failed to load shifts
          </div>
          <div style={{ color: '#dc2626', marginBottom: '1rem' }}>{error}</div>
          <button
            onClick={() => fetchShifts()}
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
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h1>Shifts</h1>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <Link
            to="/shifts/calendar"
            style={{
              padding: '0.5rem 1rem',
              background: '#8b5cf6',
              color: 'white',
              borderRadius: '0.375rem',
              border: 'none',
              cursor: 'pointer',
              fontWeight: '500',
              textDecoration: 'none',
              display: 'inline-block',
            }}
          >
            📅 Calendar View
          </Link>
          <button
            onClick={handleExportCSV}
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
            📄 Export CSV
          </button>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
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
              width: '100%',
              padding: '0.5rem',
              border: '1px solid #d1d5db',
              borderRadius: '0.375rem',
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
              width: '100%',
              padding: '0.5rem',
              border: '1px solid #d1d5db',
              borderRadius: '0.375rem',
            }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <button
            onClick={() => {
              setDateFrom('');
              setDateTo('');
              setPage(1);
            }}
            style={{
              padding: '0.5rem 1rem',
              background: '#e5e7eb',
              borderRadius: '0.375rem',
              border: 'none',
              cursor: 'pointer',
              width: '100%',
            }}
          >
            Clear Filters
          </button>
        </div>
      </div>

      {/* Info badge */}
      <div style={{ marginBottom: '1rem', padding: '0.75rem', background: '#eff6ff', borderRadius: '0.375rem', fontSize: '0.875rem' }}>
        <span style={{ fontWeight: '500', color: '#3b82f6' }}>ℹ️ Note:</span> Worker multiselect filter will be added in a future phase.
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={shifts}
        keyExtractor={(shift) => shift.id}
        emptyMessage="No shifts found"
      />

      {/* Pagination */}
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

      {/* View Shift Modal */}
      <Modal
        isOpen={isViewModalOpen}
        onClose={() => {
          setIsViewModalOpen(false);
          setSelectedShift(null);
        }}
        title={`Shift #${selectedShift?.id || ''}`}
        size="medium"
      >
        {selectedShift && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <div style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.25rem' }}>Worker ID</div>
              <div style={{ fontWeight: '500', fontSize: '1.125rem' }}>{selectedShift.user_id || '—'}</div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <div style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.25rem' }}>Status</div>
                <div style={{ fontWeight: '500' }}>
                  <span style={{
                    padding: '0.25rem 0.5rem',
                    borderRadius: '0.25rem',
                    fontSize: '0.875rem',
                    background: selectedShift.status === 'open' ? '#dbeafe' : '#d1fae5',
                    color: selectedShift.status === 'open' ? '#1e40af' : '#065f46',
                  }}>
                    {selectedShift.status === 'open' ? '🟢 Open' : '✅ Closed'}
                  </span>
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.25rem' }}>Duration</div>
                <div style={{ fontWeight: '500', color: '#059669', fontSize: '1.125rem' }}>
                  {formatDuration(selectedShift.duration_hours)}
                </div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <div style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.25rem' }}>Start Time</div>
                <div style={{ fontWeight: '500' }}>
                  {formatDateTime(selectedShift.created_at)}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.25rem' }}>End Time</div>
                <div style={{ fontWeight: '500' }}>
                  {formatDateTime(selectedShift.ended_at)}
                </div>
              </div>
            </div>

            {selectedShift.work_address && (
              <div>
                <div style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.25rem' }}>Work Address</div>
                <div style={{ fontWeight: '500' }}>{selectedShift.work_address}</div>
              </div>
            )}

            {selectedShift.duration_hours && selectedShift.duration_hours > 8 && (
              <div style={{ padding: '1rem', background: '#fef3c7', borderRadius: '0.375rem', marginTop: '0.5rem' }}>
                <div style={{ fontSize: '0.875rem', fontWeight: '500', color: '#92400e' }}>⚠️ Overtime Alert</div>
                <div style={{ fontSize: '0.875rem', color: '#78350f', marginTop: '0.25rem' }}>
                  This shift exceeds standard 8 hours ({formatDuration(selectedShift.duration_hours)})
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
