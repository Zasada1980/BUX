import { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import Spinner from '@/components/ui/Spinner';
import { useToast } from '@/contexts/ToastContext';
import { apiClient } from '@/lib/apiClient';
import type { ProfileData, PasswordChangeRequest } from '@/types';

/**
 * ProfilePage — Full Profile Management (F7 Restoration)
 * 
 * Features:
 * - Profile view: ✅ Display user info (name, email, role, created_at, last_login)
 * - Password change: ✅ Full form with validation (current, new, confirm passwords)
 * - Error handling: ✅ Loading/error states, toast notifications
 * 
 * See UX_PLAYBOOK v2.0 (Scenario 9: Fully Supported)
 */
export default function ProfilePage() {
  const { showToast } = useToast();
  
  // Profile state
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Password change state
  const [passwordForm, setPasswordForm] = useState<PasswordChangeRequest>({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });
  const [submitting, setSubmitting] = useState(false);

  // Load profile on mount
  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.getProfile();
      setProfile(data);
    } catch (err: any) {
      const errorMsg = err?.message || 'Failed to load profile';
      setError(errorMsg);
      showToast(errorMsg, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();

    // Client-side validation
    if (!passwordForm.current_password || !passwordForm.new_password || !passwordForm.confirm_password) {
      showToast('All password fields are required', 'error');
      return;
    }

    if (passwordForm.new_password.length < 6) {
      showToast('New password must be at least 6 characters', 'error');
      return;
    }

    if (passwordForm.new_password !== passwordForm.confirm_password) {
      showToast('New password and confirmation do not match', 'error');
      return;
    }

    setSubmitting(true);
    try {
      await apiClient.changePassword(passwordForm);
      showToast('Password changed successfully', 'success');
      
      // Clear form
      setPasswordForm({
        current_password: '',
        new_password: '',
        confirm_password: '',
      });
    } catch (err: any) {
      const errorMsg = err?.message || 'Failed to change password';
      showToast(errorMsg, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading && !profile) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
        <Spinner size="large" text="Loading profile..." />
      </div>
    );
  }

  if (error && !profile) {
    return (
      <div style={{ padding: '3rem', textAlign: 'center' }}>
        <div
          style={{
            background: '#fef2f2',
            border: '1px solid #fecaca',
            padding: '1.5rem',
            borderRadius: '0.5rem',
            maxWidth: '600px',
            margin: '0 auto',
          }}
        >
          <div style={{ fontSize: '1.125rem', fontWeight: '600', color: '#991b1b', marginBottom: '0.5rem' }}>
            Failed to load profile
          </div>
          <div style={{ color: '#dc2626', marginBottom: '1rem' }}>{error}</div>
          <button
            onClick={loadProfile}
            style={{
              padding: '0.5rem 1rem',
              background: '#dc2626',
              color: 'white',
              border: 'none',
              borderRadius: '0.375rem',
              cursor: 'pointer',
              fontWeight: '500',
            }}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '800px', margin: '2rem auto', padding: '0 1rem' }}>
      <h1 style={{ fontSize: '1.875rem', fontWeight: '600', marginBottom: '1.5rem' }}>Profile</h1>

      {/* Profile Info Card */}
      <Card style={{ marginBottom: '1.5rem' }}>
        <CardHeader>
          <CardTitle>User Information</CardTitle>
        </CardHeader>
        <CardContent>
          {profile && (
            <div style={{ display: 'grid', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#6b7280', marginBottom: '0.25rem' }}>
                  Name
                </label>
                <div style={{ fontSize: '1rem', color: '#1f2937' }}>{profile.name || '—'}</div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#6b7280', marginBottom: '0.25rem' }}>
                  Email
                </label>
                <div style={{ fontSize: '1rem', color: '#1f2937' }}>{profile.email || '—'}</div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#6b7280', marginBottom: '0.25rem' }}>
                  Role
                </label>
                <div style={{ fontSize: '1rem', color: '#1f2937', textTransform: 'capitalize' }}>{profile.role || '—'}</div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#6b7280', marginBottom: '0.25rem' }}>
                  User ID
                </label>
                <div style={{ fontSize: '1rem', color: '#1f2937' }}>{profile.id}</div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#6b7280', marginBottom: '0.25rem' }}>
                  Created At
                </label>
                <div style={{ fontSize: '1rem', color: '#1f2937' }}>
                  {profile.created_at ? new Date(profile.created_at).toLocaleString() : '—'}
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#6b7280', marginBottom: '0.25rem' }}>
                  Last Login
                </label>
                <div style={{ fontSize: '1rem', color: '#1f2937' }}>
                  {profile.last_login ? new Date(profile.last_login).toLocaleString() : 'Never'}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Password Change Card */}
      <Card>
        <CardHeader>
          <CardTitle>Change Password</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handlePasswordChange} style={{ display: 'grid', gap: '1rem' }}>
            <div>
              <label htmlFor="current_password" style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>
                Current Password <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <Input
                id="current_password"
                type="password"
                value={passwordForm.current_password}
                onChange={(e) => setPasswordForm({ ...passwordForm, current_password: e.target.value })}
                placeholder="Enter current password"
                disabled={submitting}
                required
              />
            </div>

            <div>
              <label htmlFor="new_password" style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>
                New Password <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <Input
                id="new_password"
                type="password"
                value={passwordForm.new_password}
                onChange={(e) => setPasswordForm({ ...passwordForm, new_password: e.target.value })}
                placeholder="Enter new password (min 6 characters)"
                disabled={submitting}
                required
                minLength={6}
              />
            </div>

            <div>
              <label htmlFor="confirm_password" style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>
                Confirm New Password <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <Input
                id="confirm_password"
                type="password"
                value={passwordForm.confirm_password}
                onChange={(e) => setPasswordForm({ ...passwordForm, confirm_password: e.target.value })}
                placeholder="Confirm new password"
                disabled={submitting}
                required
                minLength={6}
              />
            </div>

            <div style={{ marginTop: '0.5rem' }}>
              <Button
                type="submit"
                disabled={submitting}
                style={{
                  backgroundColor: submitting ? '#9ca3af' : '#3b82f6',
                  cursor: submitting ? 'not-allowed' : 'pointer',
                }}
              >
                {submitting ? 'Changing Password...' : 'Change Password'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
