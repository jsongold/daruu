/**
 * Debounce hooks for delaying function execution.
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';

/**
 * Debounce a value - returns a debounced version that only updates
 * after the specified delay has passed without new changes.
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

/**
 * Create a debounced callback function.
 * The function will only be called after the specified delay has passed
 * without any new calls.
 */
export function useDebouncedCallback<T extends (...args: unknown[]) => unknown>(
  callback: T,
  delay: number
): {
  debouncedFn: (...args: Parameters<T>) => void;
  cancel: () => void;
  flush: () => void;
  isPending: boolean;
} {
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const callbackRef = useRef(callback);
  const pendingArgsRef = useRef<Parameters<T> | null>(null);
  const [isPending, setIsPending] = useState(false);

  // Keep callback ref up to date
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  const cancel = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    pendingArgsRef.current = null;
    setIsPending(false);
  }, []);

  const flush = useCallback(() => {
    if (timeoutRef.current && pendingArgsRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
      const args = pendingArgsRef.current;
      pendingArgsRef.current = null;
      setIsPending(false);
      callbackRef.current(...args);
    }
  }, []);

  const debouncedFn = useCallback(
    (...args: Parameters<T>) => {
      // Clear existing timeout
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      // Store pending args
      pendingArgsRef.current = args;
      setIsPending(true);

      // Set new timeout
      timeoutRef.current = setTimeout(() => {
        timeoutRef.current = null;
        pendingArgsRef.current = null;
        setIsPending(false);
        callbackRef.current(...args);
      }, delay);
    },
    [delay]
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return { debouncedFn, cancel, flush, isPending };
}

/**
 * Create a debounced save function with built-in status tracking.
 * Useful for auto-save scenarios where you need to track save state per item.
 */
export function useDebouncedSave<TKey extends string | number, TValue>(
  saveFn: (key: TKey, value: TValue) => Promise<void>,
  delay: number = 500
): {
  save: (key: TKey, value: TValue) => void;
  cancel: (key: TKey) => void;
  cancelAll: () => void;
  savingKeys: Set<TKey>;
  pendingKeys: Set<TKey>;
  errorKeys: Map<TKey, string>;
  successKeys: Set<TKey>;
  clearSuccess: (key: TKey) => void;
  clearError: (key: TKey) => void;
} {
  const timeoutsRef = useRef<Map<TKey, ReturnType<typeof setTimeout>>>(new Map());
  const saveFnRef = useRef(saveFn);
  const [savingKeys, setSavingKeys] = useState<Set<TKey>>(new Set());
  const [pendingKeys, setPendingKeys] = useState<Set<TKey>>(new Set());
  const [errorKeys, setErrorKeys] = useState<Map<TKey, string>>(new Map());
  const [successKeys, setSuccessKeys] = useState<Set<TKey>>(new Set());

  // Keep save function ref up to date
  useEffect(() => {
    saveFnRef.current = saveFn;
  }, [saveFn]);

  const clearSuccess = useCallback((key: TKey) => {
    setSuccessKeys((prev) => {
      const next = new Set(prev);
      next.delete(key);
      return next;
    });
  }, []);

  const clearError = useCallback((key: TKey) => {
    setErrorKeys((prev) => {
      const next = new Map(prev);
      next.delete(key);
      return next;
    });
  }, []);

  const cancel = useCallback((key: TKey) => {
    const timeout = timeoutsRef.current.get(key);
    if (timeout) {
      clearTimeout(timeout);
      timeoutsRef.current.delete(key);
    }
    setPendingKeys((prev) => {
      const next = new Set(prev);
      next.delete(key);
      return next;
    });
  }, []);

  const cancelAll = useCallback(() => {
    timeoutsRef.current.forEach((timeout) => clearTimeout(timeout));
    timeoutsRef.current.clear();
    setPendingKeys(new Set());
  }, []);

  const save = useCallback(
    (key: TKey, value: TValue) => {
      // Clear existing timeout for this key
      const existingTimeout = timeoutsRef.current.get(key);
      if (existingTimeout) {
        clearTimeout(existingTimeout);
      }

      // Clear any previous error/success for this key
      setErrorKeys((prev) => {
        const next = new Map(prev);
        next.delete(key);
        return next;
      });
      setSuccessKeys((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });

      // Mark as pending
      setPendingKeys((prev) => {
        const next = new Set(prev);
        next.add(key);
        return next;
      });

      // Set new timeout
      const timeout = setTimeout(async () => {
        timeoutsRef.current.delete(key);

        // Move from pending to saving
        setPendingKeys((prev) => {
          const next = new Set(prev);
          next.delete(key);
          return next;
        });
        setSavingKeys((prev) => {
          const next = new Set(prev);
          next.add(key);
          return next;
        });

        try {
          await saveFnRef.current(key, value);

          // Mark as success
          setSavingKeys((prev) => {
            const next = new Set(prev);
            next.delete(key);
            return next;
          });
          setSuccessKeys((prev) => {
            const next = new Set(prev);
            next.add(key);
            return next;
          });

          // Auto-clear success after 2 seconds
          setTimeout(() => {
            setSuccessKeys((prev) => {
              const next = new Set(prev);
              next.delete(key);
              return next;
            });
          }, 2000);
        } catch (err) {
          // Mark as error
          setSavingKeys((prev) => {
            const next = new Set(prev);
            next.delete(key);
            return next;
          });
          setErrorKeys((prev) => {
            const next = new Map(prev);
            next.set(key, err instanceof Error ? err.message : 'Save failed');
            return next;
          });
        }
      }, delay);

      timeoutsRef.current.set(key, timeout);
    },
    [delay]
  );

  // Cleanup on unmount
  useEffect(() => {
    const timeouts = timeoutsRef.current;
    return () => {
      timeouts.forEach((timeout) => clearTimeout(timeout));
      timeouts.clear();
    };
  }, []);

  return useMemo(
    () => ({
      save,
      cancel,
      cancelAll,
      savingKeys,
      pendingKeys,
      errorKeys,
      successKeys,
      clearSuccess,
      clearError,
    }),
    [save, cancel, cancelAll, savingKeys, pendingKeys, errorKeys, successKeys, clearSuccess, clearError]
  );
}
