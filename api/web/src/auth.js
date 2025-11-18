/**
 * Authentication utilities for web interface.
 * Handles JWT token management, auto-refresh, and session persistence.
 */

const Auth = {
    /**
     * Get access token from sessionStorage.
     * @returns {string|null} Access token or null if not authenticated
     */
    getAccessToken() {
        return sessionStorage.getItem('access_token');
    },
    
    /**
     * Get refresh token from sessionStorage.
     * @returns {string|null} Refresh token or null
     */
    getRefreshToken() {
        return sessionStorage.getItem('refresh_token');
    },
    
    /**
     * Set tokens in sessionStorage.
     * @param {string} accessToken - JWT access token
     * @param {string} refreshToken - JWT refresh token
     */
    setTokens(accessToken, refreshToken) {
        sessionStorage.setItem('access_token', accessToken);
        sessionStorage.setItem('refresh_token', refreshToken);
        sessionStorage.setItem('token_timestamp', Date.now().toString());
    },
    
    /**
     * Clear tokens from sessionStorage (logout).
     */
    clearTokens() {
        sessionStorage.removeItem('access_token');
        sessionStorage.removeItem('refresh_token');
        sessionStorage.removeItem('token_timestamp');
        sessionStorage.removeItem('current_user');
    },
    
    /**
     * Check if user is authenticated.
     * @returns {boolean}
     */
    isAuthenticated() {
        const accessToken = this.getAccessToken();
        return accessToken !== null && accessToken !== '';
    },
    
    /**
     * Check if token needs refresh (if older than 12 minutes).
     * Access tokens expire in 15 minutes, refresh if <3 min remaining.
     * @returns {boolean}
     */
    needsRefresh() {
        const timestamp = sessionStorage.getItem('token_timestamp');
        if (!timestamp) return false;
        
        const age = Date.now() - parseInt(timestamp);
        const twelveMinutes = 12 * 60 * 1000; // 12 minutes in ms
        
        return age > twelveMinutes;
    },
    
    /**
     * Refresh access token using refresh token.
     * @returns {Promise<boolean>} True if successful
     */
    async refreshToken() {
        const refreshToken = this.getRefreshToken();
        
        if (!refreshToken) {
            return false;
        }
        
        try {
            const response = await fetch('/api/auth/refresh', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: refreshToken })
            });
            
            if (!response.ok) {
                // Refresh failed, clear tokens
                this.clearTokens();
                return false;
            }
            
            const tokens = await response.json();
            this.setTokens(tokens.access_token, tokens.refresh_token);
            
            return true;
        } catch (error) {
            console.error('Token refresh failed:', error);
            this.clearTokens();
            return false;
        }
    },
    
    /**
     * Get current user info from API (with caching).
     * @returns {Promise<object>} User object {employee, permissions}
     */
    async getCurrentUser() {
        // Check cache (5 min TTL)
        const cached = sessionStorage.getItem('current_user');
        const cacheTimestamp = sessionStorage.getItem('current_user_timestamp');
        
        if (cached && cacheTimestamp) {
            const age = Date.now() - parseInt(cacheTimestamp);
            if (age < 5 * 60 * 1000) { // 5 minutes
                return JSON.parse(cached);
            }
        }
        
        // Fetch from API
        try {
            const response = await fetch('/api/auth/me', {
                headers: {
                    'Authorization': `Bearer ${this.getAccessToken()}`
                }
            });
            
            if (!response.ok) {
                if (response.status === 401) {
                    // Try refresh
                    const refreshed = await this.refreshToken();
                    if (refreshed) {
                        // Retry with new token
                        return this.getCurrentUser();
                    }
                }
                throw new Error('Failed to fetch user info');
            }
            
            const user = await response.json();
            
            // Cache result
            sessionStorage.setItem('current_user', JSON.stringify(user));
            sessionStorage.setItem('current_user_timestamp', Date.now().toString());
            
            return user;
        } catch (error) {
            console.error('Get current user failed:', error);
            throw error;
        }
    },
    
    /**
     * Logout user (revoke refresh token and clear session).
     * @returns {Promise<void>}
     */
    async logout() {
        const refreshToken = this.getRefreshToken();
        
        if (refreshToken) {
            try {
                await fetch('/api/auth/logout', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${this.getAccessToken()}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ refresh_token: refreshToken })
                });
            } catch (error) {
                console.error('Logout API call failed:', error);
            }
        }
        
        // Clear tokens regardless of API call result
        this.clearTokens();
        
        // Redirect to login
        window.location.href = '/login.html';
    },
    
    /**
     * Initialize auth guard (redirect to login if not authenticated).
     * Call this in index.html on page load.
     */
    initAuthGuard() {
        if (!this.isAuthenticated()) {
            window.location.href = '/login.html';
            return;
        }
        
        // Check if token needs refresh
        if (this.needsRefresh()) {
            this.refreshToken().then(success => {
                if (!success) {
                    window.location.href = '/login.html';
                }
            });
        }
        
        // Set up auto-refresh interval (every 10 minutes)
        setInterval(() => {
            if (this.needsRefresh()) {
                this.refreshToken().then(success => {
                    if (!success) {
                        window.location.href = '/login.html';
                    }
                });
            }
        }, 10 * 60 * 1000); // 10 minutes
    },
    
    /**
     * Check if current user has permission.
     * @param {string} permission - Permission string (e.g., 'employees.create')
     * @returns {Promise<boolean>}
     */
    async hasPermission(permission) {
        try {
            const user = await this.getCurrentUser();
            return user.permissions.includes(permission);
        } catch (error) {
            return false;
        }
    },
    
    /**
     * Get user role.
     * @returns {Promise<string>} Role (admin, foreman, worker)
     */
    async getRole() {
        try {
            const user = await this.getCurrentUser();
            return user.employee.role;
        } catch (error) {
            return 'worker';
        }
    }
};

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Auth;
}
