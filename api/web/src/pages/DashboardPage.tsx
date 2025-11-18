import { useEffect, useState } from 'react';
import { apiClient } from '@/lib/apiClient';
import Spinner from '@/components/ui/Spinner';
import { useAuth } from '@/contexts/AuthContext';

interface DashboardSummary {
  period_days: number;
  cutoff_date: string;
  active_shifts: number;
  total_expenses: number;
  total_invoices_paid: number;
  pending_items: number;
  generated_at: string;
}

interface TimeseriesPoint {
  date: string;
  value: number;
}

interface RecentItem {
  id: number;
  type: 'expense' | 'invoice' | 'task';
  summary: string;
  amount: number;
  date: string;
  created_at: string;
}

export default function DashboardPage() {
  // B0.4 FIX: Block render until AuthContext loads from storage
  // Without this, RequireRole shows "Access denied" before user state is ready
  const { isLoading: authLoading } = useAuth();
  
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [timeseries, setTimeseries] = useState<TimeseriesPoint[]>([]);
  const [recentItems, setRecentItems] = useState<RecentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Period selector state
  const [selectedPeriod, setSelectedPeriod] = useState<7 | 30 | 90>(7);
  
  useEffect(() => {
    // Don't load data if auth context still loading
    if (!authLoading) {
      loadDashboard();
    }
  }, [selectedPeriod, authLoading]);
  
  const loadDashboard = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Load all dashboard data in parallel
      const [summaryData, expensesData, recentData] = await Promise.all([
        apiClient.get<DashboardSummary>(`/api/dashboard/summary?period_days=${selectedPeriod}`),
        apiClient.get<TimeseriesPoint[]>(`/api/dashboard/timeseries?period_days=${selectedPeriod}&metric=expenses`),
        apiClient.get<RecentItem[]>('/api/dashboard/recent?resource=expenses&limit=5')
      ]);
      
      setSummary(summaryData);
      setTimeseries(expensesData);
      setRecentItems(recentData);
    } catch (err) {
      console.error('Dashboard load error:', err);
      setError('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };
  
  const formatCurrency = (amount: number) => {
    return `₪${amount.toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };
  
  // B0.4 FIX: Show loading spinner while AuthContext initializes from storage
  // This prevents RequireRole from rendering before user state is loaded
  if (authLoading) {
    return (
      <div style={{ padding: '2rem' }}>
        <h1 style={{ marginBottom: '1.5rem' }}>Dashboard</h1>
        <Spinner size="large" text="Authenticating..." />
      </div>
    );
  }
  
  if (loading) {
    return (
      <div style={{ padding: '2rem' }}>
        <h1 style={{ marginBottom: '1.5rem' }}>Dashboard</h1>
        <Spinner size="large" text="Loading dashboard..." />
      </div>
    );
  }
  
  if (error) {
    return (
      <div style={{ padding: '2rem' }}>
        <h1 style={{ marginBottom: '1.5rem' }}>Dashboard</h1>
        <div style={{ padding: '1rem', background: '#fee', borderRadius: '0.5rem', color: '#c00' }}>
          {error}
        </div>
      </div>
    );
  }
  
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h1>Dashboard</h1>
        
        {/* Period selector */}
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {[7, 30, 90].map((days) => (
            <button
              key={days}
              onClick={() => setSelectedPeriod(days as 7 | 30 | 90)}
              style={{
                padding: '0.5rem 1rem',
                border: '1px solid #d1d5db',
                borderRadius: '0.375rem',
                background: selectedPeriod === days ? '#3b82f6' : 'white',
                color: selectedPeriod === days ? 'white' : '#374151',
                cursor: 'pointer',
                fontWeight: selectedPeriod === days ? '600' : '400',
                transition: 'all 0.2s'
              }}
            >
              {days} days
            </button>
          ))}
        </div>
      </div>
      
      {/* KPI Cards */}
      <div 
        data-testid="dashboard-kpi-grid"
        style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', 
          gap: '1.5rem', 
          marginBottom: '2rem' 
        }}
      >
        <div 
          data-testid="kpi-card-shifts"
          style={{ 
            padding: '1.5rem', 
            background: 'white', 
            borderRadius: '0.5rem', 
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
            border: '1px solid #e5e7eb'
          }}
        >
          <h3 style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.5rem', textTransform: 'uppercase', fontWeight: '600' }}>
            Active Shifts
          </h3>
          <p style={{ fontSize: '2rem', fontWeight: '600', color: '#059669' }}>
            {summary?.active_shifts || 0}
          </p>
          <p style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>
            Currently open
          </p>
        </div>
        
        <div 
          data-testid="kpi-card-expenses"
          style={{ 
            padding: '1.5rem', 
            background: 'white', 
            borderRadius: '0.5rem', 
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
            border: '1px solid #e5e7eb'
          }}
        >
          <h3 style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.5rem', textTransform: 'uppercase', fontWeight: '600' }}>
            Total Expenses
          </h3>
          <p style={{ fontSize: '2rem', fontWeight: '600', color: '#dc2626' }}>
            {formatCurrency(summary?.total_expenses || 0)}
          </p>
          <p style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>
            Last {selectedPeriod} days
          </p>
        </div>
        
        <div 
          data-testid="kpi-card-invoices"
          style={{ 
            padding: '1.5rem', 
            background: 'white', 
            borderRadius: '0.5rem', 
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
            border: '1px solid #e5e7eb'
          }}
        >
          <h3 style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.5rem', textTransform: 'uppercase', fontWeight: '600' }}>
            Invoices Paid
          </h3>
          <p style={{ fontSize: '2rem', fontWeight: '600', color: '#0891b2' }}>
            {formatCurrency(summary?.total_invoices_paid || 0)}
          </p>
          <p style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>
            Last {selectedPeriod} days
          </p>
        </div>
        
        <div 
          data-testid="kpi-card-pending"
          style={{ 
            padding: '1.5rem', 
            background: 'white', 
            borderRadius: '0.5rem', 
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
            border: '1px solid #e5e7eb'
          }}
        >
          <h3 style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.5rem', textTransform: 'uppercase', fontWeight: '600' }}>
            Pending Items
          </h3>
          <p style={{ fontSize: '2rem', fontWeight: '600', color: '#f59e0b' }}>
            {summary?.pending_items || 0}
          </p>
          <p style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.25rem' }}>
            Awaiting moderation
          </p>
        </div>
      </div>
      
      {/* Simple Expenses Chart (text-based for MVP) */}
      <div 
        data-testid="expenses-chart"
        style={{ 
          padding: '1.5rem', 
          background: 'white', 
          borderRadius: '0.5rem', 
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
          border: '1px solid #e5e7eb',
          marginBottom: '2rem' 
        }}
      >
        <h2 style={{ marginBottom: '1rem', fontSize: '1.125rem', fontWeight: '600' }}>
          Expenses Over Time
        </h2>
        
        {timeseries.length === 0 ? (
          <p style={{ color: '#6b7280', fontStyle: 'italic' }}>No expenses data for selected period</p>
        ) : (
          <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
            <table data-testid="timeseries-table" style={{ width: '100%', fontSize: '0.875rem' }}>
              <thead style={{ position: 'sticky', top: 0, background: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
                <tr>
                  <th style={{ padding: '0.5rem', textAlign: 'left', fontWeight: '600', color: '#374151' }}>Date</th>
                  <th style={{ padding: '0.5rem', textAlign: 'right', fontWeight: '600', color: '#374151' }}>Amount</th>
                  <th style={{ padding: '0.5rem', textAlign: 'left' }}>Visual</th>
                </tr>
              </thead>
              <tbody>
                {timeseries.map((point, idx) => {
                  const maxValue = Math.max(...timeseries.map(p => p.value), 1);
                  const barWidth = (point.value / maxValue) * 100;
                  
                  return (
                    <tr key={idx} style={{ borderBottom: '1px solid #f3f4f6' }}>
                      <td style={{ padding: '0.5rem', color: '#6b7280' }}>{point.date}</td>
                      <td style={{ padding: '0.5rem', textAlign: 'right', fontWeight: '500', color: '#374151' }}>
                        {formatCurrency(point.value)}
                      </td>
                      <td style={{ padding: '0.5rem' }}>
                        <div style={{ 
                          width: `${barWidth}%`, 
                          minWidth: '2px',
                          height: '8px', 
                          background: '#3b82f6', 
                          borderRadius: '2px' 
                        }} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
      
      {/* Recent Activity */}
      <div 
        data-testid="recent-activity"
        style={{ 
          padding: '1.5rem', 
          background: 'white', 
          borderRadius: '0.5rem', 
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
          border: '1px solid #e5e7eb'
        }}
      >
        <h2 style={{ marginBottom: '1rem', fontSize: '1.125rem', fontWeight: '600' }}>Recent Expenses</h2>
        
        {recentItems.length === 0 ? (
          <p style={{ color: '#6b7280', fontStyle: 'italic' }}>No recent expenses</p>
        ) : (
          <ul data-testid="recent-expenses-list" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {recentItems.map((item) => (
              <li 
                key={item.id} 
                style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  padding: '0.75rem',
                  border: '1px solid #e5e7eb',
                  borderRadius: '0.375rem',
                  transition: 'background 0.2s'
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#f9fafb'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
              >
                <div>
                  <p style={{ fontWeight: '500', color: '#374151', marginBottom: '0.25rem' }}>
                    {item.summary}
                  </p>
                  <p style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                    {item.date}
                  </p>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <p style={{ fontWeight: '600', color: '#dc2626' }}>
                    {formatCurrency(item.amount)}
                  </p>
                  <p style={{ fontSize: '0.75rem', color: '#9ca3af' }}>
                    #{item.id}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
