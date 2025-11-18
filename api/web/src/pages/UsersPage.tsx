import { useState, useEffect } from 'react';
import { DataTable } from '@/components/ui/DataTable';
import { Badge } from '@/components/ui/Badge';
import Spinner from '@/components/ui/Spinner';
import Pagination from '@/components/ui/Pagination';
import Modal from '@/components/ui/Modal';
import { useToast } from '@/contexts/ToastContext';
import { useApi } from '@/hooks/useApi';
import { apiClient } from '@/lib/apiClient';
import type { User } from '@/types';
import { exportToCsv, getCurrentDateForFilename } from '@/lib/exportCsv';

/**
 * UsersPage — Full CRUD User Management (F7 Restoration)
 * 
 * Features:
 * - Users table: Read-only view (ID, Name, Telegram ID, Role, Status)
 * - CRUD operations: ✅ Add/Edit/Activate/Deactivate users
 * - CSV Export: ✅ Client-side export
 * - Error handling: Empty/loading/error states
 * 
 * See UX_PLAYBOOK v2.0 (Scenario 2: Fully Supported)
 */
export default function UsersPage() {
  const { showToast } = useToast();
  const [page, setPage] = useState(1);
  const [limit] = useState(20);
  const [users, setUsers] = useState<User[]>([]);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);

  // CRUD state (F7 restoration)
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    telegram_id: '',
    role: 'worker',
  });
  const [submitting, setSubmitting] = useState(false);

  // Fetch users with useApi hook
  const { loading, error, execute: fetchUsers } = useApi(
    async (page: number, limit: number) => {
      console.log('[UsersPage] Fetching users...', { page, limit });
      const response = await apiClient.getUsers(page, limit);
      console.log('[UsersPage] API response:', response);
      setUsers(response.items || []);
      setTotalPages(response.pages || 1);
      setTotalItems(response.total || 0);
      return response;
    },
    { showErrorToast: true }
  );

  useEffect(() => {
    fetchUsers(page, limit);
  }, [page, limit]);

  // CRUD handlers (F7 restoration)
  const handleCreateUser = async () => {
    if (!formData.name || !formData.telegram_id) {
      showToast('Name and Telegram ID are required', 'error');
      return;
    }

    setSubmitting(true);
    try {
      await apiClient.createUser({
        name: formData.name,
        telegram_id: formData.telegram_id,
        role: formData.role as 'worker' | 'foreman' | 'admin',
        status: 'active',
      });
      showToast('User created successfully', 'success');
      setIsCreateModalOpen(false);
      setFormData({ name: '', telegram_id: '', role: 'worker' });
      fetchUsers(page, limit);
    } catch (error: any) {
      showToast(error?.message || 'Failed to create user', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEditClick = (user: User) => {
    setEditingUser(user);
    setFormData({
      name: user.name,
      telegram_id: user.telegram_id?.toString() || '',
      role: user.role,
    });
    setIsEditModalOpen(true);
  };

  const handleEditUser = async () => {
    if (!editingUser || !formData.name) {
      showToast('Name is required', 'error');
      return;
    }

    setSubmitting(true);
    try {
      await apiClient.updateUser(editingUser.id, {
        name: formData.name,
        role: formData.role as 'worker' | 'foreman' | 'admin',
      });
      showToast('User updated successfully', 'success');
      setIsEditModalOpen(false);
      setEditingUser(null);
      setFormData({ name: '', telegram_id: '', role: 'worker' });
      fetchUsers(page, limit);
    } catch (error: any) {
      showToast(error?.message || 'Failed to update user', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleStatus = async (user: User) => {
    const action = user.status === 'active' ? 'deactivate' : 'activate';
    const confirmMsg = `Are you sure you want to ${action} ${user.name}?`;
    
    if (!window.confirm(confirmMsg)) {
      return;
    }

    try {
      if (user.status === 'active') {
        await apiClient.deactivateUser(user.id);
        showToast(`${user.name} deactivated`, 'success');
      } else {
        await apiClient.activateUser(user.id);
        showToast(`${user.name} activated`, 'success');
      }
      fetchUsers(page, limit);
    } catch (error: any) {
      showToast(error?.message || `Failed to ${action} user`, 'error');
    }
  };

  const handleExportCsv = () => {
    try {
      exportToCsv(
        users,
        [
          { key: 'id', label: 'ID' },
          { key: 'name', label: 'Name' },
          { key: 'telegram_id', label: 'Telegram ID' },
          { key: 'role', label: 'Role' },
          { key: 'status', label: 'Status' },
        ],
        `users_${getCurrentDateForFilename()}`
      );
      showToast('CSV exported successfully', 'success');
    } catch (error: any) {
      showToast(error?.message || 'Failed to export CSV', 'error');
    }
  };

  const columns = [
    { key: 'id', label: 'ID', sortable: true },
    { key: 'name', label: 'Name', sortable: true },
    { key: 'telegram_id', label: 'Telegram ID' },
    {
      key: 'role',
      label: 'Role',
      render: (user: User) => <Badge variant="role" value={user.role} />,
    },
    {
      key: 'status',
      label: 'Status',
      render: (user: User) => <Badge variant="status" value={user.status} />,
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (user: User) => (
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            onClick={() => handleEditClick(user)}
            style={{
              padding: '0.25rem 0.75rem',
              fontSize: '0.875rem',
              backgroundColor: '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '0.25rem',
              cursor: 'pointer',
            }}
          >
            Edit
          </button>
          <button
            onClick={() => handleToggleStatus(user)}
            style={{
              padding: '0.25rem 0.75rem',
              fontSize: '0.875rem',
              backgroundColor: user.status === 'active' ? '#ef4444' : '#10b981',
              color: 'white',
              border: 'none',
              borderRadius: '0.25rem',
              cursor: 'pointer',
            }}
          >
            {user.status === 'active' ? 'Deactivate' : 'Activate'}
          </button>
        </div>
      ),
    },
  ];

  if (loading && users.length === 0) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
        <Spinner size="large" text="Loading users..." />
      </div>
    );
  }

  if (error && users.length === 0) {
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
            Failed to load users
          </div>
          <div style={{ color: '#dc2626', marginBottom: '1rem' }}>{error}</div>
          <button
            onClick={() => fetchUsers(page, limit)}
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h1>Users</h1>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            onClick={handleExportCsv}
            disabled={users.length === 0}
            style={{
              padding: '0.5rem 1rem',
              backgroundColor: users.length === 0 ? '#9ca3af' : '#10b981',
              color: 'white',
              border: 'none',
              borderRadius: '0.375rem',
              cursor: users.length === 0 ? 'not-allowed' : 'pointer',
              fontWeight: '500',
            }}
          >
            📥 Export CSV
          </button>
          <button
            onClick={() => setIsCreateModalOpen(true)}
            style={{
              padding: '0.5rem 1rem',
              backgroundColor: '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '0.375rem',
              cursor: 'pointer',
              fontWeight: '500',
            }}
          >
            + Add User
          </button>
        </div>
      </div>
      
      <DataTable
        columns={columns}
        data={users}
        keyExtractor={(user) => user.id}
        emptyMessage="No users found"
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

      {/* Create User Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => {
          setIsCreateModalOpen(false);
          setFormData({ name: '', telegram_id: '', role: 'worker' });
        }}
        title="Add New User"
        size="medium"
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
              style={{
                width: '100%',
                padding: '0.5rem',
                border: '1px solid #d1d5db',
                borderRadius: '0.375rem',
              }}
              placeholder="Enter user name"
            />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
              Telegram ID <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <input
              type="number"
              value={formData.telegram_id}
              onChange={(e) => setFormData({ ...formData, telegram_id: e.target.value })}
              style={{
                width: '100%',
                padding: '0.5rem',
                border: '1px solid #d1d5db',
                borderRadius: '0.375rem',
              }}
              placeholder="Enter Telegram ID"
            />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
              Role <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <select
              value={formData.role}
              onChange={(e) => setFormData({ ...formData, role: e.target.value })}
              style={{
                width: '100%',
                padding: '0.5rem',
                border: '1px solid #d1d5db',
                borderRadius: '0.375rem',
              }}
            >
              <option value="worker">Worker</option>
              <option value="foreman">Foreman</option>
              <option value="admin">Admin</option>
            </select>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '1rem' }}>
            <button
              onClick={() => {
                setIsCreateModalOpen(false);
                setFormData({ name: '', telegram_id: '', role: 'worker' });
              }}
              disabled={submitting}
              style={{
                padding: '0.5rem 1rem',
                backgroundColor: '#6b7280',
                color: 'white',
                border: 'none',
                borderRadius: '0.375rem',
                cursor: submitting ? 'not-allowed' : 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleCreateUser}
              disabled={submitting}
              style={{
                padding: '0.5rem 1rem',
                backgroundColor: submitting ? '#9ca3af' : '#3b82f6',
                color: 'white',
                border: 'none',
                borderRadius: '0.375rem',
                cursor: submitting ? 'not-allowed' : 'pointer',
              }}
            >
              {submitting ? 'Creating...' : 'Create User'}
            </button>
          </div>
        </div>
      </Modal>

      {/* Edit User Modal */}
      <Modal
        isOpen={isEditModalOpen}
        onClose={() => {
          setIsEditModalOpen(false);
          setEditingUser(null);
          setFormData({ name: '', telegram_id: '', role: 'worker' });
        }}
        title="Edit User"
        size="medium"
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
              Telegram ID
            </label>
            <input
              type="number"
              value={formData.telegram_id}
              disabled
              style={{
                width: '100%',
                padding: '0.5rem',
                border: '1px solid #d1d5db',
                borderRadius: '0.375rem',
                backgroundColor: '#f3f4f6',
                cursor: 'not-allowed',
              }}
            />
            <p style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '0.25rem' }}>
              Telegram ID cannot be changed
            </p>
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
              Role <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <select
              value={formData.role}
              onChange={(e) => setFormData({ ...formData, role: e.target.value })}
              style={{
                width: '100%',
                padding: '0.5rem',
                border: '1px solid #d1d5db',
                borderRadius: '0.375rem',
              }}
            >
              <option value="worker">Worker</option>
              <option value="foreman">Foreman</option>
              <option value="admin">Admin</option>
            </select>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '1rem' }}>
            <button
              onClick={() => {
                setIsEditModalOpen(false);
                setEditingUser(null);
                setFormData({ name: '', telegram_id: '', role: 'worker' });
              }}
              disabled={submitting}
              style={{
                padding: '0.5rem 1rem',
                backgroundColor: '#6b7280',
                color: 'white',
                border: 'none',
                borderRadius: '0.375rem',
                cursor: submitting ? 'not-allowed' : 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleEditUser}
              disabled={submitting}
              style={{
                padding: '0.5rem 1rem',
                backgroundColor: submitting ? '#9ca3af' : '#3b82f6',
                color: 'white',
                border: 'none',
                borderRadius: '0.375rem',
                cursor: submitting ? 'not-allowed' : 'pointer',
              }}
            >
              {submitting ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
