import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { ROUTES } from '@/config/constants';
import './LoginPage.css';

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();

  const [formData, setFormData] = useState({
    username: '',
    password: '',
    rememberMe: false,
  });
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const from = (location.state as any)?.from?.pathname || ROUTES.DASHBOARD;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login(formData.username, formData.password, formData.rememberMe);
      // Toast will be shown by AuthContext on errors
      navigate(from, { replace: true });
    } catch (err: any) {
      // Error already shown by AuthContext toast, keep inline error for redundancy
      setError(err.message || 'Login failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-container">
        <div className="login-header">
          <h1>TelegramOllama Work Ledger</h1>
          <p>Web Management Interface</p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          {error && <div className="error-message">❌ {error}</div>}

          <div className="form-group">
            <label htmlFor="username">Username or Telegram ID</label>
            <input
              id="username"
              name="username"
              type="text"
              value={formData.username}
              onChange={(e) => setFormData({ ...formData, username: e.target.value })}
              required
              minLength={3}
              autoComplete="username"
              autoFocus
              disabled={isLoading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              name="password"
              type="password"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              required
              minLength={6}
              autoComplete="current-password"
              disabled={isLoading}
            />
          </div>

          <div className="form-group-checkbox">
            <input
              id="rememberMe"
              type="checkbox"
              checked={formData.rememberMe}
              onChange={(e) => setFormData({ ...formData, rememberMe: e.target.checked })}
              disabled={isLoading}
            />
            <label htmlFor="rememberMe">Remember me (7 days)</label>
          </div>

          <button type="submit" className="login-btn" disabled={isLoading}>
            {isLoading ? 'Logging in...' : 'Login'}
          </button>

          <p className="help-text">Forgot password? Contact admin</p>
        </form>

        <footer className="login-footer">
          <p>Powered by FastAPI + React</p>
        </footer>
      </div>
    </div>
  );
}
