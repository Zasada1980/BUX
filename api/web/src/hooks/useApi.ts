import { useState, useCallback } from 'react';
import { useToast } from '@/contexts/ToastContext';

/**
 * Generic hook for API calls with loading/error state and toast notifications
 * 
 * @example
 * const { data, loading, error, execute } = useApi(apiClient.getUsers);
 * 
 * useEffect(() => {
 *   execute(1, 20);
 * }, []);
 */
export function useApi<TData, TArgs extends any[]>(
  apiFunction: (...args: TArgs) => Promise<TData>,
  options: {
    showSuccessToast?: boolean;
    successMessage?: string;
    showErrorToast?: boolean;
  } = {}
) {
  const { showToast } = useToast();
  const [data, setData] = useState<TData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    showSuccessToast = false,
    successMessage = 'Operation completed successfully',
    showErrorToast = true,
  } = options;

  const execute = useCallback(
    async (...args: TArgs) => {
      setLoading(true);
      setError(null);

      try {
        const result = await apiFunction(...args);
        setData(result);
        
        if (showSuccessToast) {
          showToast(successMessage, 'success');
        }
        
        return result;
      } catch (err: any) {
        const errorMessage = err.message || 'An error occurred';
        setError(errorMessage);
        
        if (showErrorToast) {
          showToast(errorMessage, 'error');
        }
        
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [apiFunction, showSuccessToast, successMessage, showErrorToast, showToast]
  );

  return { data, loading, error, execute };
}
