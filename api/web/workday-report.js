const RECORDS_KEY = 'accounting:workRecords';
const EMPLOYEES_KEY = 'spark-employees';
const MONTH_PREF_KEY = '__workday_report_month__';
const STYLE_ID = 'workday-report-styles';
const LAUNCHER_ID = 'workday-report-launcher';
const FILTER_CLASS = 'workday-report-filter';

const reportState = {
    month: '',
    filters: { employee: '', location: '' },
    overlay: null,
    container: null,
    csvRows: [],
    escHandler: null,
    pendingRefresh: false
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
