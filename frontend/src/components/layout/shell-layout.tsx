"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

type ShellLayoutValue = {
  /** Wider main for plan/memory dual-pane sessions. */
  wide: boolean;
  setWide: (wide: boolean) => void;
};

const ShellLayoutContext = createContext<ShellLayoutValue | null>(null);

export function ShellLayoutProvider({ children }: { children: ReactNode }) {
  const [wide, setWide] = useState(false);
  const value = useMemo(() => ({ wide, setWide }), [wide]);
  return (
    <ShellLayoutContext.Provider value={value}>
      {children}
    </ShellLayoutContext.Provider>
  );
}

function useShellLayout(): ShellLayoutValue {
  const ctx = useContext(ShellLayoutContext);
  if (!ctx) {
    return { wide: false, setWide: () => {} };
  }
  return ctx;
}

/** Opt the shared AppShell into a wider max width while this page is mounted. */
export function useWideShell(enabled = true): void {
  const { setWide } = useShellLayout();
  useEffect(() => {
    if (!enabled) return;
    setWide(true);
    return () => setWide(false);
  }, [enabled, setWide]);
}

export { useShellLayout };
