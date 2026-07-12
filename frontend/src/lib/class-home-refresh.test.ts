import { describe, expect, it } from "vitest";

import {
  classHomeTimelineRefreshKey,
  consumeClassHomeTimelineRefresh,
  markClassHomeTimelineRefresh,
} from "./class-home-refresh";

describe("class home refresh marker", () => {
  it("marks and consumes stale timeline state for one class", () => {
    const storage = new Map<string, string>();
    const adapter = {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      removeItem: (key: string) => storage.delete(key),
    };

    markClassHomeTimelineRefresh(adapter, "chemie_9b_2026_27");

    expect(storage.get(classHomeTimelineRefreshKey("chemie_9b_2026_27"))).toBe("1");
    expect(consumeClassHomeTimelineRefresh(adapter, "chemie_9b_2026_27")).toBe(true);
    expect(consumeClassHomeTimelineRefresh(adapter, "chemie_9b_2026_27")).toBe(false);
  });
});
