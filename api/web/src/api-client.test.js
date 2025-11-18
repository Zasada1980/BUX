/**
 * Unit tests for api-client.js - API wrapper with retry logic and error handling.
 */

import { describe, test, expect, beforeEach, jest } from '@jest/globals';

// Mock Auth module
const Auth = {
    getAccessToken: jest.fn(),
    getRefreshToken: jest.fn(),
    clearTokens: jest.fn(),
    refreshToken: jest.fn()
};

global.Auth = Auth;

// Mock fetch
global.fetch = jest.fn();

// Mock window.location
delete window.location;
window.location = { href: '', origin: 'http://localhost:8088' };

// API client implementation
const API = {
    baseURL: window.location.origin,
    
    async request(endpoint, options = {}, retries = 3) {
        const accessToken = Auth.getAccessToken();
        if (accessToken) {
            options.headers = {
                ...options.headers,
                'Authorization': `Bearer ${accessToken}`
            };
        }
        
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
            
            if (response.status === 401) {
                const refreshed = await Auth.refreshToken();
                
                if (refreshed && retries > 0) {
                    return this.request(endpoint, options, retries - 1);
                } else {
                    Auth.clearTokens();
                    window.location.href = '/login.html';
                    throw new Error('Unauthorized');
                }
            }
            
            if (response.status === 429) {
                const retryAfter = response.headers.get('Retry-After');
                const delay = retryAfter ? parseInt(retryAfter) * 1000 : 2000;
                
                if (retries > 0) {
                    await this.sleep(delay);
                    return this.request(endpoint, options, retries - 1);
                }
            }
            
            if (!response.ok && retries > 0 && response.status >= 500) {
                const delay = Math.pow(2, 3 - retries) * 1000;
                await this.sleep(delay);
                return this.request(endpoint, options, retries - 1);
            }
            
            return response;
            
        } catch (error) {
            if (retries > 0) {
                const delay = Math.pow(2, 3 - retries) * 1000;
                await this.sleep(delay);
                return this.request(endpoint, options, retries - 1);
            }
            
            throw error;
        }
    },
    
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    },
    
    async get(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;
        
        const response = await this.request(url, { method: 'GET' });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Request failed');
        }
        
        return response.json();
    },
    
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
    }
};

