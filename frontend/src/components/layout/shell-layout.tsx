"use client";

import {
  createContext,
  useContext,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

type ShellLayoutValue = {
  /** Wider main for plan/memory dual-pane sessions. */
  wide: boolean;
  setWide: (wide: boolean) => void;
  /** Lock viewport height and tighten padding for dual-pane sessions. */
  flush: boolean;
  setFlush: (flush: boolean) => void;
};

const ShellLayoutContext = createContext<ShellLayoutValue | null>(null);

export function ShellLayoutProvider({ children }: { children: ReactNode }) {
  const [wide, setWide] = useState(false);
  const [flush, setFlush] = useState(false);
  const value = useMemo(
    () => ({ wide, setWide, flush, setFlush }),
    [wide, flush],
  );
  return (
    <ShellLayoutContext.Provider value={value}>
      {children}
    </ShellLayoutContext.Provider>
  );
}

function useShellLayout(): ShellLayoutValue {
  const ctx = useContext(ShellLayoutContext);
  if (!ctx) {
    return {
      wide: false,
      setWide: () => {},
      flush: false,
      setFlush: () => {},
    };
  }
  return ctx;
}

/**
 * Opt plan/memory into the immersive dual-pane shell: wider content, locked
 * viewport height, tighter padding. useLayoutEffect avoids a visible narrow flash.
 */
export function useArtifactSessionShell(enabled = true): void {
  const { setWide, setFlush } = useShellLayout();
  useLayoutEffect(() => {
    if (!enabled) return;
    setWide(true);
    setFlush(true);
    return () => {
      setWide(false);
      setFlush(false);
    };
  }, [enabled, setWide, setFlush]);
}

/** @deprecated Prefer useArtifactSessionShell for plan/memory. */
export function useWideShell(enabled = true): void {
  useArtifactSessionShell(enabled);
}

export { useShellLayout };
