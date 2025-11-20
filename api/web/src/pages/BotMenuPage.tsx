import { useEffect, useState } from 'react';
import { useApi } from '../hooks/useApi';
import { apiClient } from '../lib/apiClient';
import type { BotMenuResponse, BotCommandConfig, UpdateBotMenuRequest } from '../types';

export default function BotMenuPage() {
  const [menu, setMenu] = useState<BotMenuResponse | null>(null);
  const [editedCommands, setEditedCommands] = useState<Map<number, { label: string; enabled: boolean; position: number }>>(new Map());
  const [hasChanges, setHasChanges] = useState(false);
  const [activeRole, setActiveRole] = useState<'admin' | 'foreman' | 'worker'>('worker');

  const { loading, error, execute: fetchMenu } = useApi(async () => {
    const data = await apiClient.getBotMenu();
    setMenu(data);
    // Initialize editedCommands map
    const edited = new Map<number, { label: string; enabled: boolean; position: number }>();
    Object.values(data.roles).flat().forEach((cmd: BotCommandConfig) => {
      edited.set(cmd.id, { label: cmd.label, enabled: cmd.enabled, position: cmd.position });
    });
    setEditedCommands(edited);
  });

  const { loading: saving, execute: saveMenu } = useApi(async () => {
    if (!menu) return;

    // Build update request
    const roles: { [key: string]: Array<{ id: number; label: string; enabled: boolean; position: number }> } = {
      admin: [],
      foreman: [],
      worker: [],
    };

    Object.entries(menu.roles).forEach(([role, commands]) => {
      commands.forEach((cmd: BotCommandConfig) => {
        const edited = editedCommands.get(cmd.id);
        if (edited) {
          roles[role].push({
            id: cmd.id,
            label: edited.label,
            enabled: edited.enabled,
            position: edited.position,
          });
        }
      });
    });

    const request: UpdateBotMenuRequest = {
      version: menu.version,
      roles,
    };

    const updated = await apiClient.updateBotMenu(request);
    setMenu(updated);
    setHasChanges(false);
    alert('✅ Bot menu saved successfully!');
  });

  // F5.3 FIX: Remove fetchMenu from deps to prevent infinite loop
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    fetchMenu();
  }, []);

  const toggleEnabled = (id: number, isCore: boolean) => {
    const current = editedCommands.get(id);
    if (!current) return;

    const currentEnabled = current.enabled;

    if (isCore && currentEnabled) {
      alert('⚠️ Core commands cannot be disabled');
      return;
    }

    const updated = new Map(editedCommands);
    updated.set(id, { ...current, enabled: !currentEnabled });
    setEditedCommands(updated);
    setHasChanges(true);
  };

  const handleSave = async () => {
    if (!hasChanges) {
      alert('ℹ️ No changes to save');
      return;
    }

    await saveMenu();
  };

  if (loading && !menu) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading bot menu...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded">
        <p className="text-red-800">Error loading bot menu: {error}</p>
        <button
          onClick={fetchMenu}
          className="mt-3 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!menu) return null;

  const commands = menu.roles[activeRole] || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Bot Menu Configuration</h1>
          <p className="text-sm text-gray-500 mt-1">
            Configure Telegram bot commands for different user roles
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={!hasChanges || saving}
          className={`px-4 py-2 rounded font-medium ${
            hasChanges && !saving
              ? 'bg-blue-600 text-white hover:bg-blue-700'
              : 'bg-gray-300 text-gray-500 cursor-not-allowed'
          }`}
        >
          {saving ? '💾 Saving...' : '💾 Save Changes'}
        </button>
      </div>

      {/* Metadata */}
      <div className="bg-gray-50 border border-gray-200 rounded p-4 text-sm">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <span className="font-medium">Version:</span> {menu.version}
          </div>
          <div>
            <span className="font-medium">Last Updated:</span>{' '}
            {menu.last_updated_by || 'Never'} at {new Date(menu.last_updated_at).toLocaleString()}
          </div>
        </div>
        {hasChanges && (
          <div className="mt-2 text-orange-600">
            ⚠️ You have unsaved changes
          </div>
        )}
      </div>

      {/* Role Tabs */}
      <div className="border-b border-gray-200">
        <div className="flex space-x-4">
          {(['worker', 'foreman', 'admin'] as const).map((role) => (
            <button
              key={role}
              onClick={() => setActiveRole(role)}
              className={`px-4 py-2 border-b-2 font-medium ${
                activeRole === role
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {role.charAt(0).toUpperCase() + role.slice(1)} ({menu.roles[role]?.length || 0})
            </button>
          ))}
        </div>
      </div>

      {/* Commands Table */}
      <div className="bg-white border border-gray-200 rounded">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Command
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Label
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Description
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                Core
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                Enabled
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {commands.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                  No commands available for this role
                </td>
              </tr>
            ) : (
              commands.map((cmd) => {
              const edited = editedCommands.get(cmd.id);
              const isEnabled = edited?.enabled ?? cmd.enabled;

              return (
                <tr key={cmd.id} className={isEnabled ? '' : 'bg-gray-50 opacity-60'}>
                  <td className="px-4 py-3 text-sm font-mono text-gray-900">
                    {cmd.telegram_command}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-900">
                    {edited?.label || cmd.label}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {cmd.description || '—'}
                  </td>
                  <td className="px-4 py-3 text-center text-sm">
                    {cmd.is_core ? '🔒' : '—'}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button
                      onClick={() => toggleEnabled(cmd.id, cmd.is_core)}
                      disabled={cmd.is_core && isEnabled}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        isEnabled ? 'bg-blue-600' : 'bg-gray-300'
                      } ${cmd.is_core && isEnabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}
                      title={cmd.is_core && isEnabled ? 'Core commands cannot be disabled' : ''}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          isEnabled ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </td>
                </tr>
              );
            }))}
          </tbody>
        </table>
      </div>

      {/* Info Box */}
      <div className="bg-blue-50 border border-blue-200 rounded p-4 text-sm">
        <div className="flex items-start space-x-2">
          <span className="text-blue-600">ℹ️</span>
          <div className="text-blue-800">
            <p className="font-medium">About Bot Menu Configuration:</p>
            <ul className="mt-2 space-y-1 list-disc list-inside">
              <li>Core commands (🔒) cannot be disabled (required for bot operation)</li>
              <li>Changes are saved to database but NOT applied to Telegram bot yet</li>
              <li>Use "Apply to Bot" feature (future) to sync with Telegram</li>
              <li>Version increments on each save to prevent conflicts</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
