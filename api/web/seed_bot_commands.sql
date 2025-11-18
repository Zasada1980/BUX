-- Seed bot_commands table for E2E testing

-- Admin commands (3 total: 2 core, 1 non-core)
INSERT INTO bot_commands (role, command_key, telegram_command, label, description, enabled, is_core, position, command_type)
VALUES 
('admin', 'dashboard', '/dashboard', 'Dashboard', 'View admin dashboard', 1, 1, 10, 'menu'),
('admin', 'reports', '/reports', 'Reports', 'Generate reports', 1, 0, 20, 'menu'),
('admin', 'settings', '/settings', 'Settings', 'Configure bot settings', 1, 1, 30, 'menu');

-- Foreman commands (2 total: 1 core, 1 non-core)
INSERT INTO bot_commands (role, command_key, telegram_command, label, description, enabled, is_core, position, command_type)
VALUES 
('foreman', 'approve_expenses', '/approve', 'Approve Expenses', 'Review pending expenses', 1, 1, 10, 'menu'),
('foreman', 'team_status', '/team', 'Team Status', 'View team shifts', 1, 0, 20, 'menu');

-- Worker commands (4 total: 2 core, 2 non-core)
INSERT INTO bot_commands (role, command_key, telegram_command, label, description, enabled, is_core, position, command_type)
VALUES 
('worker', 'shift_in', '/in', 'Start Shift', 'Clock in', 1, 1, 10, 'menu'),
('worker', 'shift_out', '/out', 'End Shift', 'Clock out', 1, 1, 20, 'menu'),
('worker', 'add_expense', '/expense', 'Add Expense', 'Report expense', 1, 0, 30, 'menu'),
('worker', 'my_status', '/status', 'My Status', 'Check current shift', 1, 0, 40, 'menu');
