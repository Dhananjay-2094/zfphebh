import { useEffect, useState } from "react";

// Ignore results from requests that were superseded by newer inputs.
export function useApi(fn, deps) {
  const [state, set] = useState({ data: null, error: null, loading: true });

  useEffect(() => {
    let live = true;
    set((current) => ({ ...current, loading: true, error: null }));
    fn()
      .then((data) => live && set({ data, error: null, loading: false }))
      .catch((error) => live && set({ data: null, error, loading: false }));
    return () => { live = false; };
    // Callers pass the values that should trigger a request.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}

export function useDebounced(value, ms = 400) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);

  return debounced;
}
