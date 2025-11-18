const RECORDS_KEY = 'accounting:workRecords';
const EMPLOYEES_KEY = 'spark-employees';
const MONTH_PREF_KEY = '__workday_report_month__';
const STYLE_ID = 'workday-report-styles';
const LAUNCHER_ID = 'workday-report-launcher';
const PANELS = {
  REPORT: 'report',
  IMPORT: 'import'
};
const PAYMENTS_KEY = 'spark-employee-payments';
const reportState = {
  month: '',
  filters: { employee: '', location: '' },
  overlay: null,
  container: null,
  csvRows: [],
  escHandler: null,
  pendingRefresh: false,
  panelMode: PANELS.REPORT,
  import_text: '',
  import_preview: [],
  import_status: ''
};

const STYLE_DEFINITION = `
#${LAUNCHER_ID} { position: fixed; right: 1.5rem; bottom: 1.5rem; z-index: 2147483000; background: #111827; color: #fff; border: none; border-radius: 999px; padding: 0.75rem 1.5rem; font-size: 0.95rem; box-shadow: 0 18px 45px rgba(15,23,42,0.35); cursor: pointer; }
#${LAUNCHER_ID}:hover { background: #1f2937; }
#${LAUNCHER_ID}:focus { outline: 2px solid #38bdf8; outline-offset: 2px; }
.workday-report-overlay { position: fixed; inset: 0; background: rgba(15,23,42,0.65); z-index: 2147483001; display: flex; align-items: center; justify-content: center; padding: 1rem; }
.workday-report-panel { width: min(100%, 960px); max-height: 90vh; background: #fff; border-radius: 1rem; display: flex; flex-direction: column; box-shadow: 0 25px 65px rgba(15,23,42,0.55); overflow: hidden; }
.workday-report-header { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.75rem; padding: 1.25rem 1.5rem; border-bottom: 1px solid rgba(15,23,42,0.1); }
.workday-report-controls { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; }
.workday-report-filter { padding: 0.35rem 0.5rem; border-radius: 0.5rem; border: 1px solid rgba(15,23,42,0.2); font-size: 0.9rem; min-width: 10rem; }
.workday-report-btn, .workday-report-export { border: 1px solid rgba(15,23,42,0.15); background: #f3f4f6; border-radius: 999px; padding: 0.35rem 0.9rem; font-size: 0.85rem; cursor: pointer; }
.workday-report-btn:hover, .workday-report-export:hover { background: #e5e7eb; }
.workday-report-close { background: transparent; border: none; font-size: 1.5rem; line-height: 1; color: #6b7280; cursor: pointer; }
.workday-report-body { padding: 1rem 1.5rem; overflow: auto; }
.workday-report-section { margin-bottom: 1.5rem; }
.workday-report-summary { display: flex; flex-direction: column; gap: 0.35rem; margin-bottom: 0.5rem; }
.workday-report-summary-title { display: flex; gap: 0.5rem; align-items: center; font-size: 1.05rem; }
.workday-report-badge { font-size: 0.75rem; background: #eef2ff; color: #4338ca; padding: 0.1rem 0.5rem; border-radius: 0.5rem; }
.workday-report-summary-stats { display: flex; flex-wrap: wrap; gap: 0.35rem; font-size: 0.85rem; color: #4b5563; }
.workday-report-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.workday-report-table th { text-align: left; padding: 0.65rem 0.5rem; border-bottom: 1px solid rgba(15,23,42,0.1); }
.workday-report-table td { padding: 0.5rem; border-bottom: 1px solid rgba(15,23,42,0.05); vertical-align: top; }
.workday-report-empty { padding: 2rem; text-align: center; color: #6b7280; }
.workday-report-stat { background: #eef2ff; color: #1f2937; padding: 0.15rem 0.6rem; border-radius: 999px; font-size: 0.8rem; }
@media (prefers-color-scheme: dark) { .workday-report-panel { background: #0f172a; color: #f8fafc; } .workday-report-header { border-bottom-color: rgba(248,250,252,0.1); } .workday-report-summary-stats { color: #e5e7eb; } .workday-report-table th { border-color: rgba(248,250,252,0.15); } .workday-report-table td { border-color: rgba(248,250,252,0.08); } .workday-report-btn, .workday-report-export { background: rgba(148,163,184,0.2); color: #f8fafc; border-color: rgba(148,163,184,0.3); } .workday-report-badge { background: rgba(79,70,229,0.25); color: #c7d2fe; } }
.workday-report-mode { display: flex; gap: 0.25rem; margin-right: 0.5rem; }
.workday-report-mode button { border: 1px solid rgba(255,255,255,0.4); background: rgba(255,255,255,0.08); color: inherit; border-radius: 999px; padding: 0.25rem 0.8rem; cursor: pointer; font-size: 0.85rem; }
.workday-report-mode button[data-active="true"] { background: rgba(255,255,255,0.15); box-shadow: 0 0 0 2px rgba(59,130,246,0.4); }
`;

