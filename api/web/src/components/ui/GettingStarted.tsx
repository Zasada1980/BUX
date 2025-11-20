/**
 * GettingStarted — Onboarding guide for first-run Dashboard (UX-V2-C1)
 * 
 * Shows when:
 * - No users (workers) created yet
 * - No shifts recorded
 * - No expenses submitted
 * 
 * Purpose: Guide admin through initial setup steps
 */

import { Link } from 'react-router-dom';

interface GettingStartedProps {
  hasUsers: boolean;
  hasShifts: boolean;
  hasExpenses: boolean;
}

export function GettingStarted({ hasUsers, hasShifts, hasExpenses }: GettingStartedProps) {
  const allComplete = hasUsers && hasShifts && hasExpenses;

  // Don't show if all steps complete
  if (allComplete) {
    return null;
  }

  return (
    <div
      style={{
        background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
        color: 'white',
        padding: '2rem',
        borderRadius: '0.75rem',
        marginBottom: '2rem',
        boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div style={{ fontSize: '2rem', marginRight: '1rem' }}>🚀</div>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.5rem', fontWeight: '600' }}>
            Getting Started with TelegramOllama
          </h2>
          <p style={{ margin: '0.25rem 0 0', opacity: 0.9, fontSize: '0.875rem' }}>
            Follow these steps to set up your work ledger system
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gap: '1rem' }}>
        {/* Step 1: Add Users */}
        <StepCard
          number={1}
          title="Add your first worker"
          description="Create user accounts for your team members"
          completed={hasUsers}
          linkTo="/users"
          linkLabel="Go to Users"
        />

        {/* Step 2: Connect Bot */}
        <StepCard
          number={2}
          title="Connect the Telegram bot"
          description="Configure bot token and webhook for mobile access"
          completed={false} // Always show (bot config is optional)
          linkTo="/settings"
          linkLabel="Go to Settings"
        />

        {/* Step 3: Record Activity */}
        <StepCard
          number={3}
          title="Record your first shift or expense"
          description="Start tracking work hours and expenses via Telegram or web"
          completed={hasShifts && hasExpenses}
          linkTo="/shifts"
          linkLabel={hasShifts ? 'Go to Expenses' : 'Go to Shifts'}
        />
      </div>

      {!allComplete && (
        <div
          style={{
            marginTop: '1.5rem',
            padding: '1rem',
            background: 'rgba(255, 255, 255, 0.1)',
            borderRadius: '0.5rem',
            fontSize: '0.875rem',
          }}
        >
          <strong>💡 Tip:</strong> You can also invite workers via Telegram bot for easy mobile access.
          See <Link to="/bot-menu" style={{ color: 'white', textDecoration: 'underline' }}>Bot Menu</Link> for commands.
        </div>
      )}
    </div>
  );
}

interface StepCardProps {
  number: number;
  title: string;
  description: string;
  completed: boolean;
  linkTo: string;
  linkLabel: string;
}

function StepCard({ number, title, description, completed, linkTo, linkLabel }: StepCardProps) {
  return (
    <div
      style={{
        background: 'rgba(255, 255, 255, 0.1)',
        borderRadius: '0.5rem',
        padding: '1rem',
        display: 'flex',
        alignItems: 'center',
        gap: '1rem',
        border: completed ? '2px solid rgba(34, 197, 94, 0.5)' : '2px solid transparent',
      }}
    >
      <div
        style={{
          width: '2.5rem',
          height: '2.5rem',
          borderRadius: '50%',
          background: completed ? '#22c55e' : 'rgba(255, 255, 255, 0.2)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '1.25rem',
          fontWeight: '600',
          flexShrink: 0,
        }}
      >
        {completed ? '✓' : number}
      </div>

      <div style={{ flex: 1 }}>
        <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: '600' }}>
          {title}
        </h3>
        <p style={{ margin: '0.25rem 0 0', fontSize: '0.875rem', opacity: 0.9 }}>
          {description}
        </p>
      </div>

      {!completed && (
        <Link
          to={linkTo}
          style={{
            padding: '0.5rem 1rem',
            background: 'white',
            color: '#3b82f6',
            borderRadius: '0.375rem',
            textDecoration: 'none',
            fontSize: '0.875rem',
            fontWeight: '500',
            whiteSpace: 'nowrap',
            transition: 'background 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = '#f0f9ff';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'white';
          }}
        >
          {linkLabel}
        </Link>
      )}
    </div>
  );
}
