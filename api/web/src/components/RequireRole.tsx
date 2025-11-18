import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { ROUTES } from '@/config/constants';
import type { UserRole } from '@/types';

interface RequireRoleProps {
  allowedRoles: UserRole[];
  children: React.ReactElement;
}

export function RequireRole({ allowedRoles, children }: RequireRoleProps) {
  const { isAuthenticated, user } = useAuth();
  const location = useLocation();

  // F4.5 FIX: Remove isLoading null render - causes blank pages in E2E tests
  // AuthContext initializes synchronously (readAuthFromStorage), so isLoading=false immediately
  // If isLoading is true, proceed with auth check anyway (fail-fast instead of blank page)

  if (!isAuthenticated || !user) {
    return <Navigate to={ROUTES.LOGIN} state={{ from: location }} replace />;
  }

  if (!allowedRoles.includes(user.role)) {
    return <Navigate to={ROUTES.DASHBOARD} replace />;
  }

  return children;
}

export function useRoleCheck() {
  const { user } = useAuth();

  const hasRole = (allowedRoles: UserRole[]): boolean => {
    if (!user) return false;
    return allowedRoles.includes(user.role);
  };

  const isAdmin = (): boolean => {
    return user?.role === 'admin';
  };

  const isForeman = (): boolean => {
    return user?.role === 'foreman';
  };

  const isWorker = (): boolean => {
    return user?.role === 'worker';
  };

  return {
    hasRole,
    isAdmin,
    isForeman,
    isWorker,
  };
}
