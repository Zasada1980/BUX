import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import type { User, UserRole } from '@/types';
import { useToast } from '@/contexts/ToastContext';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (username: string, password: string, rememberMe: boolean) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<boolean>;
  getRole: () => UserRole | null;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// F4.3.3 FIX: Synchronous auth state initialization from storage
// This prevents race conditions between page.goto() and RequireRole checks
function readAuthFromStorage(): AuthState {
  if (typeof window === 'undefined') {
    return { user: null, token: null, isAuthenticated: false, isLoading: true };
  }

  try {
    // Check both sessionStorage and localStorage for tokens
    const storages = [window.sessionStorage, window.localStorage];
    for (const storage of storages) {
      const token = storage.getItem('access_token');
      const userRaw = storage.getItem('current_user');
      if (token && userRaw) {
        const user = JSON.parse(userRaw) as User;
        return {
          user,
          token,
          isAuthenticated: true,
          isLoading: false,
        };
      }
    }
  } catch (error) {
    console.error('Failed to read auth from storage:', error);
  }

  return { user: null, token: null, isAuthenticated: false, isLoading: false };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const { showToast } = useToast();
  
  // F4.3.3 FIX: Initialize state SYNCHRONOUSLY from storage using lazy initializer
  // This ensures first render already has correct isAuthenticated/user values
  const [authState, setAuthState] = useState<AuthState>(() => readAuthFromStorage());

  // Listen for storage changes (custom event for same-window, storage event for cross-tab)
  useEffect(() => {
    const handleAuthChange = () => {
      setAuthState(readAuthFromStorage());
    };

    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'access_token' || e.key === 'current_user') {
        setAuthState(readAuthFromStorage());
      }
    };

    window.addEventListener('auth-storage-change', handleAuthChange);
    window.addEventListener('storage', handleStorageChange);
    
    return () => {
      window.removeEventListener('auth-storage-change', handleAuthChange);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);

  const clearStorage = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('current_user');
    sessionStorage.removeItem('access_token');
    sessionStorage.removeItem('refresh_token');
    sessionStorage.removeItem('current_user');
  };

  const login = async (username: string, password: string, rememberMe: boolean) => {
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        const message = errorData.detail || 'Login failed';
        showToast(message, 'error');
        throw new Error(message);
      }

      const data = await response.json();

      // Check if user is worker (not allowed in Web UI)
      if (data.role === 'worker') {
        const message = 'Access denied: Workers cannot use Web UI. Please use Telegram.';
        showToast(message, 'error');
        throw new Error(message);
      }

      const user: User = {
        id: data.user_id,
        name: data.name,
        telegram_id: data.telegram_id || '',
        role: data.role,
        status: 'active',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      // Store tokens and user
      const storage = rememberMe ? localStorage : sessionStorage;
      storage.setItem('access_token', data.access_token || data.token);
      if (data.refresh_token) {
        storage.setItem('refresh_token', data.refresh_token);
      }
      storage.setItem('current_user', JSON.stringify(user));

      // F4.3.3 FIX: Synchronously update state BEFORE dispatching event
      // This ensures any components re-rendering after event see updated state immediately
      setAuthState({
        user,
        token: data.access_token || data.token,
        isAuthenticated: true,
        isLoading: false,
      });

      // Dispatch custom event to notify other components (legacy support)
      window.dispatchEvent(new CustomEvent('auth-storage-change', { detail: { user, token: data.access_token || data.token } }));
    } catch (error) {
      throw error;
    }
  };

  const logout = () => {
    clearStorage();
    
    setAuthState({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
    });
    
    window.dispatchEvent(new Event('auth-storage-change'));
    showToast('You have been logged out.', 'info');
  };

  const refreshToken = async (): Promise<boolean> => {
    const storedRefreshToken = localStorage.getItem('refresh_token') || sessionStorage.getItem('refresh_token');

    if (!storedRefreshToken) {
      return false;
    }

    try {
      const response = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: storedRefreshToken }),
      });

      if (!response.ok) {
        logout();
        return false;
      }

      const data = await response.json();

      // Update tokens
      const storage = localStorage.getItem('access_token') ? localStorage : sessionStorage;
      storage.setItem('access_token', data.access_token);
      if (data.refresh_token) {
        storage.setItem('refresh_token', data.refresh_token);
      }

      // F4.3.3 FIX: Synchronously update token in state
      setAuthState((prev) => ({
        ...prev,
        token: data.access_token,
      }));

      // Dispatch event to notify other components
      window.dispatchEvent(new Event('auth-storage-change'));

      return true;
    } catch (error) {
      console.error('Token refresh failed:', error);
      logout();
      return false;
    }
  };

  const getRole = (): UserRole | null => {
    return authState.user?.role || null;
  };

  const value: AuthContextValue = {
    ...authState,
    login,
    logout,
    refreshToken,
    getRole,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
