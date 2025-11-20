import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';

/**
 * useTableQueryState — Unified URL state persistence for table pages
 * 
 * Purpose:
 * - Sync table filters and pagination to URL query params
 * - Restore state from URL on page load (F5 refresh support)
 * - Human-readable URLs: /expenses?status=pending&category=transport&page=2
 * 
 * Usage:
 * ```tsx
 * const {
 *   page, setPage,
 *   filters, setFilter, clearFilters,
 *   syncToUrl
 * } = useTableQueryState({
 *   defaultPage: 1,
 *   filterKeys: ['status', 'category', 'date_from', 'date_to'],
 *   filterDefaults: { status: 'all', category: 'all' },
 * });
 * 
 * // Usage in component
 * <select value={filters.status} onChange={(e) => setFilter('status', e.target.value)}>
 *   <option value="all">All</option>
 *   <option value="pending">Pending</option>
 * </select>
 * ```
 * 
 * Features:
 * - Auto-sync to URL on state change
 * - Skip default values (e.g., page=1, status='all' not added to URL)
 * - Type-safe filter keys via generics
 * - Clear filters resets to defaults
 */

interface UseTableQueryStateOptions<T extends string = string> {
  /** Default page number (usually 1) */
  defaultPage?: number;
  
  /** Filter param keys (e.g., ['status', 'category', 'date_from']) */
  filterKeys: T[];
  
  /** Default values for filters (e.g., { status: 'all', category: 'all' }) */
  filterDefaults?: Partial<Record<T, string>>;
  
  /** Custom param names mapping (e.g., { type: 'kind' } for Inbox) */
  paramMapping?: Partial<Record<T, string>>;
}

interface UseTableQueryStateReturn<T extends string = string> {
  /** Current page number */
  page: number;
  
  /** Set page and sync to URL */
  setPage: (page: number) => void;
  
  /** Current filter values */
  filters: Record<T, string>;
  
  /** Set individual filter and sync to URL */
  setFilter: (key: T, value: string) => void;
  
  /** Clear all filters (reset to defaults) */
  clearFilters: () => void;
  
  /** Manually trigger URL sync (usually auto-synced) */
  syncToUrl: () => void;
}

export function useTableQueryState<T extends string = string>({
  defaultPage = 1,
  filterKeys,
  filterDefaults = {},
  paramMapping = {},
}: UseTableQueryStateOptions<T>): UseTableQueryStateReturn<T> {
  const [searchParams, setSearchParams] = useSearchParams();

  // Initialize page from URL
  const [page, setPageState] = useState(() => {
    const urlPage = searchParams.get('page');
    return urlPage ? Number(urlPage) : defaultPage;
  });

  // Initialize filters from URL
  const [filters, setFiltersState] = useState<Record<T, string>>(() => {
    const initialFilters: Record<string, string> = {};
    filterKeys.forEach((key) => {
      const paramName = paramMapping[key] || key;
      const urlValue = searchParams.get(paramName);
      const defaultValue = filterDefaults[key] || '';
      initialFilters[key] = urlValue || defaultValue;
    });
    return initialFilters as Record<T, string>;
  });

  // Sync state to URL whenever page or filters change
  useEffect(() => {
    const params: Record<string, string> = {};

    // Add page if not default
    if (page > defaultPage) {
      params.page = page.toString();
    }

    // Add filters if not default
    filterKeys.forEach((key) => {
      const value = filters[key];
      const defaultValue = filterDefaults[key] || '';
      const paramName = paramMapping[key] || key;

      // Only add to URL if value is not default and not empty
      if (value && value !== defaultValue) {
        params[paramName] = value;
      }
    });

    setSearchParams(params, { replace: true });
  }, [page, filters, defaultPage, filterKeys, filterDefaults, paramMapping, setSearchParams]);

  // Set page and reset to page 1 when filters change
  const setPage = (newPage: number) => {
    setPageState(newPage);
  };

  // Set individual filter (resets page to 1)
  const setFilter = (key: T, value: string) => {
    setFiltersState((prev) => ({ ...prev, [key]: value }));
    setPageState(1); // Reset to page 1 when filter changes
  };

  // Clear all filters
  const clearFilters = () => {
    const resetFilters: Record<string, string> = {};
    filterKeys.forEach((key) => {
      resetFilters[key] = filterDefaults[key] || '';
    });
    setFiltersState(resetFilters as Record<T, string>);
    setPageState(1);
  };

  // Manual sync (usually not needed, auto-synced via useEffect)
  const syncToUrl = () => {
    const params: Record<string, string> = {};
    if (page > defaultPage) params.page = page.toString();
    filterKeys.forEach((key) => {
      const value = filters[key];
      const defaultValue = filterDefaults[key] || '';
      const paramName = paramMapping[key] || key;
      if (value && value !== defaultValue) {
        params[paramName] = value;
      }
    });
    setSearchParams(params, { replace: true });
  };

  return {
    page,
    setPage,
    filters,
    setFilter,
    clearFilters,
    syncToUrl,
  };
}
