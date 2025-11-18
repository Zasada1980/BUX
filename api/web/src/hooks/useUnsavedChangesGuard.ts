import { useEffect, useCallback } from 'react';
import { useBlocker, Location } from 'react-router-dom';

interface UseUnsavedChangesGuardOptions {
  when: boolean;
  message?: string;
  onNavigateAway?: () => void;
}

/**
 * Hook to guard against losing unsaved changes when navigating away
 * Handles both SPA navigation (React Router) and browser navigation (beforeunload)
 */
export function useUnsavedChangesGuard({
  when,
  message = 'У вас есть несохранённые изменения. Если уйти со страницы, они будут потеряны.',
  onNavigateAway,
}: UseUnsavedChangesGuardOptions) {
  // Guard against browser navigation (refresh, close tab, etc.)
  useEffect(() => {
    if (!when) return;

    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      // Modern browsers ignore custom message, but we still need to set returnValue
      e.preventDefault();
      e.returnValue = message;
      return message;
    };

    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [when, message]);

  // Guard against SPA navigation (React Router)
  // Note: useBlocker is a React Router v6.4+ API
  // For older versions, use custom prompt or different approach
  const blocker = useBlocker(
    useCallback(
      ({ currentLocation, nextLocation }: { currentLocation: Location; nextLocation: Location }) => {
        // Only block if we have unsaved changes and we're actually navigating away
        return when && currentLocation.pathname !== nextLocation.pathname;
      },
      [when]
    )
  );

  // Return blocker state for manual handling in component
  return {
    isBlocked: blocker.state === 'blocked',
    proceed: () => {
      if (onNavigateAway) {
        onNavigateAway();
      }
      blocker.proceed?.();
    },
    reset: () => blocker.reset?.(),
  };
}
