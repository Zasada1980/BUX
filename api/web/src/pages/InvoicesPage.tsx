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
import type { Invoice } from '@/types';

/**
 * InvoicesPage — Invoice management with filtering and details modal (F7-3 Complete)
 * 
 * Features:
 * - Pagination: ✅ Client-side pagination (20 per page)
 * - Filtering: ✅ By status, client, date range
 * - Invoice details: ✅ Modal with items breakdown
 * - CSV Export: ✅ Enabled (F7-3) — exports filtered data to CSV (max 10,000 rows)
 * 
 * Backend: GET /api/invoices (list), GET /api/invoices/export (CSV)
 * Routes: /invoices
 * Auth: Admin only
 * 
 * UX Coverage:
 * - CSV Export: ✅ Functional with filters + 10K row limit
 * - Filter by status: draft/sent/paid/cancelled/all
 * - Filter by client: dropdown (all clients)
 * - Filter by date range: date_from → date_to
 */

interface Client {
  id: number;
  name: string;
}

interface InvoiceDetails {
  id: number;
  client_name: string;
  date_from: string;
  date_to: string;
  status: string;
  total_amount: number;
  subtotal: number;
  tax: number;
  items: Array<{
    type: string;
    description: string;
    quantity: number;
    unit_price: number;
    amount: number;
  }>;
}