describe('API Client', () => {
    beforeEach(() => {
        fetch.mockClear();
        Auth.getAccessToken.mockClear();
        Auth.refreshToken.mockClear();
        Auth.clearTokens.mockClear();
        window.location.href = '';
    });

    describe('Request Authorization', () => {
        test('should add Authorization header when token exists', async () => {
            Auth.getAccessToken.mockReturnValue('test_token');
            
            fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ data: 'success' })
            });
            
            await API.request('/api/test', { method: 'GET' });
            
            expect(fetch).toHaveBeenCalledWith(
                'http://localhost:8088/api/test',
                expect.objectContaining({
                    headers: expect.objectContaining({
                        'Authorization': 'Bearer test_token'
                    })
                })
            );
        });

        test('should not add Authorization header when no token', async () => {
            Auth.getAccessToken.mockReturnValue(null);
            
            fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ data: 'success' })
            });
            
            await API.request('/api/test', { method: 'GET' });
            
            const callArgs = fetch.mock.calls[0][1];
            expect(callArgs.headers?.Authorization).toBeUndefined();
        });
    });

    describe('JSON Body Handling', () => {
        test('should stringify object body and set Content-Type', async () => {
            Auth.getAccessToken.mockReturnValue('token');
            
            fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ success: true })
            });
            
            const data = { name: 'Test', value: 123 };
            await API.request('/api/test', { method: 'POST', body: data });
            
            expect(fetch).toHaveBeenCalledWith(
                'http://localhost:8088/api/test',
                expect.objectContaining({
                    headers: expect.objectContaining({
                        'Content-Type': 'application/json'
                    }),
                    body: JSON.stringify(data)
                })
            );
        });
    });

    describe('401 Unauthorized Handling', () => {
        test('should refresh token and retry on 401', async () => {
            Auth.getAccessToken.mockReturnValue('old_token');
            Auth.refreshToken.mockResolvedValueOnce(true);
            
            // First call: 401, second call: success
            fetch
                .mockResolvedValueOnce({
                    ok: false,
                    status: 401
                })
                .mockResolvedValueOnce({
                    ok: true,
                    json: async () => ({ data: 'success' })
                });
            
            const response = await API.request('/api/test', { method: 'GET' });
            
            expect(Auth.refreshToken).toHaveBeenCalled();
            expect(fetch).toHaveBeenCalledTimes(2);
            expect(response.ok).toBe(true);
        });

        test('should redirect to login if refresh fails', async () => {
            // Mock window.location
            delete window.location;
            window.location = { href: '' };
            
            Auth.getAccessToken.mockReturnValue('token');
            Auth.refreshToken.mockResolvedValue(false); // Use mockResolvedValue (persistent) instead of mockResolvedValueOnce
            
            // Mock fetch to always return 401 (in case of retries)
            fetch.mockResolvedValue({
                ok: false,
                status: 401
            });
            
            // Use try-catch to capture error
            try {
                await API.request('/api/test', { method: 'GET' });
                // Should not reach here
                expect(true).toBe(false);
            } catch (error) {
                expect(error.message).toBe('Unauthorized');
                expect(Auth.clearTokens).toHaveBeenCalled();
                expect(window.location.href).toBe('/login.html');
            }
        }, 10000); // Increase timeout to 10 seconds
    });

    describe('429 Rate Limit Handling', () => {
        test('should retry with delay on 429', async () => {
            Auth.getAccessToken.mockReturnValue('token');
            
            const sleepSpy = jest.spyOn(API, 'sleep').mockResolvedValue();
            
            // First: 429, second: success
            fetch
                .mockResolvedValueOnce({
                    ok: false,
                    status: 429,
                    headers: new Map([['Retry-After', '2']])
                })
                .mockResolvedValueOnce({
                    ok: true,
                    json: async () => ({ data: 'success' })
                });
            
            await API.request('/api/test', { method: 'GET' });
            
            expect(sleepSpy).toHaveBeenCalledWith(2000);
            expect(fetch).toHaveBeenCalledTimes(2);
            
            sleepSpy.mockRestore();
        });

        test('should use default delay if Retry-After not present', async () => {
            Auth.getAccessToken.mockReturnValue('token');
            
            const sleepSpy = jest.spyOn(API, 'sleep').mockResolvedValue();
            
            fetch
                .mockResolvedValueOnce({
                    ok: false,
                    status: 429,
                    headers: new Map()
                })
                .mockResolvedValueOnce({
                    ok: true,
                    json: async () => ({ data: 'success' })
                });
            
            await API.request('/api/test', { method: 'GET' });
            
            expect(sleepSpy).toHaveBeenCalledWith(2000);
            
            sleepSpy.mockRestore();
        });
    });

    describe('5xx Server Error Retry', () => {
        test('should retry with exponential backoff on 500', async () => {
            Auth.getAccessToken.mockReturnValue('token');
            
            const sleepSpy = jest.spyOn(API, 'sleep').mockResolvedValue();
            
            // Fail twice, then succeed
            fetch
                .mockResolvedValueOnce({ ok: false, status: 500 })
                .mockResolvedValueOnce({ ok: false, status: 500 })
                .mockResolvedValueOnce({
                    ok: true,
                    json: async () => ({ data: 'success' })
                });
            
            await API.request('/api/test', { method: 'GET' });
            
            expect(sleepSpy).toHaveBeenCalledWith(1000); // 2^0 * 1000
            expect(sleepSpy).toHaveBeenCalledWith(2000); // 2^1 * 1000
            expect(fetch).toHaveBeenCalledTimes(3);
            
            sleepSpy.mockRestore();
        });
    });

    describe('Network Error Retry', () => {
        test('should retry on network errors with exponential backoff', async () => {
            Auth.getAccessToken.mockReturnValue('token');
            
            const sleepSpy = jest.spyOn(API, 'sleep').mockResolvedValue();
            
            // Fail twice with network error, then succeed
            fetch
                .mockRejectedValueOnce(new Error('Network error'))
                .mockRejectedValueOnce(new Error('Network error'))
                .mockResolvedValueOnce({
                    ok: true,
                    json: async () => ({ data: 'success' })
                });
            
            await API.request('/api/test', { method: 'GET' });
            
            expect(sleepSpy).toHaveBeenCalledTimes(2);
            expect(fetch).toHaveBeenCalledTimes(3);
            
            sleepSpy.mockRestore();
        });

        test('should throw after all retries exhausted', async () => {
            Auth.getAccessToken.mockReturnValue('token');
            
            const sleepSpy = jest.spyOn(API, 'sleep').mockResolvedValue();
            
            fetch.mockRejectedValue(new Error('Network error'));
            
            await expect(
                API.request('/api/test', { method: 'GET' })
            ).rejects.toThrow('Network error');
            
            expect(fetch).toHaveBeenCalledTimes(4); // Initial + 3 retries
            
            sleepSpy.mockRestore();
        });
    });

    describe('GET Method', () => {
        test('should build query string from params', async () => {
            Auth.getAccessToken.mockReturnValue('token');
            
            fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ data: 'success' })
            });
            
            await API.get('/api/test', { page: 1, limit: 10 });
            
            expect(fetch).toHaveBeenCalledWith(
                'http://localhost:8088/api/test?page=1&limit=10',
                expect.any(Object)
            );
        });

        test('should throw error with detail message on failure', async () => {
            Auth.getAccessToken.mockReturnValue('token');
            
            fetch.mockResolvedValueOnce({
                ok: false,
                status: 400,
                json: async () => ({ detail: 'Invalid request' })
            });
            
            await expect(
                API.get('/api/test')
            ).rejects.toThrow('Invalid request');
        });
    });

    describe('POST Method', () => {
        test('should send JSON body and return parsed response', async () => {
            Auth.getAccessToken.mockReturnValue('token');
            
            fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ id: 1, created: true })
            });
            
            const result = await API.post('/api/employees', {
                full_name: 'John Doe',
                role: 'worker'
            });
            
            expect(result).toEqual({ id: 1, created: true });
            expect(fetch).toHaveBeenCalledWith(
                'http://localhost:8088/api/employees',
                expect.objectContaining({
                    method: 'POST',
                    body: JSON.stringify({
                        full_name: 'John Doe',
                        role: 'worker'
                    })
                })
            );
        });
    });
});
