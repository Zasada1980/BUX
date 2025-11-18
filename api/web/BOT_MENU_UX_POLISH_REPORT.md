# Bot Menu UX Polish Report — Phase 2

> **⚠️ HISTORICAL DOCUMENT NOTICE**  
> Этот документ является **историческим отчётом** по UX полишу Telegram Bot Menu (Phase 2, ноябрь 2025).
>
> **НЕ используйте как источник правды** по текущему состоянию UX и реализации.
>
> **Актуальное состояние см.**:
> - **UX_ARCHITECTURE.md** → раздел "Known Limitations & Roadmap → Settings → Telegram Bot Tab"
> - **FRONTEND_ARCHITECTURE.md** → Page Status Matrix, Pattern 10: Unsaved Changes Guard, A11y Status
> - **DESIGN_SYSTEM.md** → Bot Menu Preview Cards
> - **UX_PLAYBOOK.md** → Scenario 6: Admin настраивает команды Telegram-бота
>
> **Цель документа**: История спринта, контекст UX улучшений, code examples.

**Author**: AI Agent (Copilot)  
**Date**: 2025-01-XX  
**Status**: ✅ **COMPLETE** (Code + Documentation)  
**Scope**: UX enhancements для Settings → Telegram Bot tab (БЕЗ изменений backend/bot логики)

---

## Executive Summary

В рамках Phase 2 UX Polish было реализовано **3 критических UX-улучшения** для Settings → Telegram Bot:

1. **Unsaved Changes Guard** — Защита от случайной потери несохранённых изменений (SPA + browser navigation)
2. **Explanatory Disclaimer** — Информационный блок, разъясняющий назначение вкладки (управление отображением ≠ создание логики)
3. **Menu Preview** — Визуальный предпросмотр меню бота по ролям (Admin/Foreman/Worker) с live update

**Результат**: Пользователи получают:
- **Безопасность**: Невозможно случайно потерять несохранённую работу
- **Прозрачность**: Чёткое понимание, что вкладка управляет отображением, а не добавляет функции
- **Визуальный фидбек**: Видят итоговое меню до применения к Telegram

**Ограничения (по ТЗ)**:
- ❌ Backend endpoints НЕ изменены (API контракты остались прежними)
- ❌ Бизнес-логика бота НЕ тронута (aiogram хэндлеры без изменений)
- ✅ Только фронтенд (React components, hooks, UI primitives)

---

## Improvements Made

### 1. Unsaved Changes Guard ✅

**Проблема**: Admin мог случайно уйти со страницы с несохранёнными изменениями → потеря работы.

**Решение**: Двухуровневая защита:

**A. SPA Navigation** (внутри React App):
- **Hook**: `useUnsavedChangesGuard` (React Router `useBlocker` API)
- **Условие**: Срабатывает если `hasChanges()=true` и пользователь пытается сменить route
- **UI**: Модальное окно "Несохранённые изменения" с 2 кнопками:
  - [Остаться на странице] → Navigation отменяется, фокус возвращается к редактированию
  - [Уйти без сохранения] → Navigation продолжается, локальный state сбрасывается
- **A11y**: Modal имеет `role="alertdialog"`, `aria-modal="true"`, logical focus order

**B. Browser Navigation** (refresh/close tab):
- **Механизм**: `window.beforeunload` event listener
- **Условие**: Срабатывает если `hasChanges()=true` при попытке закрыть/обновить вкладку
- **UI**: Браузер показывает стандартное предупреждение "Changes you made may not be saved."
- **Очистка**: Handler удаляется после успешного сохранения (`hasChanges()=false`)

**Файлы созданы**:
- `api/web/src/hooks/useUnsavedChangesGuard.ts` (60 lines) — Reusable hook
- `api/web/src/components/UnsavedChangesDialog.tsx` (30 lines) — Modal dialog component
- `api/web/src/components/ui/alert-dialog.tsx` (110 lines) — AlertDialog UI primitives (shadcn/ui style)

**Reusable**: Hook может применяться ко всем страницам с формами/конфигами (Users edit, Clients edit, future forms).

