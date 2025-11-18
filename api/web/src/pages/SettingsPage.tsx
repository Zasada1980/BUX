import { useState, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import { BadgeStyled as Badge } from '@/components/ui/BadgeStyled';
// F5: Bot Menu removed (will be separate page), all Bot Menu imports removed

interface GeneralSettings {
  company_name: string;
  timezone: string;
  contact_email: string;
  editable: boolean;
  note?: string;
}

interface BackupStatus {
  last_backup_at: string | null;
  backup_count: number;
  latest_file?: string;
  note?: string;
}

interface SystemInfo {
  versions: {
    api: string;
    bot: string;
    web_ui: string;
  };
  database: {
    exists: boolean;
    size_bytes: number;
    size_mb: number;
    path: string;
  };
  integrations: {
    telegram_bot: {
      status: string;
      note: string;
    };
    sqlite: {
      status: string;
      note: string;
    };
  };
  platform: {
    os: string;
    python: string;
  };
  generated_at: string;
}

export default function SettingsPage() {
  const { toast } = useToast();

  // F5: Bot Menu state removed (will be separate page)
  
  // General settings state
  const [generalSettings, setGeneralSettings] = useState<GeneralSettings | null>(null);
  const [loadingGeneral, setLoadingGeneral] = useState(false);
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null);
  
  // Backup state
  const [backupStatus, setBackupStatus] = useState<BackupStatus | null>(null);
  const [loadingBackup, setLoadingBackup] = useState(false);
  const [errorBackup, setErrorBackup] = useState<string | null>(null);
  const [creatingBackup, setCreatingBackup] = useState(false);
  
  // System Info state
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [loadingSystem, setLoadingSystem] = useState(false);
  const [errorSystem, setErrorSystem] = useState<string | null>(null);

  // F5: Bot Menu hooks/callbacks removed (will be separate page)
  
  // Load settings data on mount
  useEffect(() => {
    loadGeneralSettings();
    loadBackupStatus();
    loadSystemInfo();
  }, []);
  
  // Load General Settings
  const loadGeneralSettings = async () => {
    try {
      setLoadingGeneral(true);
      setErrorGeneral(null);
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      const response = await fetch('/api/settings/general', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!response.ok) throw new Error('Failed to load general settings');
      const data = await response.json();
      setGeneralSettings(data);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Не удалось загрузить общие настройки';
      setErrorGeneral(errorMessage);
      toast({
        variant: 'destructive',
        title: 'Ошибка загрузки',
        description: errorMessage,
      });
    } finally {
      setLoadingGeneral(false);
    }
  };
  
  // Load Backup Status
  const loadBackupStatus = async () => {
    try {
      setLoadingBackup(true);
      setErrorBackup(null);
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      const response = await fetch('/api/settings/backup', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!response.ok) throw new Error('Failed to load backup status');
      const data = await response.json();
      setBackupStatus(data);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Не удалось загрузить статус backup';
      setErrorBackup(errorMessage);
      toast({
        variant: 'destructive',
        title: 'Ошибка загрузки',
        description: errorMessage,
      });
    } finally {
      setLoadingBackup(false);
    }
  };
  
  // Create Backup
  const createBackup = async () => {
    try {
      setCreatingBackup(true);
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      const response = await fetch('/api/settings/backup/create', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!response.ok) throw new Error('Failed to create backup');
      const result = await response.json();
      
      toast({
        title: 'Backup создан',
        description: `Файл: ${result.filename}, размер: ${result.size_mb.toFixed(2)} MB`,
      });
      
      // Reload backup status
      await loadBackupStatus();
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Ошибка создания backup',
        description: error instanceof Error ? error.message : 'Не удалось создать backup',
      });
    } finally {
      setCreatingBackup(false);
    }
  };
  
  // Load System Info
  const loadSystemInfo = async () => {
    try {
      setLoadingSystem(true);
      setErrorSystem(null);
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      const response = await fetch('/api/settings/system', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!response.ok) throw new Error('Failed to load system info');
      const data = await response.json();
      setSystemInfo(data);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Не удалось загрузить системную информацию';
      setErrorSystem(errorMessage);
      toast({
        variant: 'destructive',
        title: 'Ошибка загрузки',
        description: errorMessage,
      });
    } finally {
      setLoadingSystem(false);
    }
  };

  // F5: Bot Menu handlers removed (will be separate page)

  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">Настройки</h1>

      <Tabs defaultValue="general" className="w-full">
        <TabsList>
          <TabsTrigger value="general">Общие</TabsTrigger>
          <TabsTrigger value="backup">Backup</TabsTrigger>
          <TabsTrigger value="system">Система</TabsTrigger>
        </TabsList>

        <TabsContent value="general">
          <Card>
            <CardHeader>
              <CardTitle>Общие настройки</CardTitle>
              <CardDescription>Информация о системе (только чтение)</CardDescription>
            </CardHeader>
            <CardContent>
              {loadingGeneral && <p className="text-muted-foreground">Загрузка...</p>}
              
              {errorGeneral && !loadingGeneral && (
                <div className="p-4 bg-red-50 border border-red-200 rounded">
                  <p className="text-red-800 mb-3">Ошибка: {errorGeneral}</p>
                  <Button onClick={loadGeneralSettings} variant="destructive" size="sm">
                    Повторить попытку
                  </Button>
                </div>
              )}
              
              {!loadingGeneral && !errorGeneral && generalSettings && (
                <div className="space-y-4">
                  <div className="grid grid-cols-[140px_1fr] gap-3 items-center">
                    <span className="text-sm font-medium">Компания:</span>
                    <span className="text-sm text-muted-foreground">{generalSettings.company_name}</span>
                  </div>
                  
                  <div className="grid grid-cols-[140px_1fr] gap-3 items-center">
                    <span className="text-sm font-medium">Часовой пояс:</span>
                    <span className="text-sm text-muted-foreground">{generalSettings.timezone}</span>
                  </div>
                  
                  <div className="grid grid-cols-[140px_1fr] gap-3 items-center">
                    <span className="text-sm font-medium">Email:</span>
                    <span className="text-sm text-muted-foreground">{generalSettings.contact_email}</span>
                  </div>
                  
                  {generalSettings.note && (
                    <div className="mt-4 p-3 bg-muted/30 rounded text-sm text-muted-foreground border border-muted">
                      <strong>Примечание:</strong> {generalSettings.note}
                    </div>
                  )}
                  
                  {!generalSettings.editable && (
                    <p className="text-xs text-muted-foreground italic mt-4">
                      💡 Редактирование пока не поддерживается. Для изменения настроек отредактируйте переменные окружения.
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="backup">
          <Card>
            <CardHeader>
              <CardTitle>Резервное копирование</CardTitle>
              <CardDescription>Управление backup базы данных</CardDescription>
            </CardHeader>
            <CardContent>
              {loadingBackup && <p className="text-muted-foreground">Загрузка...</p>}
              
              {errorBackup && !loadingBackup && (
                <div className="p-4 bg-red-50 border border-red-200 rounded">
                  <p className="text-red-800 mb-3">Ошибка: {errorBackup}</p>
                  <Button onClick={loadBackupStatus} variant="destructive" size="sm">
                    Повторить попытку
                  </Button>
                </div>
              )}
              
              {!loadingBackup && !errorBackup && backupStatus && (
                <div className="space-y-6">
                  <div className="space-y-3">
                    <div className="grid grid-cols-[160px_1fr] gap-3 items-center">
                      <span className="text-sm font-medium">Последний backup:</span>
                      <span className="text-sm text-muted-foreground">
                        {backupStatus.last_backup_at 
                          ? new Date(backupStatus.last_backup_at).toLocaleString('ru-RU') 
                          : 'Нет данных'}
                      </span>
                    </div>
                    
                    <div className="grid grid-cols-[160px_1fr] gap-3 items-center">
                      <span className="text-sm font-medium">Количество файлов:</span>
                      <span className="text-sm text-muted-foreground">{backupStatus.backup_count}</span>
                    </div>
                    
                    {backupStatus.latest_file && (
                      <div className="grid grid-cols-[160px_1fr] gap-3 items-start">
                        <span className="text-sm font-medium">Последний файл:</span>
                        <span className="text-sm text-muted-foreground font-mono break-all">
                          {backupStatus.latest_file}
                        </span>
                      </div>
                    )}
                  </div>
                  
                  <div className="pt-4 border-t">
                    <Button 
                      onClick={createBackup} 
                      disabled={creatingBackup}
                      variant="default"
                    >
                      {creatingBackup ? 'Создание backup...' : '💾 Создать backup'}
                    </Button>
                    <p className="text-xs text-muted-foreground mt-2">
                      Создаёт копию shifts.db в директорию ./backups с текущей датой/временем
                    </p>
                  </div>
                  
                  {backupStatus.note && (
                    <div className="p-3 bg-muted/30 rounded text-sm text-muted-foreground border border-muted">
                      💡 {backupStatus.note}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="system">
          <Card>
            <CardHeader>
              <CardTitle>Системная информация</CardTitle>
              <CardDescription>Версии компонентов и статус интеграций</CardDescription>
            </CardHeader>
            <CardContent>
              {loadingSystem && <p className="text-muted-foreground">Загрузка...</p>}
              
              {errorSystem && !loadingSystem && (
                <div className="p-4 bg-red-50 border border-red-200 rounded">
                  <p className="text-red-800 mb-3">Ошибка: {errorSystem}</p>
                  <Button onClick={loadSystemInfo} variant="destructive" size="sm">
                    Повторить попытку
                  </Button>
                </div>
              )}
              
              {!loadingSystem && !errorSystem && systemInfo && (
                <div className="space-y-6">
                  {/* Versions */}
                  <div>
                    <h3 className="text-sm font-semibold mb-3">Версии компонентов</h3>
                    <div className="space-y-2">
                      <div className="grid grid-cols-[140px_1fr] gap-3 items-center">
                        <span className="text-sm">API:</span>
                        <code className="text-sm text-muted-foreground font-mono">{systemInfo.versions.api}</code>
                      </div>
                      <div className="grid grid-cols-[140px_1fr] gap-3 items-center">
                        <span className="text-sm">Telegram Bot:</span>
                        <code className="text-sm text-muted-foreground font-mono">{systemInfo.versions.bot}</code>
                      </div>
                      <div className="grid grid-cols-[140px_1fr] gap-3 items-center">
                        <span className="text-sm">Web UI:</span>
                        <code className="text-sm text-muted-foreground font-mono">{systemInfo.versions.web_ui}</code>
                      </div>
                    </div>
                  </div>
                  
                  {/* Database */}
                  <div className="pt-4 border-t">
                    <h3 className="text-sm font-semibold mb-3">База данных</h3>
                    <div className="space-y-2">
                      <div className="grid grid-cols-[140px_1fr] gap-3 items-center">
                        <span className="text-sm">Статус:</span>
                        <Badge variant={systemInfo.database.exists ? "default" : "destructive"}>
                          {systemInfo.database.exists ? '✅ OK' : '❌ Не найдена'}
                        </Badge>
                      </div>
                      <div className="grid grid-cols-[140px_1fr] gap-3 items-center">
                        <span className="text-sm">Размер:</span>
                        <span className="text-sm text-muted-foreground">
                          {systemInfo.database.size_mb.toFixed(2)} MB ({systemInfo.database.size_bytes.toLocaleString()} bytes)
                        </span>
                      </div>
                      <div className="grid grid-cols-[140px_1fr] gap-3 items-start">
                        <span className="text-sm">Путь:</span>
                        <code className="text-sm text-muted-foreground font-mono break-all">
                          {systemInfo.database.path}
                        </code>
                      </div>
                    </div>
                  </div>
                  
                  {/* Integrations */}
                  <div className="pt-4 border-t">
                    <h3 className="text-sm font-semibold mb-3">Интеграции</h3>
                    <div className="space-y-3">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-medium">Telegram Bot:</span>
                          <Badge variant={systemInfo.integrations.telegram_bot.status === 'configured' ? "default" : "outline"}>
                            {systemInfo.integrations.telegram_bot.status === 'configured' ? '✅ Настроен' : '⚠️ Не настроен'}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground pl-1">
                          {systemInfo.integrations.telegram_bot.note}
                        </p>
                      </div>
                      
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-medium">SQLite:</span>
                          <Badge variant="default">✅ {systemInfo.integrations.sqlite.status}</Badge>
                        </div>
                        <p className="text-xs text-muted-foreground pl-1">
                          {systemInfo.integrations.sqlite.note}
                        </p>
                      </div>
                    </div>
                  </div>
                  
                  {/* Platform */}
                  <div className="pt-4 border-t">
                    <h3 className="text-sm font-semibold mb-3">Платформа</h3>
                    <div className="space-y-2">
                      <div className="grid grid-cols-[140px_1fr] gap-3 items-center">
                        <span className="text-sm">ОС:</span>
                        <span className="text-sm text-muted-foreground">{systemInfo.platform.os}</span>
                      </div>
                      <div className="grid grid-cols-[140px_1fr] gap-3 items-center">
                        <span className="text-sm">Python:</span>
                        <code className="text-sm text-muted-foreground font-mono">{systemInfo.platform.python}</code>
                      </div>
                    </div>
                  </div>
                  
                  <div className="pt-4 text-xs text-muted-foreground italic">
                    Обновлено: {new Date(systemInfo.generated_at).toLocaleString('ru-RU')}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

      </Tabs>
    </div>
  );
}