export default function InvoicesPage() {
  const { showToast } = useToast();
  const [page, setPage] = useState(1);
  const [limit] = useState(20);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [clientFilter, setClientFilter] = useState<string>('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [clients, setClients] = useState<Client[]>([]);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState<InvoiceDetails | null>(null);

  // Fetch clients for filter dropdown
  useEffect(() => {
    const loadClients = async () => {
      try {
        const response = await fetch('/api/clients', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token') || sessionStorage.getItem('access_token')}`,
          },
        });
        if (response.ok) {
          const data = await response.json();
          setClients(data.items || []);
        }
      } catch (error) {
        console.error('Failed to load clients:', error);
      }
    };
    loadClients();
  }, []);

  // Fetch invoices with useApi hook
  const { loading, error, execute: fetchInvoices } = useApi(
    async (page: number, limit: number) => {
      const response = await apiClient.getInvoices(page, limit);
      const filteredItems = (response.items || []).filter((invoice: Invoice) => {
        const matchesStatus = statusFilter === 'all' || invoice.status === statusFilter;
        const matchesClient = clientFilter === 'all' || invoice.client_id === Number(clientFilter);
        let matchesDate = true;
        if (dateFrom && invoice.date_from) {
          matchesDate = matchesDate && new Date(invoice.date_from) >= new Date(dateFrom);
        }
        if (dateTo && invoice.date_to) {
          matchesDate = matchesDate && new Date(invoice.date_to) <= new Date(dateTo);
        }
        return matchesStatus && matchesClient && matchesDate;
      });
      setInvoices(filteredItems);
      setTotalPages(response.pages || 1);
      setTotalItems(response.total || 0);
      return response;
    },
    { showErrorToast: true }
  );

  useEffect(() => {
    fetchInvoices(page, limit);
  }, [page, limit, statusFilter, clientFilter, dateFrom, dateTo]);

  const handleViewDetails = async (invoiceId: number) => {
    try {
      const response = await fetch(`/api/invoices/${invoiceId}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token') || sessionStorage.getItem('access_token')}`,
        },
      });
      if (response.ok) {
        const details = await response.json();
        setSelectedInvoice(details);
        setDetailModalOpen(true);
      } else {
        showToast('Failed to load invoice details', 'error');
      }
    } catch (error: any) {
      showToast(error.message || 'Failed to load invoice details', 'error');
    }
  };

  const columns = [
    { key: 'id', label: 'ID', sortable: true },
    { key: 'client_name', label: 'Client', sortable: true },
    {
      key: 'total_amount',
      label: 'Total',
      render: (invoice: Invoice) => formatMoney(invoice.total_amount),
      sortable: true,
    },
    { key: 'items_count', label: 'Items', sortable: true },
    {
      key: 'date_range',
      label: 'Date Range',
      render: (invoice: Invoice) => {
        if (invoice.date_from && invoice.date_to) {
          return `${formatDate(invoice.date_from)} - ${formatDate(invoice.date_to)}`;
        }
        return '—';
      },
    },
    {
      key: 'status',
      label: 'Status',
      render: (invoice: Invoice) => <Badge variant="status" value={invoice.status} />,
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (invoice: Invoice) => (
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            onClick={() => handleViewDetails(invoice.id)}
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
        </div>
      ),
      sortable: false,
    },
  ];

  // CSV Export handler - ENABLED in F7-3
  const handleExport = async () => {
    try {
      const filters: Record<string, any> = {};
      if (statusFilter !== 'all') filters.status = statusFilter;
      if (clientFilter !== 'all') filters.client_id = clientFilter;
      if (dateFrom) filters.date_from = dateFrom;
      if (dateTo) filters.date_to = dateTo;

      const blob = await apiClient.exportInvoicesCSV(filters);

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `invoices_${new Date().toISOString().replace(/[-:]/g, '').split('.')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);

      showToast('CSV exported successfully', 'success');
    } catch (error: any) {
      showToast(error?.message || 'Failed to export CSV', 'error');
    }
  };

  if (loading && invoices.length === 0) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
        <Spinner size="large" text="Loading invoices..." />
      </div>
    );
  }

  // F4.4 FIX: Show error state if API fails
  if (error && invoices.length === 0) {
    return (
      <div style={{ padding: '3rem', textAlign: 'center' }}>
        <div style={{ color: '#dc2626', fontSize: '1.125rem', fontWeight: '500', marginBottom: '0.5rem' }}>
          Failed to load invoices
        </div>
        <div style={{ color: '#6b7280', marginBottom: '1rem' }}>
          {error}
        </div>
        <button
          onClick={() => fetchInvoices(page, limit)}
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
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h1>Invoices</h1>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            onClick={handleExport}
            disabled={false}
            title="Export filtered invoices to CSV (max 10,000 rows)"
            style={{
              padding: '0.5rem 1rem',
              background: '#10b981',
              color: 'white',
              borderRadius: '0.375rem',
              border: 'none',
              cursor: 'pointer',
              fontWeight: '500',
              opacity: 1,
            }}
          >
            📊 Export CSV
          </button>
          <button
            onClick={() => showToast('Invoice wizard will be implemented in a future phase', 'info')}
            style={{
              padding: '0.5rem 1rem',
              background: '#3b82f6',
              color: 'white',
              borderRadius: '0.375rem',
              border: 'none',
              cursor: 'pointer',
              fontWeight: '500',
            }}
          >
            + Create Invoice
          </button>
        </div>
      </div>

      {/* AI Placeholder (Phase 3 - PRESERVED) */}
      <div style={{ marginBottom: '2rem', padding: '1.5rem', background: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)', borderRadius: '0.5rem', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', color: '#1a202c' }}>
        <h2 style={{ marginBottom: '0.5rem' }}>💡 AI Invoice Optimization (Phase 3)</h2>
        <p style={{ opacity: 0.9, fontSize: '0.95rem' }}>
          AI-powered invoice generation with smart recommendations:
        </p>
        <ul style={{ marginTop: '1rem', opacity: 0.8, fontSize: '0.875rem', paddingLeft: '1.5rem' }}>
          <li>Auto-suggest invoice amounts based on work patterns</li>
          <li>Detect missing expenses or tasks in invoices</li>
          <li>Optimize invoice timing for cash flow</li>
        </ul>
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
            <option value="draft">Draft</option>
            <option value="issued">Issued</option>
            <option value="paid">Paid</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: '500' }}>
            Client
          </label>
          <select
            value={clientFilter}
            onChange={(e) => {
              setClientFilter(e.target.value);
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
            <option value="all">All Clients</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
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
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <button
          onClick={() => {
            setStatusFilter('all');
            setClientFilter('all');
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

      {/* Info badge */}
      <div style={{ marginBottom: '1rem', padding: '0.75rem', background: '#eff6ff', borderRadius: '0.375rem', fontSize: '0.875rem' }}>
        <span style={{ fontWeight: '500', color: '#3b82f6' }}>ℹ️ Note:</span> 4-step invoice wizard will be implemented in a future phase.
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={invoices}
        keyExtractor={(invoice) => invoice.id}
        emptyMessage="No invoices found"
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

      {/* Invoice Detail Modal */}
      <Modal
        isOpen={detailModalOpen}
        onClose={() => setDetailModalOpen(false)}
        title="Invoice Details"
        size="large"
      >
        {selectedInvoice ? (
          <div>
            {/* Invoice Header */}
            <div style={{ marginBottom: '1.5rem', padding: '1rem', background: '#f9fafb', borderRadius: '0.375rem' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '0.75rem' }}>
                <div>
                  <div style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.25rem' }}>Client</div>
                  <div style={{ fontWeight: '500' }}>{selectedInvoice.client_name}</div>
                </div>
                <div>
                  <div style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.25rem' }}>Status</div>
                  <div>
                    <span
                      style={{
                        padding: '0.25rem 0.75rem',
                        borderRadius: '9999px',
                        fontSize: '0.75rem',
                        fontWeight: '500',
                        background:
                          selectedInvoice.status === 'paid'
                            ? '#d1fae5'
                            : selectedInvoice.status === 'issued'
                            ? '#fef3c7'
                            : selectedInvoice.status === 'cancelled'
                            ? '#fee2e2'
                            : '#e5e7eb',
                        color:
                          selectedInvoice.status === 'paid'
                            ? '#065f46'
                            : selectedInvoice.status === 'issued'
                            ? '#92400e'
                            : selectedInvoice.status === 'cancelled'
                            ? '#991b1b'
                            : '#374151',
                      }}
                    >
                      {selectedInvoice.status}
                    </span>
                  </div>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div>
                  <div style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.25rem' }}>Period</div>
                  <div>{new Date(selectedInvoice.date_from).toLocaleDateString()} — {new Date(selectedInvoice.date_to).toLocaleDateString()}</div>
                </div>
              </div>
            </div>

            {/* Line Items Table */}
            <div style={{ marginBottom: '1.5rem' }}>
              <h3 style={{ marginBottom: '0.75rem', fontSize: '1rem', fontWeight: '500' }}>Invoice Items</h3>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
                    <th style={{ padding: '0.75rem', textAlign: 'left', fontSize: '0.875rem', fontWeight: '500' }}>Type</th>
                    <th style={{ padding: '0.75rem', textAlign: 'left', fontSize: '0.875rem', fontWeight: '500' }}>Description</th>
                    <th style={{ padding: '0.75rem', textAlign: 'right', fontSize: '0.875rem', fontWeight: '500' }}>Qty</th>
                    <th style={{ padding: '0.75rem', textAlign: 'right', fontSize: '0.875rem', fontWeight: '500' }}>Price</th>
                    <th style={{ padding: '0.75rem', textAlign: 'right', fontSize: '0.875rem', fontWeight: '500' }}>Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedInvoice.items.map((item, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid #e5e7eb' }}>
                      <td style={{ padding: '0.75rem', fontSize: '0.875rem' }}>{item.type}</td>
                      <td style={{ padding: '0.75rem', fontSize: '0.875rem' }}>{item.description}</td>
                      <td style={{ padding: '0.75rem', textAlign: 'right', fontSize: '0.875rem' }}>{item.quantity}</td>
                      <td style={{ padding: '0.75rem', textAlign: 'right', fontSize: '0.875rem' }}>{formatMoney(item.unit_price)}</td>
                      <td style={{ padding: '0.75rem', textAlign: 'right', fontSize: '0.875rem' }}>{formatMoney(item.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Totals Section */}
            <div style={{ borderTop: '2px solid #e5e7eb', paddingTop: '1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '0.5rem' }}>
                <div style={{ width: '250px', display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem' }}>
                  <span style={{ color: '#6b7280' }}>Subtotal:</span>
                  <span style={{ fontWeight: '500' }}>{formatMoney(selectedInvoice.subtotal)}</span>
                </div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '0.5rem' }}>
                <div style={{ width: '250px', display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem' }}>
                  <span style={{ color: '#6b7280' }}>Tax:</span>
                  <span style={{ fontWeight: '500' }}>{formatMoney(selectedInvoice.tax)}</span>
                </div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '0.5rem', borderTop: '1px solid #e5e7eb' }}>
                <div style={{ width: '250px', display: 'flex', justifyContent: 'space-between', fontSize: '1rem' }}>
                  <span style={{ fontWeight: '600' }}>Total:</span>
                  <span style={{ fontWeight: '600', color: '#3b82f6' }}>{formatMoney(selectedInvoice.total_amount)}</span>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#6b7280' }}>
            Loading invoice details...
          </div>
        )}
      </Modal>
    </div>
  );
}
