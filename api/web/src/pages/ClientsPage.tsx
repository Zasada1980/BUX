import { useState, useEffect } from 'react';
import { DataTable } from '@/components/ui/DataTable';
import { Badge } from '@/components/ui/Badge';
import Spinner from '@/components/ui/Spinner';
import Pagination from '@/components/ui/Pagination';
import Modal from '@/components/ui/Modal';
import { useToast } from '@/contexts/ToastContext';
import { useApi } from '@/hooks/useApi';
import { apiClient } from '@/lib/apiClient';
import { formatMoney } from '@/utils/format';
import type { Client } from '@/types';

export default function ClientsPage() {
  const { showToast } = useToast();
  const [page, setPage] = useState(1);
  const [limit] = useState(20);
  const [clients, setClients] = useState<Client[]>([]);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'archived'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isArchiveModalOpen, setIsArchiveModalOpen] = useState(false);
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    contact: '',
    default_pricing_rule: '',
  });

  // Fetch clients with useApi hook
  const { loading, execute: fetchClients } = useApi(
    async (page: number, limit: number) => {
      const response = await apiClient.getClients(page, limit);
      const filteredItems = (response.items || []).filter((client: Client) => {
        const matchesStatus = statusFilter === 'all' || client.status === statusFilter;
        const matchesSearch = searchQuery === '' || 
          client.name.toLowerCase().includes(searchQuery.toLowerCase());
        return matchesStatus && matchesSearch;
      });
      setClients(filteredItems);
      setTotalPages(response.pages || 1);
      setTotalItems(response.total || 0);
      return response;
    },
    { showErrorToast: true }
  );

  useEffect(() => {
    fetchClients(page, limit);
  }, [page, limit, statusFilter, searchQuery]);

  const handleCreateClient = async () => {
    if (!formData.name.trim()) {
      showToast('Client name is required', 'error');
      return;
    }
    try {
      await apiClient.createClient(formData);
      showToast('Client created successfully', 'success');
      setIsCreateModalOpen(false);
      setFormData({ name: '', contact: '', default_pricing_rule: '' });
      setPage(1);
      fetchClients(1, limit);
    } catch (error: any) {
      showToast(error.message || 'Failed to create client', 'error');
    }
  };

  const handleArchiveClient = async () => {
    if (!selectedClient) return;
    try {
      await apiClient.updateClient(selectedClient.id, { status: 'archived' });
      showToast('Client archived successfully', 'success');
      setIsArchiveModalOpen(false);
      setSelectedClient(null);
      fetchClients(page, limit);
    } catch (error: any) {
      showToast(error.message || 'Failed to archive client', 'error');
    }
  };

  const columns = [
    { key: 'id', label: 'ID', sortable: true },
    { key: 'name', label: 'Name', sortable: true },
    { key: 'contact', label: 'Contact' },
    { key: 'default_pricing_rule', label: 'Pricing Rule' },
    {
      key: 'total_invoiced',
      label: 'Total Invoiced',
      render: (client: Client) => formatMoney(client.total_invoiced || 0),
      sortable: true,
    },
    {
      key: 'status',
      label: 'Status',
      render: (client: Client) => <Badge variant="status" value={client.status} />,
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (client: Client) => (
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {client.status === 'active' && (
            <button
              onClick={() => {
                setSelectedClient(client);
                setIsArchiveModalOpen(true);
              }}
              style={{
                padding: '0.25rem 0.75rem',
                fontSize: '0.875rem',
                background: '#ef4444',
                color: 'white',
                borderRadius: '0.25rem',
                border: 'none',
                cursor: 'pointer',
              }}
            >
              Archive
            </button>
          )}
        </div>
      ),
      sortable: false,
    },
  ];

  if (loading && clients.length === 0) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
        <Spinner size="large" text="Loading clients..." />
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h1>Clients</h1>
        <button
          onClick={() => setIsCreateModalOpen(true)}
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
          + Add Client
        </button>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
        <div style={{ flex: 1 }}>
          <input
            type="text"
            placeholder="Search by name..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
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
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value as any);
              setPage(1);
            }}
            style={{
              padding: '0.5rem 1rem',
              border: '1px solid #d1d5db',
              borderRadius: '0.375rem',
              background: 'white',
            }}
          >
            <option value="all">All Statuses</option>
            <option value="active">Active</option>
            <option value="archived">Archived</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={clients}
        keyExtractor={(client) => client.id}
        emptyMessage="No clients found"
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

      {/* Create Client Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => {
          setIsCreateModalOpen(false);
          setFormData({ name: '', contact: '', default_pricing_rule: '' });
        }}
        title="Create New Client"
        size="medium"
        footer={
          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
            <button
              onClick={() => setIsCreateModalOpen(false)}
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
              onClick={handleCreateClient}
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
              Create Client
            </button>
          </div>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
              Name <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="Enter client name (max 200 characters)"
              maxLength={200}
              style={{
                width: '100%',
                padding: '0.5rem',
                border: '1px solid #d1d5db',
                borderRadius: '0.375rem',
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
              Contact Info
            </label>
            <input
              type="text"
              value={formData.contact}
              onChange={(e) => setFormData({ ...formData, contact: e.target.value })}
              placeholder="Phone, email, or address (optional)"
              style={{
                width: '100%',
                padding: '0.5rem',
                border: '1px solid #d1d5db',
                borderRadius: '0.375rem',
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
              Default Pricing Rule
            </label>
            <select
              value={formData.default_pricing_rule}
              onChange={(e) => setFormData({ ...formData, default_pricing_rule: e.target.value })}
              style={{
                width: '100%',
                padding: '0.5rem',
                border: '1px solid #d1d5db',
                borderRadius: '0.375rem',
              }}
            >
              <option value="">-- Select Pricing Rule --</option>
              <option value="hourly">Hourly Rate</option>
              <option value="daily">Daily Rate</option>
              <option value="fixed">Fixed Price</option>
            </select>
          </div>
        </div>
      </Modal>

      {/* Archive Confirmation Modal */}
      <Modal
        isOpen={isArchiveModalOpen}
        onClose={() => {
          setIsArchiveModalOpen(false);
          setSelectedClient(null);
        }}
        title="Archive Client"
        size="small"
        footer={
          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
            <button
              onClick={() => setIsArchiveModalOpen(false)}
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
              onClick={handleArchiveClient}
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
              Archive
            </button>
          </div>
        }
      >
        <p>
          Are you sure you want to archive <strong>{selectedClient?.name}</strong>?
          This action cannot be undone if there are draft invoices associated with this client.
        </p>
      </Modal>
    </div>
  );
}