function injectStyles() {
  if (document.getElementById(STYLE_ID)) {
    return;
  }
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = STYLE_DEFINITION;
  document.head.appendChild(style);
}

function parseJson(value, fallback) {
  if (!value) {
    return fallback;
  }
  try {
    return JSON.parse(value) || fallback;
  } catch (error) {
    return fallback;
  }
}

function renderActiveTab(container) {
  if (reportState.panelMode === PANELS.IMPORT) {
    renderImportTab(container);
  } else {
    renderReport(container);
  }
}

function renderImportTab(container) {
  container.textContent = '';
  const label = document.createElement('p');
  label.textContent = 'Paste Excel rows (Name\\tAmount), one per line.';
  const textarea = document.createElement('textarea');
  textarea.className = 'workday-report-filter';
  textarea.style.minHeight = '150px';
  textarea.value = reportState.import_text;
  textarea.addEventListener('input', () => {
    reportState.import_text = textarea.value;
    reportState.import_preview = parseSalaryLines(reportState.import_text);
    refreshPanel();
  });
  const previewTitle = document.createElement('p');
  previewTitle.textContent = 'Preview:';
  const table = document.createElement('table');
  table.className = 'workday-report-table';
  const thead = document.createElement('thead');
  const headRow = document.createElement('tr');
  ['Name', 'Amount', 'Matched', 'Status'].forEach((text) => {
    const th = document.createElement('th');
    th.textContent = text;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  reportState.import_preview.forEach((item) => {
    const row = document.createElement('tr');
    [item.name, item.amount != null ? item.amount : '—', item.match?.name || '—', item.status].forEach((value) => {
      const td = document.createElement('td');
      td.textContent = value;
      row.appendChild(td);
    });
    tbody.appendChild(row);
  });
  table.appendChild(tbody);
  const status = document.createElement('p');
  status.textContent = reportState.import_status;
  const importButton = document.createElement('button');
  importButton.type = 'button';
  importButton.className = 'workday-report-btn';
  importButton.textContent = 'Import Salaries';
  importButton.addEventListener('click', () => {
    applySalaryImport();
    refreshPanel();
  });
  container.appendChild(label);
  container.appendChild(textarea);
  container.appendChild(document.createElement('br'));
  container.appendChild(previewTitle);
  container.appendChild(table);
  container.appendChild(status);
  container.appendChild(importButton);
}
function loadRecords() {
  return parseJson(window.localStorage?.getItem(RECORDS_KEY), []);
}

function loadEmployees() {
  return parseJson(window.localStorage?.getItem(EMPLOYEES_KEY), []);
}

function formatNumber(value) {
  try {
    return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(value);
  } catch (error) {
    return String(value);
  }
}

function formatDisplayDate(value) {
  if (!value) {
    return '—';
  }
  try {
    const parsed = new Date(value);
    if (isNaN(parsed.getTime())) {
      return value;
    }
    return new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium' }).format(parsed);
  } catch (error) {
    return value;
  }
}

function loadPayments() {
  return parseJson(window.localStorage?.getItem(PAYMENTS_KEY), []);
}

function savePayments(payments) {
  window.localStorage?.setItem(PAYMENTS_KEY, JSON.stringify(payments));
}

function buildReportData() {
  const records = loadRecords();
  const employees = loadEmployees();
  const groups = new Map();
  const employeeFilter = reportState.filters.employee?.trim().toLowerCase();
  const locationFilter = reportState.filters.location?.trim().toLowerCase();
  records.forEach((record) => {
    if (!record || typeof record !== 'object') {
      return;
    }
    const date = record.date || '';
    if (reportState.month && date.slice(0, 7) !== reportState.month) {
      return;
    }
    const employeeName = record.employeeName?.trim() || 'Без имени';
    if (employeeFilter && !employeeName.toLowerCase().includes(employeeFilter)) {
      return;
    }
    const location = record.location?.trim() || '';
    if (locationFilter && !location.toLowerCase().includes(locationFilter)) {
      return;
    }
    let group = groups.get(employeeName);
    if (!group) {
      const meta = employees.find((entry) => entry.name?.trim() && entry.name.trim().toLowerCase() === employeeName.toLowerCase());
      group = {
        name: employeeName,
        employeeId: meta?.id,
        position: meta?.position,
        phone: meta?.phone,
        totalQuantity: 0,
        totalEntries: 0,
        days: new Map()
      };
      groups.set(employeeName, group);
    }
    const dayKey = date || 'Не указано';
    let day = group.days.get(dayKey);
    if (!day) {
      day = { date: dayKey, quantity: 0, entries: 0, locations: new Set(), notes: [] };
      group.days.set(dayKey, day);
    }
    const quantity = Number(record.quantity) || 0;
    day.quantity += quantity;
    day.entries += 1;
    group.totalQuantity += quantity;
    group.totalEntries += 1;
    if (record.location) {
      day.locations.add(String(record.location));
    }
    if (record.notes) {
      day.notes.push(String(record.notes));
    }
  });
  return Array.from(groups.values())
    .map((group) => {
      const dayList = Array.from(group.days.values()).sort((a, b) => b.date.localeCompare(a.date));
      return { ...group, totalDays: dayList.length, dayList };
    })
    .sort((a, b) => {
      if (b.totalQuantity === a.totalQuantity) {
        return a.name.localeCompare(b.name);
      }
      return b.totalQuantity - a.totalQuantity;
    });
}

function normalizeName(name) {
  return name?.trim().toLowerCase() || '';
}

function parseSalaryLines(rawText) {
  return rawText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const cols = line.split(/\t|;/).map((c) => c.trim());
      const name = cols[0] || '';
      const amount = parseFloat((cols[1] || '').replace(',', '.'));
      const match = loadEmployees().find(
        (emp) => normalizeName(emp.name) === normalizeName(name)
      );
      return {
        id: index + 1,
        raw: line,
        name,
        amount: Number.isNaN(amount) ? null : amount,
        match,
        status: match ? 'matched' : 'no match'
      };
    });
}

