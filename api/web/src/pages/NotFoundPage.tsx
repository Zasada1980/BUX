import { Link } from 'react-router-dom';
import { ROUTES } from '@/config/constants';

export default function NotFoundPage() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '50vh', textAlign: 'center' }}>
      <h1 style={{ fontSize: '4rem', marginBottom: '1rem' }}>404</h1>
      <p style={{ fontSize: '1.25rem', color: '#6b7280', marginBottom: '2rem' }}>Page not found</p>
      <Link to={ROUTES.DASHBOARD} style={{ padding: '0.75rem 1.5rem', background: '#3b82f6', color: 'white', textDecoration: 'none', borderRadius: '0.375rem' }}>
        Go to Dashboard
      </Link>
    </div>
  );
}
