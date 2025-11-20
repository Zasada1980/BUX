import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useToast } from '@/hooks/use-toast';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { BadgeStyled as Badge } from '@/components/ui/BadgeStyled';

interface UserCredential {
  id: number;
  employee_id: number;
  username: string;
  name: string;
  role: 'admin' | 'foreman' | 'worker';
  active: boolean;
  failed_attempts: number;
  locked_until: string | null;
  created_at: string;
}

export default function AccessTokensTab() {
  const { toast } = useToast();
  const [users, setUsers] = useState<UserCredential[]>([]);
  const [loading, setLoading] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  
  // Create user form
  const [newUser, setNewUser] = useState({
    username: '',
    password: '',
    name: '',
    role: 'worker' as 'admin' | 'foreman' | 'worker',
    telegram_id: '',
    telegram_username: '',
    phone: ''
  });

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      const response = await fetch('/api/auth/users', {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (!response.ok) throw new Error('Failed to load users');
      
      const data = await response.json();
      setUsers(data);
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Ошибка загрузки',
        description: error instanceof Error ? error.message : 'Не удалось загрузить пользователей'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async () => {
    if (!newUser.username || !newUser.password || !newUser.name) {
      toast({
        variant: 'destructive',
        title: 'Ошибка валидации',
        description: 'Заполните все обязательные поля'
      });
      return;
    }

    if (newUser.password.length < 8) {
      toast({
        variant: 'destructive',
        title: 'Слабый пароль',
        description: 'Пароль должен быть минимум 8 символов'
      });
      return;
    }

    try {
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      const payload: any = {
        username: newUser.username,
        password: newUser.password,
        name: newUser.name,
        role: newUser.role
      };
      
      if (newUser.telegram_id) {
        payload.telegram_id = parseInt(newUser.telegram_id);
      }
      
      if (newUser.telegram_username) {
        payload.telegram_username = newUser.telegram_username;
      }
      
      if (newUser.phone) {
        payload.phone = newUser.phone;
      }
      
      const response = await fetch('/api/auth/users', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create user');
      }
      
      toast({
        title: 'Пользователь создан',
        description: `${newUser.username} успешно добавлен`
      });
      
      setCreateDialogOpen(false);
      setNewUser({ username: '', password: '', name: '', role: 'worker', telegram_id: '', telegram_username: '', phone: '' });
      loadUsers();
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Ошибка создания',
        description: error instanceof Error ? error.message : 'Не удалось создать пользователя'
      });
    }
  };

  const handleDeleteUser = async (employeeId: number, username: string) => {
    if (!confirm(`Удалить пользователя ${username}? Все токены будут отозваны.`)) {
      return;
    }

    try {
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      const response = await fetch(`/api/auth/users/${employeeId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete user');
      }
      
      toast({
        title: 'Пользователь удалён',
        description: `${username} удалён из системы`
      });
      
      loadUsers();
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Ошибка удаления',
        description: error instanceof Error ? error.message : 'Не удалось удалить пользователя'
      });
    }
  };

  const handleRevokeTokens = async (employeeId: number, username: string) => {
    if (!confirm(`Отозвать все токены для ${username}?`)) {
      return;
    }

    try {
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      const response = await fetch(`/api/auth/users/${employeeId}/revoke-tokens`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to revoke tokens');
      }
      
      const result = await response.json();
      toast({
        title: 'Токены отозваны',
        description: result.message
      });
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Ошибка',
        description: error instanceof Error ? error.message : 'Не удалось отозвать токены'
      });
    }
  };

  const handleResetPassword = async (employeeId: number, username: string) => {
    const newPassword = prompt(`Новый пароль для ${username} (мин. 8 символов):`);
    if (!newPassword) return;
    
    if (newPassword.length < 8) {
      toast({
        variant: 'destructive',
        title: 'Слабый пароль',
        description: 'Пароль должен быть минимум 8 символов'
      });
      return;
    }

    try {
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      const response = await fetch(`/api/auth/users/${employeeId}/reset-password?new_password=${encodeURIComponent(newPassword)}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to reset password');
      }
      
      toast({
        title: 'Пароль сброшен',
        description: `Пароль для ${username} обновлён, все токены отозваны`
      });
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Ошибка',
        description: error instanceof Error ? error.message : 'Не удалось сбросить пароль'
      });
    }
  };

  const getRoleBadge = (role: string) => {
    const variants: Record<string, 'destructive' | 'outline'> = {
      admin: 'destructive',
      foreman: 'outline',
      worker: 'outline'
    };
    
    const labels: Record<string, string> = {
      admin: 'Админ',
      foreman: 'Бригадир',
      worker: 'Рабочий'
    };
    
    return <Badge variant={variants[role] || 'outline'}>{labels[role] || role}</Badge>;
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-medium">Управление доступом</h3>
          <p className="text-sm text-muted-foreground">
            Создавайте пользователей и управляйте их токенами доступа
          </p>
        </div>
        
        <Button onClick={() => setCreateDialogOpen(!createDialogOpen)}>
          ➕ Создать пользователя
        </Button>
      </div>

      {/* Create User Form */}
      {createDialogOpen && (
        <Card>
          <CardHeader>
            <CardTitle>Новый пользователь</CardTitle>
            <CardDescription>
              Создайте учётную запись с логином и паролем
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="username" className="text-sm font-medium">Логин *</label>
                <Input
                  id="username"
                  placeholder="admin"
                  value={newUser.username}
                  onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                />
              </div>
              
              <div className="space-y-2">
                <label htmlFor="password" className="text-sm font-medium">Пароль * (мин. 8 символов)</label>
                <Input
                  id="password"
                  type="password"
                  placeholder="********"
                  value={newUser.password}
                  onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                />
              </div>
              
              <div className="space-y-2">
                <label htmlFor="name" className="text-sm font-medium">Имя *</label>
                <Input
                  id="name"
                  placeholder="Admin User"
                  value={newUser.name}
                  onChange={(e) => setNewUser({ ...newUser, name: e.target.value })}
                />
              </div>
              
              <div className="space-y-2">
                <label htmlFor="role" className="text-sm font-medium">Роль *</label>
                <select
                  id="role"
                  className="w-full p-2 border rounded"
                  value={newUser.role}
                  onChange={(e) => setNewUser({ ...newUser, role: e.target.value as 'admin' | 'foreman' | 'worker' })}
                >
                  <option value="admin">Админ</option>
                  <option value="foreman">Бригадир</option>
                  <option value="worker">Рабочий</option>
                </select>
              </div>
              
              <div className="space-y-2">
                <label htmlFor="telegram_id" className="text-sm font-medium">Telegram ID (опционально)</label>
                <Input
                  id="telegram_id"
                  type="number"
                  placeholder="123456789"
                  value={newUser.telegram_id}
                  onChange={(e) => setNewUser({ ...newUser, telegram_id: e.target.value })}
                />
              </div>
              
              <div className="space-y-2">
                <label htmlFor="telegram_username" className="text-sm font-medium">Telegram Username (опционально)</label>
                <Input
                  id="telegram_username"
                  placeholder="@username"
                  value={newUser.telegram_username}
                  onChange={(e) => setNewUser({ ...newUser, telegram_username: e.target.value })}
                />
              </div>
              
              <div className="space-y-2">
                <label htmlFor="phone" className="text-sm font-medium">Телефон (опционально)</label>
                <Input
                  id="phone"
                  type="tel"
                  placeholder="+972-50-123-4567"
                  value={newUser.phone}
                  onChange={(e) => setNewUser({ ...newUser, phone: e.target.value })}
                />
              </div>
              
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
                  Отмена
                </Button>
                <Button onClick={handleCreateUser}>
                  Создать
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      {loading ? (
        <div className="text-center py-8">Загрузка...</div>
      ) : (
        <div className="grid gap-4">
          {users.map((user) => (
            <Card key={user.id}>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-base">
                      {user.name}
                      {!user.active && <Badge variant="destructive" className="ml-2">Неактивен</Badge>}
                      {user.locked_until && new Date(user.locked_until) > new Date() && (
                        <Badge variant="destructive" className="ml-2">Заблокирован</Badge>
                      )}
                    </CardTitle>
                    <CardDescription>
                      @{user.username} · {getRoleBadge(user.role)}
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleRevokeTokens(user.employee_id, user.username)}
                    >
                      🔐 Отозвать токены
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleResetPassword(user.employee_id, user.username)}
                    >
                      🔑 Сброс пароля
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleDeleteUser(user.employee_id, user.username)}
                    >
                      🗑️ Удалить
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">ID сотрудника:</span>
                    <div className="font-mono">{user.employee_id}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Неудачные попытки:</span>
                    <div>{user.failed_attempts}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Создан:</span>
                    <div>{new Date(user.created_at).toLocaleDateString('ru-RU')}</div>
                  </div>
                </div>
                
                {user.locked_until && new Date(user.locked_until) > new Date() && (
                  <div className="mt-4 p-3 bg-destructive/10 rounded-md text-sm">
                    ⚠️ Аккаунт заблокирован до {new Date(user.locked_until).toLocaleString('ru-RU')}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
          
          {users.length === 0 && (
            <Card>
              <CardContent className="text-center py-8 text-muted-foreground">
                Нет пользователей. Создайте первого пользователя.
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
