// Core domain types for TelegramOllama Work Ledger

export type UserRole = 'admin' | 'foreman' | 'worker';
export type UserStatus = 'active' | 'inactive';

export interface User {
  id: number;
  name: string;
  telegram_id: string;
  role: UserRole;
  status: UserStatus;
  created_at: string;
  updated_at: string;
}

export interface Client {
  id: number;
  name: string;
  contact?: string;
  default_pricing_rule?: string;
  status: 'active' | 'archived';
  total_invoiced: number;
  created_at: string;
  updated_at: string;
}

export type TaskStatus = 'pending' | 'approved' | 'archived';

export interface Task {
  id: number;
  worker_id: number;
  worker_name: string;
  client_id: number;
  client_name: string;
  description: string;
  pricing_rule: string;
  quantity: number;
  amount: number;
  date: string;
  status: TaskStatus;
  created_at: string;
  updated_at: string;
}

export type ExpenseCategory = 'materials' | 'transport' | 'tools' | 'other';
export type OCRStatus = 'required' | 'ok' | 'abstain';

export interface Expense {
  id: number;
  worker_id: number;
  worker_name: string;
  category: ExpenseCategory;
  amount: number;
  description?: string;
  photo_ref?: string;
  date: string;
  ocr_metadata?: {
    enabled: boolean;
    status: OCRStatus;
    confidence?: number;
    detected_amount?: number;
  };
  status: 'pending' | 'approved';
  created_at: string;
  updated_at: string;
}

export type InvoiceStatus = 'draft' | 'issued' | 'paid' | 'cancelled';

export interface Invoice {
  id: number;
  client_id: number;
  client_name: string;
  date_from: string;
  date_to: string;
  total_amount: number;
  status: InvoiceStatus;
  items_count: number;
  issued_at?: string;
  created_at: string;
  updated_at: string;
}

export interface InvoiceItem {
  id: number;
  invoice_id: number;
  type: 'task' | 'expense';
  description: string;
  quantity: number;
  unit_price: number;
  amount: number;
}

export interface Shift {
  id: number;
  worker_id: number;
  worker_name: string;
  start_time: string;
  end_time?: string;
  duration_hours?: number;
  date: string;
  created_at: string;
  updated_at: string;
}

export type PendingItemType = 'task' | 'expense';

export interface PendingItem {
  id: number;
  type: PendingItemType;
  worker_id: number;
  worker_name: string;
  amount: number;
  description: string;
  date: string;
  metadata: Record<string, any>;
  created_at: string;
}

// Dashboard KPIs
export interface DashboardKPIs {
  total_hours: number;
  total_costs: number;
  costs_trend: number; // ±% vs previous period
  pending_items_count: number;
  invoices_issued_count: number;
  invoices_issued_total: number;
}

// Settings
export interface PricingRule {
  id: number;
  name: string;
  type: 'hourly' | 'fixed' | 'per_unit';
  rate: number;
  unit?: string;
  description?: string;
}

export interface SystemSettings {
  ocr_enabled: boolean;
  ocr_threshold: number;
  backup_schedule: string;
  version: string;
}

// Bot Menu Management Types
export interface BotCommandConfig {
  id: number;
  role: UserRole;
  command_key: string;
  telegram_command: string;
  label: string;
  description?: string;
  enabled: boolean;
  is_core: boolean;
  position: number;
  command_type: 'slash' | 'menu';
}

export interface BotMenuResponse {
  version: number;
  last_updated_at: string;
  last_updated_by?: string;
  last_applied_at?: string;
  last_applied_by?: string;
  roles: {
    admin: BotCommandConfig[];
    foreman: BotCommandConfig[];
    worker: BotCommandConfig[];
  };
}

export interface UpdateBotCommandPayload {
  id: number;
  label: string;
  enabled: boolean;
  position: number;
}

export interface UpdateBotMenuRequest {
  version: number;
  roles: {
    [key: string]: UpdateBotCommandPayload[];
  };
}

export interface ApplyBotMenuResponse {
  success: boolean;
  applied_at?: string;
  details?: string;
}

// Profile Types (F1.3)
export interface ProfileData {
  id: number;
  name: string;
  email: string | null;
  role: string;
  created_at: string;
  last_login: string | null;
}

export interface PasswordChangeRequest {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

export interface PasswordChangeResponse {
  message: string;
  changed_at: string;
}

// API Responses
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface ApiError {
  error: string;
  detail?: string;
  status_code: number;
}
