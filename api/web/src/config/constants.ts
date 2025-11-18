// Route constants
export const ROUTES = {
  LOGIN: '/login',
  DASHBOARD: '/dashboard',
  USERS: '/users',
  CLIENTS: '/clients',
  TASKS: '/tasks',
  EXPENSES: '/expenses',
  INVOICES: '/invoices',
  SHIFTS: '/shifts',
  SHIFTS_CALENDAR: '/shifts/calendar',
  INBOX: '/inbox',
  SETTINGS: '/settings',
  BOT_MENU: '/bot-menu',
  PROFILE: '/profile',
  NOT_FOUND: '/404',
} as const;

// RBAC role constants
export const ROLES = {
  ADMIN: 'admin',
  FOREMAN: 'foreman',
  WORKER: 'worker',
} as const;

// Role access matrix
export const ROLE_ACCESS = {
  [ROUTES.DASHBOARD]: ['admin', 'foreman'],
  [ROUTES.USERS]: ['admin'],
  [ROUTES.CLIENTS]: ['admin', 'foreman'],
  [ROUTES.TASKS]: ['admin', 'foreman'],
  [ROUTES.EXPENSES]: ['admin', 'foreman'],
  [ROUTES.INVOICES]: ['admin', 'foreman'],
  [ROUTES.SHIFTS]: ['admin', 'foreman'],
  [ROUTES.SHIFTS_CALENDAR]: ['admin', 'foreman'],
  [ROUTES.INBOX]: ['admin', 'foreman'],
  [ROUTES.SETTINGS]: ['admin'],
  [ROUTES.BOT_MENU]: ['admin'],
  [ROUTES.PROFILE]: ['admin', 'foreman', 'worker'],
} as const;

// Status badge colors
export const STATUS_COLORS = {
  pending: 'yellow',
  approved: 'green',
  archived: 'gray',
  draft: 'blue',
  issued: 'green',
  paid: 'cyan',
  cancelled: 'red',
  active: 'green',
  inactive: 'gray',
} as const;

// Role badge colors
export const ROLE_COLORS = {
  admin: 'red',
  foreman: 'orange',
  worker: 'blue',
} as const;

// OCR status colors
export const OCR_STATUS_COLORS = {
  required: 'red',
  ok: 'green',
  abstain: 'gray',
} as const;

// Pagination defaults
export const PAGINATION = {
  DEFAULT_PAGE: 1,
  DEFAULT_LIMIT: 20,
  LIMIT_OPTIONS: [10, 20, 50, 100],
} as const;

// API endpoints
export const API_ENDPOINTS = {
  AUTH: {
    LOGIN: '/api/auth/login',
    LOGOUT: '/api/auth/logout',
    REFRESH: '/api/auth/refresh',
  },
  USERS: {
    LIST: '/api/users/',
    GET: (id: number) => `/api/users/${id}`,
    CREATE: '/api/users/',
    UPDATE: (id: number) => `/api/users/${id}`,
    DELETE: (id: number) => `/api/users/${id}`,
  },
  CLIENTS: {
    LIST: '/api/clients',
    GET: (id: number) => `/api/clients/${id}`,
    CREATE: '/api/clients',
    UPDATE: (id: number) => `/api/clients/${id}`,
  },
  TASKS: {
    LIST: '/api/tasks',
    GET: (id: number) => `/api/tasks/${id}`,
    EXPORT: '/api/tasks/export',
  },
  EXPENSES: {
    LIST: '/api/expenses',
    GET: (id: number) => `/api/expenses/${id}`,
    EXPORT: '/api/expenses/export',
  },
  INVOICES: {
    LIST: '/api/invoices',
    GET: (id: number) => `/api/invoices/${id}`,
    CREATE: '/api/invoices',
    PREVIEW: (id: number) => `/api/invoice/preview/${id}`,
    ISSUE: (id: number) => `/api/invoice/preview/${id}/issue`,
    EXPORT: '/api/invoices/export',
  },
  SHIFTS: {
    LIST: '/api/shifts',
    CALENDAR: '/api/shifts/calendar',
  },
  INBOX: {
    LIST: '/api/admin/pending',
    APPROVE: (id: number) => `/api/admin/pending/${id}/approve`,
    REJECT: (id: number) => `/api/admin/pending/${id}/reject`,
    BULK_APPROVE: '/api/admin/pending/bulk.approve',
    BULK_REJECT: '/api/admin/pending/bulk.reject',
  },
  DASHBOARD: {
    SUMMARY: '/api/dashboard/summary',
    TIMESERIES: '/api/dashboard/timeseries',
    RECENT: '/api/dashboard/recent',
  },
  SETTINGS: {
    GET: '/api/settings',
    UPDATE: '/api/settings',
  },
  PROFILE: {
    GET: '/api/profile',
    CHANGE_PASSWORD: '/api/profile/password',
  },
} as const;
