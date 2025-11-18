import { useState, ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { useRoleCheck } from '@/components/RequireRole';
import { ROUTES } from '@/config/constants';
import './MainLayout.css';

interface MainLayoutProps {
  children: ReactNode;
}

interface NavItem {
  path: string;
  label: string;
  icon: string;
  allowedRoles: ('admin' | 'foreman')[];
}

const NAV_ITEMS: NavItem[] = [
  { path: ROUTES.DASHBOARD, label: 'Dashboard', icon: '📊', allowedRoles: ['admin', 'foreman'] },
  { path: ROUTES.USERS, label: 'Users', icon: '👥', allowedRoles: ['admin'] },
  { path: ROUTES.CLIENTS, label: 'Clients', icon: '🏢', allowedRoles: ['admin', 'foreman'] },
  { path: ROUTES.TASKS, label: 'Tasks', icon: '📋', allowedRoles: ['admin', 'foreman'] },
  { path: ROUTES.EXPENSES, label: 'Expenses', icon: '💰', allowedRoles: ['admin', 'foreman'] },
  { path: ROUTES.INVOICES, label: 'Invoices', icon: '📄', allowedRoles: ['admin', 'foreman'] },
  { path: ROUTES.SHIFTS, label: 'Shifts', icon: '⏱️', allowedRoles: ['admin', 'foreman'] },
  { path: ROUTES.INBOX, label: 'Inbox', icon: '📮', allowedRoles: ['admin', 'foreman'] },
  { path: ROUTES.SETTINGS, label: 'Settings', icon: '⚙️', allowedRoles: ['admin'] },
  { path: ROUTES.BOT_MENU, label: 'Bot Menu', icon: '🤖', allowedRoles: ['admin'] },
];

export function MainLayout({ children }: MainLayoutProps) {
  const { user, logout } = useAuth();
  const { hasRole } = useRoleCheck();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const visibleNavItems = NAV_ITEMS.filter((item) => hasRole(item.allowedRoles));

  const getRoleBadgeClass = () => {
    if (!user) return '';
    switch (user.role) {
      case 'admin':
        return 'badge-admin';
      case 'foreman':
        return 'badge-foreman';
      case 'worker':
        return 'badge-worker';
      default:
        return '';
    }
  };

  const getRoleLabel = () => {
    if (!user) return '';
    switch (user.role) {
      case 'admin':
        return 'Admin';
      case 'foreman':
        return 'Foreman';
      case 'worker':
        return 'Worker';
      default:
        return '';
    }
  };

  return (
    <div className="main-layout">
      {/* Header */}
      <header className="header">
        <div className="header-left">
          <button
            className="hamburger-btn"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label="Toggle sidebar"
          >
            ☰
          </button>
          <h1 className="logo">TelegramOllama</h1>
        </div>

        <div className="header-right">
          <div className="user-menu">
            <button
              className="user-menu-trigger"
              onClick={() => setUserMenuOpen(!userMenuOpen)}
              aria-label="User menu"
            >
              <span className="user-name">{user?.name}</span>
              <span className={`role-badge ${getRoleBadgeClass()}`}>{getRoleLabel()}</span>
              <span className="dropdown-arrow">▼</span>
            </button>

            {userMenuOpen && (
              <div className="user-menu-dropdown">
                <Link to={ROUTES.PROFILE} onClick={() => setUserMenuOpen(false)}>
                  Profile
                </Link>
                {hasRole(['admin']) && (
                  <Link to={ROUTES.SETTINGS} onClick={() => setUserMenuOpen(false)}>
                    Settings
                  </Link>
                )}
                <button onClick={logout} className="logout-btn">
                  Logout
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : 'closed'}`}>
        <nav className="sidebar-nav">
          {visibleNavItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`nav-item ${isActive ? 'active' : ''}`}
              >
                <span className="nav-icon">{item.icon}</span>
                {sidebarOpen && <span className="nav-label">{item.label}</span>}
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Main content */}
      <main className={`main-content ${sidebarOpen ? '' : 'sidebar-closed'}`}>
        <div className="content-wrapper">{children}</div>
      </main>
    </div>
  );
}
