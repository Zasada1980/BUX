import { API_ENDPOINTS } from '@/config/constants';
import type { User, Client, Task, Expense, Invoice, Shift, PendingItem, DashboardKPIs, PaginatedResponse, BotMenuResponse, UpdateBotMenuRequest, ApplyBotMenuResponse, ProfileData, PasswordChangeRequest, PasswordChangeResponse } from '@/types';

const BASE_URL = '';

class ApiClient {
  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    // Add custom headers from options
    if (options.headers) {
      Object.entries(options.headers).forEach(([key, value]) => {
        if (typeof value === 'string') {
          headers[key] = value;
        }
      });
    }

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      localStorage.removeItem('access_token');
      sessionStorage.removeItem('access_token');
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
      throw new Error(errorData.error || errorData.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // Generic GET method for endpoints not yet wrapped
  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  // Auth
  async login(username: string, password: string) {
    return this.request<{ token: string; refresh_token?: string; role: string; user_id: number; name: string; telegram_id?: string }>(
      API_ENDPOINTS.AUTH.LOGIN,
      {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      }
    );
  }

  // Users
  async getUsers(page = 1, limit = 20): Promise<PaginatedResponse<User>> {
    return this.request<PaginatedResponse<User>>(`${API_ENDPOINTS.USERS.LIST}?page=${page}&limit=${limit}`);
  }

  async getUser(id: number): Promise<User> {
    return this.request<User>(API_ENDPOINTS.USERS.GET(id));
  }

  async createUser(userData: Partial<User>): Promise<User> {
    return this.request<User>(API_ENDPOINTS.USERS.CREATE, {
      method: 'POST',
      body: JSON.stringify(userData),
    });
  }

  async updateUser(id: number, userData: Partial<User>): Promise<User> {
    return this.request<User>(API_ENDPOINTS.USERS.UPDATE(id), {
      method: 'PATCH',
      body: JSON.stringify(userData),
    });
  }

  async activateUser(id: number): Promise<User> {
    return this.request<User>(`/api/users/${id}/activate`, {
      method: 'POST',
    });
  }

  async deactivateUser(id: number): Promise<User> {
    return this.request<User>(`/api/users/${id}/deactivate`, {
      method: 'POST',
    });
  }

  async deleteUser(id: number): Promise<void> {
    return this.request<void>(API_ENDPOINTS.USERS.DELETE(id), {
      method: 'DELETE',
    });
  }

  // Clients
  async getClients(page = 1, limit = 20): Promise<PaginatedResponse<Client>> {
    return this.request<PaginatedResponse<Client>>(`${API_ENDPOINTS.CLIENTS.LIST}?page=${page}&limit=${limit}`);
  }

  async getClient(id: number): Promise<Client> {
    return this.request<Client>(API_ENDPOINTS.CLIENTS.GET(id));
  }

  async createClient(clientData: Partial<Client>): Promise<Client> {
    return this.request<Client>(API_ENDPOINTS.CLIENTS.CREATE, {
      method: 'POST',
      body: JSON.stringify(clientData),
    });
  }

  async updateClient(id: number, clientData: Partial<Client>): Promise<Client> {
    return this.request<Client>(API_ENDPOINTS.CLIENTS.UPDATE(id), {
      method: 'PUT',
      body: JSON.stringify(clientData),
    });
  }

  // Tasks
  async getTasks(filters?: Record<string, any>): Promise<PaginatedResponse<Task>> {
    const query = new URLSearchParams(filters).toString();
    return this.request<PaginatedResponse<Task>>(`${API_ENDPOINTS.TASKS.LIST}?${query}`);
  }

  async getTask(id: number): Promise<Task> {
    return this.request<Task>(API_ENDPOINTS.TASKS.GET(id));
  }

  // Expenses
  async getExpenses(filters?: Record<string, any>): Promise<PaginatedResponse<Expense>> {
    const query = new URLSearchParams(filters).toString();
    return this.request<PaginatedResponse<Expense>>(`${API_ENDPOINTS.EXPENSES.LIST}?${query}`);
  }

  async getExpense(id: number): Promise<Expense> {
    return this.request<Expense>(API_ENDPOINTS.EXPENSES.GET(id));
  }

  async exportExpensesCSV(filters?: Record<string, any>): Promise<Blob> {
    const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
    const query = filters ? new URLSearchParams(filters).toString() : '';
    const url = `${BASE_URL}${API_ENDPOINTS.EXPENSES.EXPORT}${query ? `?${query}` : ''}`;

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Authorization': token ? `Bearer ${token}` : '',
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ error: 'Export failed' }));
      throw new Error(errorData.detail?.message || errorData.error || `HTTP ${response.status}`);
    }

    return response.blob();
  }

  // Invoices
  async getInvoices(page = 1, limit = 20): Promise<PaginatedResponse<Invoice>> {
    return this.request<PaginatedResponse<Invoice>>(`${API_ENDPOINTS.INVOICES.LIST}?page=${page}&limit=${limit}`);
  }

  async getInvoice(id: number): Promise<Invoice> {
    return this.request<Invoice>(API_ENDPOINTS.INVOICES.GET(id));
  }

  async createInvoice(invoiceData: Partial<Invoice>): Promise<Invoice> {
    return this.request<Invoice>(API_ENDPOINTS.INVOICES.CREATE, {
      method: 'POST',
      body: JSON.stringify(invoiceData),
    });
  }

  async exportInvoicesCSV(filters?: Record<string, any>): Promise<Blob> {
    const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
    const query = filters ? new URLSearchParams(filters).toString() : '';
    const url = `${BASE_URL}${API_ENDPOINTS.INVOICES.EXPORT}${query ? `?${query}` : ''}`;

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Authorization': token ? `Bearer ${token}` : '',
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ error: 'Export failed' }));
      throw new Error(errorData.detail?.message || errorData.error || `HTTP ${response.status}`);
    }

    return response.blob();
  }

  // Shifts
  async getShifts(filters?: Record<string, any>): Promise<PaginatedResponse<Shift>> {
    const query = new URLSearchParams(filters).toString();
    return this.request<PaginatedResponse<Shift>>(`${API_ENDPOINTS.SHIFTS.LIST}?${query}`);
  }

  // Inbox (Moderation)
  async getPendingItems(page = 1, limit = 20, filters?: Record<string, any>): Promise<PaginatedResponse<PendingItem>> {
    const params = new URLSearchParams({ page: page.toString(), limit: limit.toString() });
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '' && value !== 'all') {
          params.append(key, value.toString());
        }
      });
    }
    return this.request<PaginatedResponse<PendingItem>>(`${API_ENDPOINTS.INBOX.LIST}?${params.toString()}`);
  }

  async approvePendingItem(id: number): Promise<void> {
    return this.request<void>(API_ENDPOINTS.INBOX.APPROVE(id), { method: 'POST' });
  }

  async rejectPendingItem(id: number): Promise<void> {
    return this.request<void>(API_ENDPOINTS.INBOX.REJECT(id), { method: 'POST' });
  }

  async bulkApprovePendingItems(ids: number[]): Promise<void> {
    return this.request<void>(API_ENDPOINTS.INBOX.BULK_APPROVE, {
      method: 'POST',
      body: JSON.stringify({ ids }),
    });
  }

  async bulkRejectPendingItems(ids: number[]): Promise<void> {
    return this.request<void>(API_ENDPOINTS.INBOX.BULK_REJECT, {
      method: 'POST',
      body: JSON.stringify({ ids }),
    });
  }

  // Dashboard
  async getDashboardKPIs(): Promise<DashboardKPIs> {
    return this.request<DashboardKPIs>(API_ENDPOINTS.DASHBOARD.KPIS);
  }

  // Bot Menu Management (Admin only)
  async getBotMenu(): Promise<BotMenuResponse> {
    return this.request<BotMenuResponse>('/api/admin/bot-menu');
  }

  async updateBotMenu(request: UpdateBotMenuRequest): Promise<BotMenuResponse> {
    return this.request<BotMenuResponse>('/api/admin/bot-menu', {
      method: 'PUT',
      body: JSON.stringify(request),
    });
  }

  async applyBotMenu(): Promise<ApplyBotMenuResponse> {
    return this.request<ApplyBotMenuResponse>('/api/admin/bot-menu/apply', {
      method: 'POST',
    });
  }

  // Dashboard (B0.3)
  async getDashboardSummary<T>(periodDays: number): Promise<T> {
    return this.request<T>(`${API_ENDPOINTS.DASHBOARD.SUMMARY}?period_days=${periodDays}`);
  }

  async getDashboardTimeseries<T>(periodDays: number, metric: string): Promise<T> {
    return this.request<T>(`${API_ENDPOINTS.DASHBOARD.TIMESERIES}?period_days=${periodDays}&metric=${metric}`);
  }

  async getDashboardRecent<T>(resource: string, limit: number): Promise<T> {
    return this.request<T>(`${API_ENDPOINTS.DASHBOARD.RECENT}?resource=${resource}&limit=${limit}`);
  }

  // Profile (F1.3)
  async getProfile(): Promise<ProfileData> {
    return this.request<ProfileData>(API_ENDPOINTS.PROFILE.GET);
  }

  async changePassword(data: PasswordChangeRequest): Promise<PasswordChangeResponse> {
    return this.request<PasswordChangeResponse>(API_ENDPOINTS.PROFILE.CHANGE_PASSWORD, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }
}

export const apiClient = new ApiClient();
