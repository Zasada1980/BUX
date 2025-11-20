import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ToastProvider } from '@/contexts/ToastContext';
import { AuthProvider } from '@/contexts/AuthContext';
import { RequireRole } from '@/components/RequireRole';
import { MainLayout } from '@/components/layout/MainLayout';
import { ROUTES } from '@/config/constants';
import ToastContainer from '@/components/ui/ToastContainer';

// Pages
import LoginPage from '@/pages/LoginPage';
import DashboardPage from '@/pages/DashboardPage';
import UsersPage from '@/pages/UsersPage';
import ClientsPage from '@/pages/ClientsPage';
import TasksPage from '@/pages/TasksPage';
import ExpensesPage from '@/pages/ExpensesPage';
import InvoicesPage from '@/pages/InvoicesPage';
import ShiftsPage from './pages/ShiftsPage';
import ShiftsCalendarPage from './pages/ShiftsCalendarPage';
import InboxPage from './pages/InboxPage';
import ChatPage from './pages/ChatPage';
import BotMenuPage from './pages/BotMenuPage';
import SettingsPage from '@/pages/SettingsPage';
import ProfilePage from '@/pages/ProfilePage';
import NotFoundPage from '@/pages/NotFoundPage';

import './App.css';

function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <Routes>
          {/* Public routes */}
          <Route path={ROUTES.LOGIN} element={<LoginPage />} />
          <Route path="/" element={<Navigate to={ROUTES.DASHBOARD} replace />} />

          {/* Protected routes */}
          <Route
            path={ROUTES.DASHBOARD}
            element={
              <RequireRole allowedRoles={['admin', 'foreman']}>
                <MainLayout>
                  <DashboardPage />
                </MainLayout>
              </RequireRole>
            }
          />

          <Route
            path={ROUTES.USERS}
            element={
              <RequireRole allowedRoles={['admin']}>
                <MainLayout>
                  <UsersPage />
                </MainLayout>
              </RequireRole>
            }
          />

          <Route
            path={ROUTES.CLIENTS}
            element={
              <RequireRole allowedRoles={['admin', 'foreman']}>
                <MainLayout>
                  <ClientsPage />
                </MainLayout>
              </RequireRole>
            }
          />

          <Route
            path={ROUTES.TASKS}
            element={
              <RequireRole allowedRoles={['admin', 'foreman']}>
                <MainLayout>
                  <TasksPage />
                </MainLayout>
              </RequireRole>
            }
          />

          <Route
            path={ROUTES.EXPENSES}
            element={
              <RequireRole allowedRoles={['admin', 'foreman']}>
                <MainLayout>
                  <ExpensesPage />
                </MainLayout>
              </RequireRole>
            }
          />

          <Route
            path={ROUTES.INVOICES}
            element={
              <RequireRole allowedRoles={['admin', 'foreman']}>
                <MainLayout>
                  <InvoicesPage />
                </MainLayout>
              </RequireRole>
            }
          />

          <Route
            path={ROUTES.SHIFTS}
            element={
              <RequireRole allowedRoles={['admin', 'foreman']}>
                <MainLayout>
                  <ShiftsPage />
                </MainLayout>
              </RequireRole>
            }
          />

          <Route
            path={ROUTES.SHIFTS_CALENDAR}
            element={
              <RequireRole allowedRoles={['admin', 'foreman']}>
                <MainLayout>
                  <ShiftsCalendarPage />
                </MainLayout>
              </RequireRole>
            }
          />

          <Route
            path={ROUTES.INBOX}
            element={
              <RequireRole allowedRoles={['admin', 'foreman']}>
                <MainLayout>
                  <InboxPage />
                </MainLayout>
              </RequireRole>
            }
          />

          <Route
            path={ROUTES.CHAT}
            element={
              <RequireRole allowedRoles={['admin', 'foreman']}>
                <MainLayout>
                  <ChatPage />
                </MainLayout>
              </RequireRole>
            }
          />

          <Route
            path={ROUTES.SETTINGS}
            element={
              <RequireRole allowedRoles={['admin']}>
                <MainLayout>
                  <SettingsPage />
                </MainLayout>
              </RequireRole>
            }
          />

          <Route
            path={ROUTES.BOT_MENU}
            element={
              <RequireRole allowedRoles={['admin']}>
                <MainLayout>
                  <BotMenuPage />
                </MainLayout>
              </RequireRole>
            }
          />

          <Route
            path={ROUTES.PROFILE}
            element={
              <RequireRole allowedRoles={['admin', 'foreman']}>
                <MainLayout>
                  <ProfilePage />
                </MainLayout>
              </RequireRole>
            }
          />

          {/* 404 */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
        <ToastContainer />
      </AuthProvider>
    </ToastProvider>
    </BrowserRouter>
  );
}

export default App;