function applySalaryImport() {
  const entries = reportState.import_preview.filter(
    (item) => item.match && item.amount !== null
  );
  if (!entries.length) {
    reportState.import_status = 'No valid rows to import.';
    return;
  }
  const payments = loadPayments();
  const added = entries.map((entry) => ({
    id: `import-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    employeeId: entry.match.id,
    date: new Date().toISOString(),
    amount: entry.amount,
    source: 'report-import'
  }));
  const merged = [...payments, ...added];
  savePayments(merged);
  reportState.import_status = `${added.length} payment${added.length > 1 ? 's' : ''} saved.`;
}

function downloadCsv(rows) {
  if (!rows.length || rows.length === 1) {
    console.warn('[workday-report] no data for CSV export.');
    return;
  }
  const csv = rows
    .map((row) => row.map((cell) => '"' + (cell == null ? '' : String(cell)).replace(/"/g, '""') + '"').join(';'))
    .join('\r\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'workday-report.csv';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function downloadJson(data) {
  if (!data.length) {
    console.warn('[workday-report] no data for JSON export.');
    return;
  }
  const payload = { month: reportState.month || 'all', generatedAt: new Date().toISOString(), data };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'workday-report.json';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function renderReport(container) {
  if (!container) {
    return;
  }
  container.textContent = '';
  const data = buildReportData();
  reportState.csvRows = data.reduce(
    (rows, employee) => {
      employee.dayList.forEach((day) => {
        rows.push([employee.name, day.date, String(day.entries), String(day.quantity), day.locations.size ? Array.from(day.locations).join(', ') : '', day.notes.length ? day.notes.join(' | ') : '', employee.employeeId || '']);
      });
      return rows;
    },
    [['Сотрудник', 'Дата', 'Записей', 'Кол-во', 'Локации', 'Заметки', 'ID']]
  );
  if (!data.length) {
    const empty = document.createElement('p');
    empty.className = 'workday-report-empty';
    empty.textContent = 'Нет записей за выбранный период.';
    container.appendChild(empty);
    return;
  }
  data.forEach((employee) => {
    const section = document.createElement('section');
    section.className = 'workday-report-section';
    const summary = document.createElement('div');
    summary.className = 'workday-report-summary';
    const title = document.createElement('div');
    title.className = 'workday-report-summary-title';
    const strong = document.createElement('strong');
    strong.textContent = employee.name;
    title.appendChild(strong);
    if (employee.employeeId) {
      const badge = document.createElement('span');
      badge.className = 'workday-report-badge';
      badge.textContent = 'ID: ' + employee.employeeId;
      title.appendChild(badge);
    }
    summary.appendChild(title);
    const stats = document.createElement('div');
    stats.className = 'workday-report-summary-stats';
    [{ label: 'Дней', value: employee.totalDays }, { label: 'Записей', value: employee.totalEntries }, { label: 'Объем', value: formatNumber(employee.totalQuantity) }].forEach((item) => {
      const span = document.createElement('span');
      span.className = 'workday-report-stat';
      span.textContent = `${item.label}: ${item.value}`;
      stats.appendChild(span);
    });
    summary.appendChild(stats);
    section.appendChild(summary);
    const table = document.createElement('table');
    table.className = 'workday-report-table';
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    ['Дата', 'Записей', 'Кол-во', 'Локации', 'Заметки'].forEach((label) => {
      const th = document.createElement('th');
      th.textContent = label;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    const tbody = document.createElement('tbody');
    employee.dayList.forEach((day) => {
      const row = document.createElement('tr');
      [formatDisplayDate(day.date), String(day.entries), formatNumber(day.quantity), day.locations.size ? Array.from(day.locations).join(', ') : '—', day.notes.length ? day.notes.join(' | ') : '—'].forEach((text) => {
        const td = document.createElement('td');
        td.textContent = text;
        row.appendChild(td);
      });
      tbody.appendChild(row);
    });
    table.appendChild(tbody);
    section.appendChild(table);
    container.appendChild(section);
  });
}

function refreshPanel() {
  if (!reportState.container || reportState.pendingRefresh) {
    return;
  }
  reportState.pendingRefresh = true;
  requestAnimationFrame(() => {
    reportState.pendingRefresh = false;
    renderActiveTab(reportState.container);
  });
}

function openPanel() {
  if (reportState.overlay) {
    return;
  }
  injectStyles();
  const overlay = document.createElement('div');
  overlay.className = 'workday-report-overlay';
  const panel = document.createElement('div');
  panel.className = 'workday-report-panel';
  const header = document.createElement('div');
  header.className = 'workday-report-header';
  const title = document.createElement('h2');
  title.textContent = 'Отчёт по рабочим дням';
  header.appendChild(title);
  const controls = document.createElement('div');
  controls.className = 'workday-report-controls';
  const monthLabel = document.createElement('label');
  monthLabel.className = 'workday-report-filter';
  monthLabel.textContent = 'Месяц:';
  const monthInput = document.createElement('input');
  monthInput.type = 'month';
  monthInput.value = reportState.month;
  monthInput.addEventListener('change', () => {
    reportState.month = monthInput.value;
    if (reportState.month) {
      window.localStorage?.setItem(MONTH_PREF_KEY, reportState.month);
    } else {
      window.localStorage?.removeItem(MONTH_PREF_KEY);
    }
    refreshPanel();
  });
  monthLabel.appendChild(monthInput);
  controls.appendChild(monthLabel);
  controls.appendChild(createFilter('Сотрудник', 'employee'));
  controls.appendChild(createFilter('Локация', 'location'));
  controls.appendChild(createButton('Все месяцы', () => {
    reportState.month = '';
    monthInput.value = '';
    window.localStorage?.removeItem(MONTH_PREF_KEY);
    refreshPanel();
  }, 'workday-report-btn'));
  controls.appendChild(createButton('Обновить', refreshPanel, 'workday-report-btn'));
  controls.appendChild(createButton('Экспорт CSV', () => downloadCsv(reportState.csvRows), 'workday-report-btn'));
  controls.appendChild(createButton('Экспорт JSON', () => downloadJson(buildReportData()), 'workday-report-export'));
  const closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.className = 'workday-report-close';
  closeBtn.setAttribute('aria-label', 'Закрыть отчет');
  closeBtn.textContent = '×';
  closeBtn.addEventListener('click', closePanel);
  header.appendChild(controls);
  header.appendChild(closeBtn);
  panel.appendChild(header);
  const modeSwitcher = document.createElement('div');
  modeSwitcher.className = 'workday-report-mode';
  const reportTab = createModeButton('Отчёт', PANELS.REPORT);
  const importTab = createModeButton('Импорт зарплат', PANELS.IMPORT);
  modeSwitcher.appendChild(reportTab);
  modeSwitcher.appendChild(importTab);
  header.insertBefore(modeSwitcher, controls);
  const body = document.createElement('div');
  body.className = 'workday-report-body';
  panel.appendChild(body);
  overlay.appendChild(panel);
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) {
      closePanel();
    }
  });
  document.body.appendChild(overlay);
  reportState.overlay = overlay;
  reportState.container = body;
  reportState.escHandler = (event) => {
    if (event.key === 'Escape') {
      closePanel();
    }
  };
  document.addEventListener('keydown', reportState.escHandler);
  refreshPanel();
}

function createModeButton(label, mode) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.textContent = label;
  btn.dataset.mode = mode;
  btn.setAttribute('data-active', reportState.panelMode === mode ? 'true' : 'false');
  btn.addEventListener('click', () => setPanelMode(mode));
  return btn;
}

function setPanelMode(mode) {
  reportState.panelMode = mode;
  if (mode === PANELS.IMPORT) {
    reportState.import_preview = parseSalaryLines(reportState.import_text);
  }
  refreshPanel();
  document.querySelectorAll('.workday-report-mode button').forEach((btn) => {
    btn.setAttribute('data-active', btn.dataset.mode === mode ? 'true' : 'false');
  });
}

function createFilter(label, key) {
  const input = document.createElement('input');
  input.type = 'text';
  input.placeholder = label;
  input.className = 'workday-report-filter';
  input.value = reportState.filters[key];
  input.addEventListener('input', () => {
    reportState.filters[key] = input.value;
    refreshPanel();
  });
  return input;
}

function createButton(text, handler, className) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = className;
  button.textContent = text;
  button.addEventListener('click', handler);
  return button;
}

function closePanel() {
  if (!reportState.overlay) {
    return;
  }
  document.removeEventListener('keydown', reportState.escHandler);
  reportState.escHandler = null;
  reportState.overlay.remove();
  reportState.overlay = null;
  reportState.container = null;
}

function ensureLauncher() {
  if (document.getElementById(LAUNCHER_ID)) {
    return;
  }
  const button = document.createElement('button');
  button.id = LAUNCHER_ID;
  button.type = 'button';
  button.textContent = 'Отчёт по рабочим дням';
  button.addEventListener('click', openPanel);
  document.body.appendChild(button);
}

function ready(fn) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', fn, { once: true });
    return;
  }
  fn();
}

ready(() => {
  injectStyles();
  ensureLauncher();
  try {
    if (typeof Storage !== 'undefined' && !Storage.prototype.__workdayReportPatched) {
      const originalSetItem = Storage.prototype.setItem;
      Storage.prototype.setItem = function (key, value) {
        const result = originalSetItem.apply(this, arguments);
        if (key === RECORDS_KEY) {
          refreshPanel();
        }
        return result;
      };
      Object.defineProperty(Storage.prototype, '__workdayReportPatched', { value: true, configurable: false, enumerable: false, writable: false });
    }
  } catch (error) {
    console.warn('[workday-report] storage hook failed', error);
  }
  window.addEventListener('storage', (event) => {
    if (event?.key === RECORDS_KEY) {
      refreshPanel();
    }
  });
  reportState.month = window.localStorage?.getItem(MONTH_PREF_KEY) || '';
});
