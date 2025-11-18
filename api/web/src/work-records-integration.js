/**
 * Work Records API Integration Layer
 * 
 * Provides a hybrid approach: fetch from API with localStorage fallback for offline support.
 * Auto-caching with 5-minute TTL.
 */

const WorkRecordsAPI = {
    // Cache configuration
    CACHE_KEY: 'api_work_records_cache',
    CACHE_TIMESTAMP_KEY: 'api_work_records_cache_timestamp',
    CACHE_TTL_MS: 5 * 60 * 1000, // 5 minutes

    /**
     * Get work records with caching and fallback
     * @param {Object} filters - { date_from, date_to, user_id, client_id }
     * @param {boolean} forceRefresh - Skip cache and force API call
     * @returns {Promise<Array>} Work records
     */
    async getWorkRecords(filters = {}, forceRefresh = false) {
        // Check cache first (unless force refresh)
        if (!forceRefresh && this.isCacheValid()) {
            const cached = this.getCachedRecords();
            if (cached) {
                console.log('[WorkRecordsAPI] Returning cached data');
                return this.filterCachedRecords(cached, filters);
            }
        }

        // Try API call
        try {
            console.log('[WorkRecordsAPI] Fetching from API', filters);
            const params = {
                page: 1,
                page_size: 1000, // Large page to get all records
                ...filters
            };

            const response = await API.getWorkRecords(params);
            const records = response.records || [];

            // Transform API records to localStorage format for compatibility
            const transformed = this.transformApiToLocalFormat(records);

            // Cache the results
            this.cacheRecords(transformed);

            console.log(`[WorkRecordsAPI] Fetched ${records.length} records from API`);
            return transformed;

        } catch (error) {
            console.error('[WorkRecordsAPI] API call failed, falling back to localStorage', error);

            // Fallback to localStorage
            return this.getLocalStorageRecords(filters);
        }
    },

    /**
     * Export work records (triggers download)
     * @param {string} format - 'csv' or 'json'
     * @param {Object} filters - Same as getWorkRecords
     */
    async exportWorkRecords(format = 'csv', filters = {}) {
        try {
            console.log(`[WorkRecordsAPI] Exporting as ${format}`, filters);
            await API.exportWorkRecords(format, filters);
            console.log('[WorkRecordsAPI] Export initiated');
        } catch (error) {
            console.error('[WorkRecordsAPI] Export failed', error);
            
            // Fallback: generate export from cached/localStorage data
            const records = await this.getWorkRecords(filters, false);
            this.fallbackExport(records, format);
        }
    },

    /**
     * Transform API response to localStorage format
     * @param {Array} apiRecords - Records from API
     * @returns {Array} Transformed records
     */
    transformApiToLocalFormat(apiRecords) {
        return apiRecords.map(record => ({
            // Match existing localStorage schema
            date: record.shift_start?.split('T')[0] || '',
            employeeName: record.employee_name || 'Без имени',
            location: record.work_address || '',
            shiftStart: record.shift_start,
            shiftEnd: record.shift_end,
            shiftDuration: record.shift_duration_hours,
            taskCount: record.task_count || 0,
            tasks: record.task_descriptions ? record.task_descriptions.split('; ') : [],
            expenseCount: record.expense_count || 0,
            totalExpenses: record.total_expenses || 0,
            expenseBreakdown: record.expense_breakdown || {},
            clientName: record.client_name || '',
            
            // Additional API fields
            shiftId: record.shift_id,
            userId: record.user_id,
            clientId: record.client_id
        }));
    },

    /**
     * Check if cache is still valid
     * @returns {boolean}
     */
    isCacheValid() {
        const timestamp = sessionStorage.getItem(this.CACHE_TIMESTAMP_KEY);
        if (!timestamp) return false;

        const age = Date.now() - parseInt(timestamp, 10);
        return age < this.CACHE_TTL_MS;
    },

    /**
     * Get cached records
     * @returns {Array|null}
     */
    getCachedRecords() {
        try {
            const cached = sessionStorage.getItem(this.CACHE_KEY);
            return cached ? JSON.parse(cached) : null;
        } catch (error) {
            console.error('[WorkRecordsAPI] Cache read error', error);
            return null;
        }
    },

    /**
     * Cache records
     * @param {Array} records
     */
    cacheRecords(records) {
        try {
            sessionStorage.setItem(this.CACHE_KEY, JSON.stringify(records));
            sessionStorage.setItem(this.CACHE_TIMESTAMP_KEY, Date.now().toString());
        } catch (error) {
            console.error('[WorkRecordsAPI] Cache write error', error);
        }
    },

    /**
     * Filter cached records client-side
     * @param {Array} records - Cached records
     * @param {Object} filters - Filters to apply
     * @returns {Array}
     */
    filterCachedRecords(records, filters) {
        let filtered = records;

        if (filters.date_from) {
            filtered = filtered.filter(r => r.date >= filters.date_from);
        }

        if (filters.date_to) {
            filtered = filtered.filter(r => r.date <= filters.date_to);
        }

        if (filters.user_id) {
            filtered = filtered.filter(r => r.userId === filters.user_id);
        }

        if (filters.client_id) {
            filtered = filtered.filter(r => r.clientId === filters.client_id);
        }

        return filtered;
    },

    /**
     * Fallback to localStorage (existing offline data)
     * @param {Object} filters
     * @returns {Array}
     */
    getLocalStorageRecords(filters) {
        try {
            const stored = localStorage.getItem('accounting:workRecords');
            const records = stored ? JSON.parse(stored) : [];

            // Apply basic date filtering
            let filtered = records;
            if (filters.date_from) {
                filtered = filtered.filter(r => (r.date || '') >= filters.date_from);
            }
            if (filters.date_to) {
                filtered = filtered.filter(r => (r.date || '') <= filters.date_to);
            }

            console.log(`[WorkRecordsAPI] Loaded ${filtered.length} records from localStorage`);
            return filtered;

        } catch (error) {
            console.error('[WorkRecordsAPI] localStorage read error', error);
            return [];
        }
    },

    /**
     * Fallback export using client-side data
     * @param {Array} records
     * @param {string} format
     */
    fallbackExport(records, format) {
        if (format === 'csv') {
            this.exportAsCsv(records);
        } else {
            this.exportAsJson(records);
        }
    },

    /**
     * Export as CSV (client-side)
     * @param {Array} records
     */
    exportAsCsv(records) {
        const headers = [
            'Дата',
            'Сотрудник',
            'Локация',
            'Начало смены',
            'Конец смены',
            'Длительность (ч)',
            'Задачи',
            'Расходы'
        ];

        const rows = records.map(r => [
            r.date || '',
            r.employeeName || '',
            r.location || '',
            r.shiftStart || '',
            r.shiftEnd || '',
            r.shiftDuration || '',
            r.taskCount || 0,
            r.totalExpenses || 0
        ]);

        const csv = [
            headers.join(','),
            ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
        ].join('\n');

        const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `work_records_${new Date().toISOString().split('T')[0]}.csv`;
        link.click();
        window.URL.revokeObjectURL(url);
    },

    /**
     * Export as JSON (client-side)
     * @param {Array} records
     */
    exportAsJson(records) {
        const json = JSON.stringify(records, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `work_records_${new Date().toISOString().split('T')[0]}.json`;
        link.click();
        window.URL.revokeObjectURL(url);
    },

    /**
     * Clear cache (force refresh on next call)
     */
    clearCache() {
        sessionStorage.removeItem(this.CACHE_KEY);
        sessionStorage.removeItem(this.CACHE_TIMESTAMP_KEY);
        console.log('[WorkRecordsAPI] Cache cleared');
    }
};

// Global export for use in workday-report.js
window.WorkRecordsAPI = WorkRecordsAPI;
