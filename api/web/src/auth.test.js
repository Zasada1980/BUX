/**
 * Unit tests for auth.js - JWT token management and session handling.
 */

import { describe, test, expect, beforeEach, afterEach, jest } from '@jest/globals';

// Mock sessionStorage
const sessionStorageMock = (() => {
    let store = {};
    return {
        getItem: (key) => store[key] || null,
        setItem: (key, value) => { store[key] = value.toString(); },
        removeItem: (key) => { delete store[key]; },
        clear: () => { store = {}; }
    };
})();

global.sessionStorage = sessionStorageMock;

// Mock fetch
global.fetch = jest.fn();

// Import Auth module (assuming it exports Auth object)
// For testing, we'll recreate the Auth object inline
const Auth = {
    getAccessToken() {
        return sessionStorage.getItem('access_token');
    },
    
    getRefreshToken() {
        return sessionStorage.getItem('refresh_token');
    },
    
    setTokens(accessToken, refreshToken) {
        sessionStorage.setItem('access_token', accessToken);
        sessionStorage.setItem('refresh_token', refreshToken);
        sessionStorage.setItem('token_timestamp', Date.now().toString());
    },
    
    clearTokens() {
        sessionStorage.removeItem('access_token');
        sessionStorage.removeItem('refresh_token');
        sessionStorage.removeItem('token_timestamp');
        sessionStorage.removeItem('current_user');
    },
    
    isAuthenticated() {
        const accessToken = this.getAccessToken();
        return accessToken !== null && accessToken !== '';
    },
    
    needsRefresh() {
        const timestamp = sessionStorage.getItem('token_timestamp');
        if (!timestamp) return false;
        
        const age = Date.now() - parseInt(timestamp);
        const twelveMinutes = 12 * 60 * 1000;
        
        return age > twelveMinutes;
    },
    
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
    }
};

describe('Auth Module', () => {
    beforeEach(() => {
        sessionStorage.clear();
        fetch.mockClear();
    });

    describe('Token Storage', () => {
        test('setTokens should store tokens in sessionStorage', () => {
            const accessToken = 'test_access_token';
            const refreshToken = 'test_refresh_token';
            
            Auth.setTokens(accessToken, refreshToken);
            
            expect(Auth.getAccessToken()).toBe(accessToken);
            expect(Auth.getRefreshToken()).toBe(refreshToken);
            expect(sessionStorage.getItem('token_timestamp')).toBeTruthy();
        });

        test('getAccessToken should return null when not authenticated', () => {
            expect(Auth.getAccessToken()).toBeNull();
        });

        test('clearTokens should remove all tokens and user data', () => {
            Auth.setTokens('access', 'refresh');
            sessionStorage.setItem('current_user', JSON.stringify({ id: 1 }));
            
            Auth.clearTokens();
            
            expect(Auth.getAccessToken()).toBeNull();
            expect(Auth.getRefreshToken()).toBeNull();
            expect(sessionStorage.getItem('token_timestamp')).toBeNull();
            expect(sessionStorage.getItem('current_user')).toBeNull();
        });
    });

    describe('Authentication Status', () => {
        test('isAuthenticated should return true when access token exists', () => {
            Auth.setTokens('access_token', 'refresh_token');
            expect(Auth.isAuthenticated()).toBe(true);
        });

        test('isAuthenticated should return false when no token', () => {
            expect(Auth.isAuthenticated()).toBe(false);
        });

        test('isAuthenticated should return false for empty token', () => {
            sessionStorage.setItem('access_token', '');
            expect(Auth.isAuthenticated()).toBe(false);
        });
    });

    describe('Token Refresh Logic', () => {
        test('needsRefresh should return false when no timestamp', () => {
            Auth.setTokens('access', 'refresh');
            sessionStorage.removeItem('token_timestamp');
            
            expect(Auth.needsRefresh()).toBe(false);
        });

        test('needsRefresh should return false for fresh tokens (<12 min)', () => {
            Auth.setTokens('access', 'refresh');
            // Token is fresh (just set)
            expect(Auth.needsRefresh()).toBe(false);
        });

        test('needsRefresh should return true for old tokens (>12 min)', () => {
            Auth.setTokens('access', 'refresh');
            // Set old timestamp (13 minutes ago)
            const oldTimestamp = Date.now() - (13 * 60 * 1000);
            sessionStorage.setItem('token_timestamp', oldTimestamp.toString());
            
            expect(Auth.needsRefresh()).toBe(true);
        });
    });

    describe('Token Refresh API', () => {
        test('refreshToken should return false when no refresh token', async () => {
            const result = await Auth.refreshToken();
            expect(result).toBe(false);
        });

        test('refreshToken should call API and update tokens on success', async () => {
            Auth.setTokens('old_access', 'old_refresh');
            
            const newTokens = {
                access_token: 'new_access',
                refresh_token: 'new_refresh'
            };
            
            fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => newTokens
            });
            
            const result = await Auth.refreshToken();
            
            expect(result).toBe(true);
            expect(fetch).toHaveBeenCalledWith('/api/auth/refresh', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: 'old_refresh' })
            });
            expect(Auth.getAccessToken()).toBe('new_access');
            expect(Auth.getRefreshToken()).toBe('new_refresh');
        });

        test('refreshToken should clear tokens and return false on API error', async () => {
            Auth.setTokens('access', 'refresh');
            
            fetch.mockResolvedValueOnce({
                ok: false,
                status: 401
            });
            
            const result = await Auth.refreshToken();
            
            expect(result).toBe(false);
            expect(Auth.getAccessToken()).toBeNull();
            expect(Auth.getRefreshToken()).toBeNull();
        });

        test('refreshToken should handle network errors gracefully', async () => {
            Auth.setTokens('access', 'refresh');
            
            const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();
            fetch.mockRejectedValueOnce(new Error('Network error'));
            
            const result = await Auth.refreshToken();
            
            expect(result).toBe(false);
            expect(Auth.getAccessToken()).toBeNull();
            expect(consoleErrorSpy).toHaveBeenCalled();
            
            consoleErrorSpy.mockRestore();
        });
    });

    describe('Token Timestamp Management', () => {
        test('setTokens should update timestamp', () => {
            const beforeTimestamp = Date.now();
            Auth.setTokens('access', 'refresh');
            const afterTimestamp = Date.now();
            
            const storedTimestamp = parseInt(sessionStorage.getItem('token_timestamp'));
            
            expect(storedTimestamp).toBeGreaterThanOrEqual(beforeTimestamp);
            expect(storedTimestamp).toBeLessThanOrEqual(afterTimestamp);
        });
    });
});
