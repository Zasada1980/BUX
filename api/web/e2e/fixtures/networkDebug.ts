import { Page } from '@playwright/test';

/**
 * E2E Network Debug Helper (F4.3.4 — Pre-Backend-Fix Diagnostic Layer)
 * 
 * Enables detailed logging of API requests/responses for JWT↔API mismatch diagnosis.
 * 
 * Usage:
 * ```typescript
 * import { enableNetworkDebug } from './fixtures/networkDebug';
 * 
 * test('expenses scenario', async ({ page }) => {
 *   const logs = enableNetworkDebug(page, /\/api\/(expenses|invoices|admin\/pending)/);
 *   await loginAsAdmin(page);
 *   await page.goto('/expenses');
 *   // ... test logic
 *   console.log('[NETWORK LOGS]', logs);
 * });
 * ```
 */

export interface NetworkLog {
  timestamp: string;
  type: 'request' | 'response';
  method?: string;
  url: string;
  status?: number;
  headers?: Record<string, string>;
  hasAuthHeader?: boolean;
  hasAdminSecret?: boolean;
}

export function enableNetworkDebug(page: Page, urlPattern: RegExp): NetworkLog[] {
  const logs: NetworkLog[] = [];

  page.on('request', (request) => {
    if (!urlPattern.test(request.url())) return;

    const headers = request.headers();
    const hasAuthHeader = !!headers['authorization'];
    const hasAdminSecret = !!headers['x-admin-secret'];

    const log: NetworkLog = {
      timestamp: new Date().toISOString(),
      type: 'request',
      method: request.method(),
      url: request.url(),
      headers: {
        authorization: headers['authorization'] ? `${headers['authorization'].substring(0, 30)}...` : 'MISSING',
        'x-admin-secret': headers['x-admin-secret'] ? 'PRESENT' : 'MISSING',
        'content-type': headers['content-type'] || 'N/A',
      },
      hasAuthHeader,
      hasAdminSecret,
    };

    logs.push(log);
    console.log('[E2E REQUEST]', {
      url: request.url(),
      method: request.method(),
      authHeader: hasAuthHeader ? '✅ Present' : '❌ Missing',
      adminSecret: hasAdminSecret ? '✅ Present' : '❌ Missing',
    });
  });

  page.on('response', async (response) => {
    if (!urlPattern.test(response.url())) return;

    const log: NetworkLog = {
      timestamp: new Date().toISOString(),
      type: 'response',
      url: response.url(),
      status: response.status(),
      headers: {
        'content-type': response.headers()['content-type'] || 'N/A',
      },
    };

    logs.push(log);
    console.log('[E2E RESPONSE]', {
      url: response.url(),
      status: response.status(),
      statusText: response.status() === 401 ? '❌ Unauthorized' : response.status() === 200 ? '✅ OK' : `⚠️ ${response.status()}`,
    });

    // Log response body for 401/403/5xx errors
    if (response.status() >= 400) {
      try {
        const body = await response.text();
        console.log('[E2E ERROR BODY]', {
          url: response.url(),
          status: response.status(),
          body: body.substring(0, 200), // First 200 chars
        });
      } catch (err) {
        console.log('[E2E ERROR] Failed to read response body:', err);
      }
    }
  });

  return logs;
}

/**
 * Verify auth state in browser storage (JWT token + user object)
 * 
 * Usage:
 * ```typescript
 * import { verifyAuthState } from './fixtures/networkDebug';
 * 
 * test('expenses scenario', async ({ page }) => {
 *   await loginAsAdmin(page);
 *   const authState = await verifyAuthState(page);
 *   expect(authState.hasToken).toBe(true);
 *   expect(authState.user).toBeTruthy();
 * });
 * ```
 */
export interface AuthState {
  hasToken: boolean;
  tokenPreview: string | null;
  hasUser: boolean;
  user: {
    id?: number;
    name?: string;
    role?: string;
  } | null;
  storageType: 'sessionStorage' | 'localStorage' | 'none';
}

export async function verifyAuthState(page: Page): Promise<AuthState> {
  const authState = await page.evaluate((): AuthState => {
    const sessionToken = window.sessionStorage.getItem('access_token');
    const localToken = window.localStorage.getItem('access_token');
    const token = sessionToken || localToken;

    const sessionUser = window.sessionStorage.getItem('current_user');
    const localUser = window.localStorage.getItem('current_user');
    const userStr = sessionUser || localUser;

    let user = null;
    if (userStr) {
      try {
        user = JSON.parse(userStr);
      } catch {
        user = null;
      }
    }

    return {
      hasToken: !!token,
      tokenPreview: token ? token.substring(0, 30) : null,
      hasUser: !!user,
      user: user || null,
      storageType: sessionToken ? ('sessionStorage' as const) : localToken ? ('localStorage' as const) : ('none' as const),
    };
  });

  console.log('[E2E AUTH STATE]', {
    hasToken: authState.hasToken ? '✅' : '❌',
    tokenPreview: authState.tokenPreview || 'N/A',
    hasUser: authState.hasUser ? '✅' : '❌',
    userName: authState.user?.name || 'N/A',
    userRole: authState.user?.role || 'N/A',
    storageType: authState.storageType,
  });

  return authState;
}
