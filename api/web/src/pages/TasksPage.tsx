import { useState, useEffect } from 'react';
import { DataTable } from '@/components/ui/DataTable';
import { Badge } from '@/components/ui/Badge';
import Spinner from '@/components/ui/Spinner';
import Pagination from '@/components/ui/Pagination';
import Modal from '@/components/ui/Modal';
import { useToast } from '@/contexts/ToastContext';
import { useApi } from '@/hooks/useApi';
import { apiClient } from '@/lib/apiClient';
import { formatMoney, formatDate } from '@/utils/format';
import type { Task } from '@/types';
import { exportToCsv, getCurrentDateForFilename } from '@/lib/exportCsv';

export default function TasksPage() {
  const { showToast } = useToast();
  const [page, setPage] = useState(1);
  const [limit] = useState(50);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [isViewModalOpen, setIsViewModalOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);

  // Fetch tasks with useApi hook
  const { loading, execute: fetchTasks } = useApi(
    async () => {
      const filters: Record<string, any> = {};
      if (statusFilter !== 'all') filters.status = statusFilter;
      if (dateFrom) filters.date_from = dateFrom;
      if (dateTo) filters.date_to = dateTo;
      
      const response = await apiClient.getTasks(filters);
      setTasks(response.items || []);
      setTotalPages(response.pages || 1);
      setTotalItems(response.total || 0);
      return response;
    },
    { showErrorToast: true }
  );

  useEffect(() => {
    fetchTasks();
  }, [statusFilter, dateFrom, dateTo, fetchTasks]);

  const handleExportCSV = () => {
    try {
      exportToCsv(
        tasks,
        [
          { key: 'id', label: 'ID' },
          { key: 'worker_name', label: 'Worker' },
          { key: 'client_name', label: 'Client' },
          { key: 'description', label: 'Description' },
          { key: 'pricing_rule', label: 'Pricing Rule' },
          { key: 'quantity', label: 'Quantity', format: (val) => Number(val).toFixed(2) },
          { key: 'amount', label: 'Amount (ILS)', format: (val) => formatMoney(val) },
          { key: 'date', label: 'Date', format: (val) => formatDate(val) },
          { key: 'status', label: 'Status' },
        ],
        `tasks_${getCurrentDateForFilename()}`
      );
      showToast('CSV exported successfully', 'success');
    } catch (error: any) {
      showToast(error?.message || 'Failed to export CSV', 'error');
    }
  };

  const columns = [
    { key: 'id', label: 'ID', sortable: true },
    { key: 'worker_name', label: 'Worker', sortable: true },
    { key: 'client_name', label: 'Client', sortable: true },
    {
      key: 'description',
      label: 'Description',
      render: (task: Task) => {
        const truncated = task.description.length > 50 
          ? task.description.substring(0, 50) + '...' 
          : task.description;
        return (
          <span title={task.description} style={{ cursor: 'help' }}>
            {truncated}
          </span>
        );
      },
    },
    { key: 'pricing_rule', label: 'Pricing Rule' },
    {
      key: 'quantity',
      label: 'Qty',
      render: (task: Task) => task.quantity.toFixed(2),
    },
    {
      key: 'amount',
      label: 'Amount',
      render: (task: Task) => formatMoney(task.amount),
      sortable: true,
    },
    {
      key: 'date',
      label: 'Date',
      render: (task: Task) => formatDate(task.date),
      sortable: true,
    },
    {
      key: 'status',
      label: 'Status',
      render: (task: Task) => <Badge variant="status" value={task.status} />,
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (task: Task) => (
        <button
          onClick={() => {
            setSelectedTask(task);
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

  if (loading && tasks.length === 0) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
        <Spinner size="large" text="Loading tasks..." />
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h1>Tasks</h1>
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

      {/* Filters */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
        <div>
          <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: '500' }}>
            Status
          </label>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            style={{
              width: '100%',
              padding: '0.5rem',
              border: '1px solid #d1d5db',
              borderRadius: '0.375rem',
              background: 'white',
            }}
          >
            <option value="all">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="archived">Archived</option>
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
              setStatusFilter('all');
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
        <span style={{ fontWeight: '500', color: '#3b82f6' }}>ℹ️ Note:</span> Worker and Client multiselect filters will be added in a future phase.
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={tasks}
        keyExtractor={(task) => task.id}
        emptyMessage="No tasks found"
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

      {/* View Task Modal */}
      <Modal
        isOpen={isViewModalOpen}
        onClose={() => {
          setIsViewModalOpen(false);
          setSelectedTask(null);
        }}
        title={`Task #${selectedTask?.id || ''}`}
        size="medium"
      >
        {selectedTask && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <div style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.25rem' }}>Worker</div>
                <div style={{ fontWeight: '500' }}>{selectedTask.worker_name || `ID ${selectedTask.worker_id}`}</div>
              </div>
              <div>
                <div style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.25rem' }}>Client</div>
                <div style={{ fontWeight: '500' }}>{selectedTask.client_name || `ID ${selectedTask.client_id}`}</div>
              </div>
            </div>

            <div>
              <div style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.25rem' }}>Description</div>
              <div style={{ whiteSpace: 'pre-wrap' }}>{selectedTask.description}</div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem' }}>
              <div>
                <div style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.25rem' }}>Pricing Rule</div>
                <div style={{ fontWeight: '500' }}>{selectedTask.pricing_rule}</div>
              </div>
              <div>
                <div style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.25rem' }}>Quantity</div>
                <div style={{ fontWeight: '500' }}>{selectedTask.quantity.toFixed(2)}</div>
              </div>
              <div>
                <div style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.25rem' }}>Amount</div>
                <div style={{ fontWeight: '500', color: '#059669' }}>{formatMoney(selectedTask.amount)}</div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <div style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.25rem' }}>Date</div>
                <div>{formatDate(selectedTask.date)}</div>
              </div>
              <div>
                <div style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.25rem' }}>Status</div>
                <div><Badge variant="status" value={selectedTask.status} /></div>
              </div>
            </div>

            <div style={{ padding: '1rem', background: '#f9fafb', borderRadius: '0.375rem', marginTop: '0.5rem' }}>
              <div style={{ fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>Pricing Calculation</div>
              <div style={{ fontSize: '0.875rem', color: '#6b7280' }}>
                {selectedTask.pricing_rule === 'hourly' && `${selectedTask.quantity} hours × Rate = ${formatMoney(selectedTask.amount)}`}
                {selectedTask.pricing_rule === 'daily' && `${selectedTask.quantity} days × Rate = ${formatMoney(selectedTask.amount)}`}
                {selectedTask.pricing_rule === 'fixed' && `Fixed price: ${formatMoney(selectedTask.amount)}`}
                {!['hourly', 'daily', 'fixed'].includes(selectedTask.pricing_rule) && `${selectedTask.quantity} units = ${formatMoney(selectedTask.amount)}`}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
