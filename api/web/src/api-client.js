/**
 * API client wrapper with retry logic and error handling.
 * Automatically handles JWT tokens, retries, and 401 redirects.
 */

const API = {
    /**
     * Base URL for API (defaults to current origin).
     */
    baseURL: window.location.origin,
    
    /**
     * Make API request with automatic token handling and retries.
     * @param {string} endpoint - API endpoint (e.g., '/api/employees')
     * @param {object} options - Fetch options
     * @param {number} retries - Number of retries (default 3)
     * @returns {Promise<Response>}
     */
    async request(endpoint, options = {}, retries = 3) {
        // Add Authorization header
        const accessToken = Auth.getAccessToken();
        if (accessToken) {
            options.headers = {
                ...options.headers,
                'Authorization': `Bearer ${accessToken}`
            };
        }
        
        // Add Content-Type for JSON requests
        if (options.body && typeof options.body === 'object') {
            options.headers = {
                ...options.headers,
                'Content-Type': 'application/json'
            };
            options.body = JSON.stringify(options.body);
        }
        
        const url = `${this.baseURL}${endpoint}`;
        
        try {
            const response = await fetch(url, options);
            
            // Handle 401 Unauthorized
            if (response.status === 401) {
                // Try to refresh token
                const refreshed = await Auth.refreshToken();
                
                if (refreshed && retries > 0) {
                    // Retry with new token
                    return this.request(endpoint, options, retries - 1);
                } else {
                    // Refresh failed, redirect to login
                    Auth.clearTokens();
                    window.location.href = '/login.html';
                    throw new Error('Unauthorized');
                }
            }
            
            // Handle 429 Rate Limit
            if (response.status === 429) {
                const retryAfter = response.headers.get('Retry-After');
                const delay = retryAfter ? parseInt(retryAfter) * 1000 : 2000;
                
                if (retries > 0) {
                    await this.sleep(delay);
                    return this.request(endpoint, options, retries - 1);
                }
            }
            
            // Handle network errors with exponential backoff
            if (!response.ok && retries > 0 && response.status >= 500) {
                const delay = Math.pow(2, 3 - retries) * 1000; // 1s, 2s, 4s
                await this.sleep(delay);
                return this.request(endpoint, options, retries - 1);
            }
            
            return response;
            
        } catch (error) {
            // Network error, retry with exponential backoff
            if (retries > 0) {
                const delay = Math.pow(2, 3 - retries) * 1000;
                await this.sleep(delay);
                return this.request(endpoint, options, retries - 1);
            }
            
            throw error;
        }
    },
    
    /**
     * Sleep utility for delays.
     * @param {number} ms - Milliseconds to sleep
     * @returns {Promise<void>}
     */
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    },
    
    /**
     * GET request.
     * @param {string} endpoint - API endpoint
     * @param {object} params - Query parameters
     * @returns {Promise<any>} - Parsed JSON response
     */
    async get(endpoint, params = {}) {
        // Build query string
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;
        
        const response = await this.request(url, { method: 'GET' });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Request failed');
        }
        
        return response.json();
    },
    
    /**
     * POST request.
     * @param {string} endpoint - API endpoint
     * @param {object} data - Request body
     * @returns {Promise<any>} - Parsed JSON response
     */
    async post(endpoint, data = {}) {
        const response = await this.request(endpoint, {
            method: 'POST',
            body: data
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Request failed');
        }
        
        return response.json();
    },
    
    /**
     * PUT request.
     * @param {string} endpoint - API endpoint
     * @param {object} data - Request body
     * @returns {Promise<any>} - Parsed JSON response
     */
    async put(endpoint, data = {}) {
        const response = await this.request(endpoint, {
            method: 'PUT',
            body: data
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Request failed');
        }
        
        return response.json();
    },
    
    /**
     * DELETE request.
     * @param {string} endpoint - API endpoint
     * @returns {Promise<void>}
     */
    async delete(endpoint) {
        const response = await this.request(endpoint, {
            method: 'DELETE'
        });
        
        if (!response.ok && response.status !== 204) {
            const error = await response.json();
            throw new Error(error.detail || 'Request failed');
        }
    },
    
    // ========== Employee Management ==========
    
    /**
     * List employees with filtering.
     * @param {object} params - Query params (page, page_size, role, is_active, search)
     * @returns {Promise<object>} - {employees, total, page, page_size}
     */
    async listEmployees(params = {}) {
        return this.get('/api/employees', params);
    },
    
    /**
     * Get employee by ID.
     * @param {number} id - Employee ID
     * @returns {Promise<object>} - Employee object
     */
    async getEmployee(id) {
        return this.get(`/api/employees/${id}`);
    },
    
    /**
     * Create new employee.
     * @param {object} data - Employee data
     * @returns {Promise<object>} - Created employee
     */
    async createEmployee(data) {
        const result = await this.post('/api/employees', data);
        // Trigger webhook to sync with Telegram bot
        this.triggerAgentSync();
        return result;
    },
    
    /**
     * Update employee.
     * @param {number} id - Employee ID
     * @param {object} data - Updated fields
     * @returns {Promise<object>} - Updated employee
     */
    async updateEmployee(id, data) {
        const result = await this.put(`/api/employees/${id}`, data);
        // Trigger webhook to sync with Telegram bot
        this.triggerAgentSync();
        return result;
    },
    
    /**
     * Delete employee (soft delete).
     * @param {number} id - Employee ID
     * @returns {Promise<void>}
     */
    async deleteEmployee(id) {
        return this.delete(`/api/employees/${id}`);
    },
    
    // ========== Work Records ==========
    
    /**
     * Get work records with filtering.
     * @param {object} params - Query params (page, page_size, date_from, date_to, user_id, client_id)
     * @returns {Promise<object>} - {records, total, page, page_size}
     */
    async getWorkRecords(params = {}) {
        return this.get('/api/work-records', params);
    },
    
    /**
     * Export work records as CSV or JSON.
     * @param {string} format - 'csv' or 'json'
     * @param {object} params - Filter params
     * @returns {Promise<Blob>} - File blob for download
     */
    async exportWorkRecords(format = 'csv', params = {}) {
        const queryString = new URLSearchParams({ ...params, format }).toString();
        const response = await this.request(`/api/work-records/export?${queryString}`, {
            method: 'GET'
        });
        
        if (!response.ok) {
            throw new Error('Export failed');
        }
        
        // Get filename from Content-Disposition header
        const contentDisposition = response.headers.get('Content-Disposition');
        const filename = contentDisposition 
            ? contentDisposition.split('filename=')[1].replace(/"/g, '')
            : `work_records.${format}`;
        
        const blob = await response.blob();
        
        // Trigger download
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        return blob;
    },
    
    // ========== Salaries ==========
    
    /**
     * Preview salary bulk import.
     * @param {string} csvData - CSV data (paste from Excel)
     * @returns {Promise<object>} - {matched, unmatched, preview_token}
     */
    async previewSalaryImport(csvData) {
        return this.post('/api/salaries/bulk-import/preview', { csv_data: csvData });
    },
    
    /**
     * Confirm salary bulk import.
     * @param {string} previewToken - Token from preview response
     * @param {string} idempotencyKey - Unique key for idempotency
     * @returns {Promise<object>} - {imported, errors}
     */
    async confirmSalaryImport(previewToken, idempotencyKey) {
        const response = await this.request('/api/salaries/bulk-import/confirm', {
            method: 'POST',
            headers: {
                'Idempotency-Key': idempotencyKey
            },
            body: { preview_token: previewToken }
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Import failed');
        }
        
        return response.json();
    },
    
    /**
     * Trigger Ollama agent sync webhook (fire-and-forget for data refresh).
     * Called automatically after save operations to sync Telegram bot users.
     * @returns {Promise<void>}
     */
    async triggerAgentSync() {
        try {
            // Fire-and-forget: don't wait for response
            fetch(`${this.baseURL}/api/webhook/sync-agent`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            }).catch(err => {
                console.warn('[API] Agent sync webhook failed (non-critical):', err);
            });
        } catch (error) {
            // Silent failure - webhook is non-critical
            console.warn('[API] Agent sync trigger error:', error);
        }
    }
};

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = API;
}