**Ограничения**:
- beforeunload текст нельзя кастомизировать (браузерная безопасность)
- F5 refresh показывает предупреждение (ожидаемое поведение)
- Не блокирует normal navigation если `hasChanges()=false`

---

### 2. Explanatory Disclaimer ✅

**Проблема**: Пользователи могли думать, что вкладка создаёт новые команды бота или изменяет бизнес-логику.

**Решение**: Info-блок в CardHeader (над таблицами) с двумя параграфами:

**Текст**:
> **Что делает эта вкладка**
> Здесь вы управляете **отображением уже существующих команд Telegram-бота**:
> включаете или выключаете команды в меню, меняете подписи (label), которые видят пользователи.
> 
> **Важно**: эта вкладка **не создаёт новую бизнес-логику и не добавляет новые команды** —
> бот по-прежнему выполняет только те действия, которые реализованы на сервере. 
> Меню ≠ права доступа и ≠ новые функции.

**Дизайн**:
- Фон: `bg-muted/50` (светло-серый, визуально отделён от основного контента)
- Границы: `border border-muted`, `rounded-lg`
- Отступы: `p-4` (внутренние), `mt-4` (сверху от CardDescription)
- Шрифт: `text-sm`, `text-muted-foreground` с `<strong>` для акцентов

**A11y**:
- Semantic HTML: `<p>`, `<strong>` (нет лишних div)
- Readable contrast: WCAG AA compliant (text-muted-foreground на bg-muted/50)
- Informational only: Нет интерактивных элементов

**Результат**: Чёткое разделение между "управление отображением" и "создание функций".

---

### 3. Menu Preview ✅

**Проблема**: Admin не видел финальный вид меню до применения к Telegram → неудобно проверять изменения.

**Решение**: Блок "Предпросмотр меню" с 3 карточками (Admin/Foreman/Worker) под таблицами, перед кнопками.

**Структура**:
```
┌─ [Предпросмотр меню]  [Badge: С учётом несохранённых изменений] ──┐
│                                                                     │
│ ┌─ Admin ──────┐  ┌─ Foreman ──┐  ┌─ Worker ────┐                 │
│ │ /users — 👥  │  │ /inbox — 📥│  │ /start — ▶️ │                 │
│ │ /tasks — ✅  │  │ /worker — 👷│  │ /worker — 👷│                 │
│ │ /expenses —  │  │ ...         │  │             │                 │
│ │ ...          │  └─────────────┘  └─────────────┘                 │
│ └──────────────┘                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

**Логика**:
- **Источник данных**: `currentData` (текущий state с учётом несохранённых изменений)
- **Фильтрация**: Только команды с `enabled=true`
- **Сортировка**: По полю `position` (ascending)
- **Формат строки**: `/command` — "Label" (с emoji из label)
- **Пустое меню**: "Нет команд в меню (все выключены)" (если все `enabled=false`)
- **Badge индикатор**: Показывается над preview только если `hasChanges()=true`

**Дизайн**:
- **Layout**: `grid grid-cols-1 md:grid-cols-3 gap-4` (responsive: 1 колонка mobile, 3 desktop)
- **Card styling**: `border-2` (толще обычных), `padding: 1rem`, белый фон
- **Role badges**:
  - Admin: `variant="destructive"` (red)
  - Foreman: Custom orange (`bg-orange-100 text-orange-800`)
  - Worker: `variant="default"` (blue)
- **Command list**: `font-mono`, `text-sm`, `leading-relaxed`
- **Empty state**: `italic`, `text-muted-foreground`

**Live Update**: Preview пересчитывается при каждом изменении `currentData` (real-time feedback).

**A11y**:
- Read-only: Нет focusable elements (только статический текст)
- Semantic structure: Card → CardHeader (title + badge) → CardContent (list)
- No extra tab stops (preview не участвует в keyboard navigation)

**Результат**: Admin видит точный вид меню до нажатия [Apply to Bot].

---

## Files Changed

### 📁 Created Files (3)

1. **`api/web/src/hooks/useUnsavedChangesGuard.ts`** (60 lines)
   - Reusable React hook для unsaved changes protection
   - SPA navigation: React Router `useBlocker`
   - Browser navigation: `window.beforeunload` event
   - Returns: `{isBlocked, proceed, reset}`
   - Dependencies: `react`, `react-router-dom`

2. **`api/web/src/components/UnsavedChangesDialog.tsx`** (30 lines)
   - Modal dialog component для confirmation
   - Props: `{open, onStay, onLeave}`
   - Title: "Несохранённые изменения"
   - Actions: [Остаться на странице] / [Уйти без сохранения]
   - Uses AlertDialog primitives

3. **`api/web/src/components/ui/alert-dialog.tsx`** (110 lines)
   - AlertDialog UI primitives (shadcn/ui style)
   - Components: AlertDialog, Content, Header, Footer, Title, Description, Action, Cancel
   - Styling: Tailwind CSS, fixed overlay z-50, modal backdrop bg-black/50
   - A11y: `role="alertdialog"`, `aria-modal="true"`

### ✏️ Modified Files (1)

4. **`api/web/src/pages/SettingsPage.tsx`** (305 → ~400 lines, +95 lines)
   - **Imports added**: `Badge`, `useUnsavedChangesGuard`, `UnsavedChangesDialog`
   - **Hook integration** (line ~30):
     ```tsx
     const { isBlocked, proceed, reset } = useUnsavedChangesGuard({
       when: hasChanges(),
       onNavigateAway: () => { setCurrentData(null); setOriginalData(null); },
     });
     ```
   - **Disclaimer block** (in CardHeader, after CardDescription):
     - Container: `bg-muted/50 rounded-lg border p-4 mt-4`
     - Content: 2 paragraphs with `<strong>` emphasis
   - **Preview block** (before action buttons):
     - Container: `mt-8 pt-6 border-t`
     - Header: "Предпросмотр меню" + Badge (if hasChanges)
     - Grid: `grid-cols-1 md:grid-cols-3 gap-4`
     - 3 Cards: Admin/Foreman/Worker with enabled commands, sorted by position
   - **Dialog integration** (end of JSX):
     ```tsx
     <UnsavedChangesDialog open={isBlocked} onStay={reset} onLeave={proceed} />
     ```

**Total Code Changes**: ~200 lines added (3 new files + 1 modified file).

---

## Documentation Updated

### 📚 Master Documents (4)

1. **`UX_ARCHITECTURE.md`** (Tab 5: Telegram Bot section)
   - Added section **0. Explanatory Disclaimer**:
     - Text, purpose, styling (bg-muted/50, border)
   - Added section **3. Menu Preview**:
     - 3 cards, filtering, sorting, format, badge logic
   - Added scenario **0. Попытка уйти со страницы с несохранёнными изменениями**:
     - SPA navigation: Modal flow (2 buttons)
     - Browser navigation: beforeunload warning
     - Guard disabling logic

2. **`FRONTEND_ARCHITECTURE.md`**
   - **Page Status Matrix**: Updated Settings row
     - Old: "⚠️ Partial | Telegram Bot tab only (Config)"
     - New: "✅ ENHANCED | Telegram Bot (Config + Preview + Guard) | 3 tables + 3 cards | AlertDialog, Badge"
   - **UX Patterns section**: Added **Pattern 10: Unsaved Changes Guard Pattern**
     - Hook implementation (`useUnsavedChangesGuard`)
     - Usage example (SettingsPage integration)
     - Modal dialog structure
     - Key UX requirements (A11y, reusability)
     - Etalon status (reference for future forms)
   - **A11y Status**: Added Settings → Telegram Bot enhancements
     - ✅ Unsaved Changes Guard: Modal A11y compliant
     - ✅ Preview Cards: Read-only, semantic
     - ✅ Disclaimer Block: Semantic structure, readable contrast
     - ⚠️ Limitations: beforeunload cannot be customized
     - ⚠️ Screen reader testing: Not performed (pending Phase 5)

3. **`DESIGN_SYSTEM.md`**
   - Added section **"Bot Menu Preview Cards"** (after Settings Tables):
     - Use Case: Visual preview of Telegram bot menu per role
     - Design Tokens:
       - Preview card: border-2, padding, background
       - Role badges: Admin (red), Foreman (orange), Worker (blue)
       - Command list: monospace, 14px, line-height 1.5
       - Empty state: italic, muted color
       - Unsaved badge: bg-secondary, 12px, padding 4px/8px
     - Responsive: 1 column mobile, 3 columns desktop

4. **`UX_PLAYBOOK.md`** (Scenario 6 updates)
   - Added step **5. Observe explanatory disclaimer**:
     - Info block with "Что делает эта вкладка"
     - Clear expectation: Menu = display control, not new features
   - Added step **6a. Attempt to navigate away with unsaved changes**:
     - Modal dialog flow (2 choices)
     - beforeunload warning for browser navigation
   - Added step **8. Check menu preview**:
     - 3 cards (Admin/Foreman/Worker)
     - Badge indicator for unsaved changes
     - Verification before save/apply

**Documentation Volume**: ~500 lines added/updated across 4 docs.

---

## Roadmap (NOT Implemented)

**Явно НЕ включено в эту фазу** (для будущих улучшений):

1. **i18n для command labels** (Multi-language support):
   - Хранить labels на английском + русском в БД
   - UI переключатель языка (для интернациональных команд)
   - Требует: Backend миграция (добавить `label_en`/`label_ru` поля)
   - Priority: **LOW** (пока нет интернациональных юзеров)

2. **Drag&Drop reordering** (Визуальное управление позициями):
   - Перетаскивание строк в таблицах для изменения `position`
   - UI library: `@dnd-kit/core` или `react-beautiful-dnd`
   - Требует: Refactor таблиц (обёртка в DragContext, onDragEnd handler)
   - Priority: **MEDIUM** (упростит UX, но не критично)

3. **Custom Commands** (Добавление новых команд через UI):
   - UI форма: telegram_command (input), label (input), role (select), description (textarea)
   - Backend: `POST /api/admin/bot-menu/custom` endpoint
   - Bot logic: Generic command handler с динамической регистрацией
   - Risks: Требует изменения бота (нарушает текущий scope "только отображение")
   - Priority: **LOW** (требует переосмысления архитектуры)

4. **Usage Analytics** (Отслеживание популярности команд):
   - Логирование использования команд в боте (count по command + user_id + timestamp)
   - Dashboard: Топ-10 команд, частота, heatmap по времени суток
   - Требует: Backend таблица `bot_command_usage`, Telegram bot middleware для логирования
   - Priority: **MEDIUM** (полезно для оптимизации меню)

5. **Deep A11y Audit** (Comprehensive accessibility testing):
   - Screen reader testing: JAWS, NVDA (Windows), VoiceOver (macOS)
   - Keyboard shortcuts: Global hotkeys для быстрого сохранения (`Ctrl+S`), отмены (`Ctrl+Z`)
   - High contrast mode: Тестирование Windows High Contrast
   - Focus visible: Улучшение `:focus-visible` индикаторов
   - ARIA live regions: Обновления preview объявляются screen reader'ом
   - Priority: **HIGH** (запланировано на Phase 5)

**Roadmap Criteria**: Все пункты требуют либо backend changes (1-4), либо extensive testing (5) → выходят за рамки Phase 2 UX Polish.

---

## Screenshots / Code Examples

### Hook Usage Example

```typescript
// api/web/src/pages/SettingsPage.tsx (line ~30)
const { isBlocked, proceed, reset } = useUnsavedChangesGuard({
  when: hasChanges(),  // Uses existing hasChanges() logic
  message: 'У вас есть несохранённые изменения в меню бота. Если уйти со страницы, они будут потеряны.',
  onNavigateAway: () => {
    setCurrentData(null);
    setOriginalData(null);
  },
});
```

### Modal Dialog Structure

```tsx
// api/web/src/components/UnsavedChangesDialog.tsx
export function UnsavedChangesDialog({ open, onStay, onLeave }: Props) {
  return (
    <AlertDialog open={open}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Несохранённые изменения</AlertDialogTitle>
          <AlertDialogDescription>
            У вас есть несохранённые изменения в меню бота. 
            Если уйти со страницы, они будут потеряны.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onStay}>
            Остаться на странице
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={onLeave}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            Уйти без сохранения
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
```

### Preview Cards JSX

```tsx
// api/web/src/pages/SettingsPage.tsx (preview block)
<div className="mt-8 pt-6 border-t">
  <div className="flex items-center gap-2 mb-4">
    <h3 className="text-lg font-semibold">Предпросмотр меню</h3>
    {hasChanges() && (
      <Badge variant="secondary" className="text-xs">
        С учётом несохранённых изменений
      </Badge>
    )}
  </div>
  
  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
    {/* Admin Card */}
    <Card className="border-2">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Admin
          <Badge variant="destructive" className="text-xs">admin</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {currentData?.roles.admin
          .filter(cmd => cmd.enabled)
          .sort((a, b) => a.position - b.position)
          .map(cmd => (
            <div key={cmd.telegram_command} className="font-mono text-sm">
              <span className="text-muted-foreground shrink-0">
                {cmd.telegram_command}
              </span>
              {' — '}
              <span className="break-words">{cmd.label}</span>
            </div>
          ))}
        {currentData?.roles.admin.filter(cmd => cmd.enabled).length === 0 && (
          <div className="text-sm text-muted-foreground italic">
            Нет команд в меню (все выключены)
          </div>
        )}
      </CardContent>
    </Card>
    
    {/* Foreman Card, Worker Card — similar structure */}
  </div>
</div>
```

---

## Validation Checklist

**ШАГ 4: A11y и UX Verification** ✅

- [x] **Guard doesn't block normal navigation**: Протестировано — при `hasChanges()=false` навигация не блокируется
- [x] **Modal A11y compliant**: AlertDialog имеет `role="alertdialog"`, `aria-modal="true"`, logical focus order
- [x] **Preview is read-only**: Нет интерактивных элементов, только статический текст (no extra tab stops)
- [x] **beforeunload works**: Browser показывает native warning при попытке закрыть/обновить tab с изменениями
- [x] **Live update preview**: Preview пересчитывается при каждом изменении `currentData` (real-time feedback)
- [x] **Badge indicator**: Badge "С учётом несохранённых изменений" появляется только при `hasChanges()=true`
- [x] **Disclaimer readable**: Текст чёткий, контраст WCAG AA compliant, semantic HTML
- [x] **No backend changes**: API endpoints не изменены (подтверждено — только фронтенд)
- [x] **No bot logic changes**: aiogram хэндлеры не тронуты (подтверждено)
- [x] **Documentation complete**: Все 4 master docs обновлены (UX_ARCHITECTURE, FRONTEND_ARCHITECTURE, DESIGN_SYSTEM, UX_PLAYBOOK)

---

## Conclusion

**Phase 2 UX Polish успешно завершён**:

- ✅ **3 UX improvements реализовано**: Guard, Disclaimer, Preview
- ✅ **4 файла изменено**: 3 новых (hook, dialog, alert-dialog) + 1 обновлён (SettingsPage)
- ✅ **4 master docs обновлено**: UX, Frontend, Design, Playbook
- ✅ **~200 lines кода**, ~500 lines документации
- ✅ **Backward compatible**: Никаких breaking changes для backend/bot
- ✅ **Reusable patterns**: useUnsavedChangesGuard hook готов для других форм

**Что получили пользователи**:
1. **Защита от потери данных** — Невозможно случайно уйти с несохранёнными изменениями
2. **Прозрачность** — Чёткое понимание: меню ≠ новые функции
3. **Визуальный фидбек** — Live preview итогового меню по ролям

**Готовность к production**: ✅ **READY** (код протестирован, документация полная, A11y базовый уровень соблюдён).

**Next Steps** (опционально):
- Deploy to staging → QA тестирование
- Screen reader testing (JAWS/NVDA) → Phase 5
- Drag&drop reordering → Phase 3 или по запросу
- Custom commands → Архитектурное обсуждение (требует изменения бота)

---

**EOF** — Bot Menu UX Polish Report v1.0
