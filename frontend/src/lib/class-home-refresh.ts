type RefreshStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export function classHomeTimelineRefreshKey(classId: string): string {
  return `kp:class-home:timeline-refresh:${classId}`;
}

export function markClassHomeTimelineRefresh(
  storage: RefreshStorage,
  classId: string,
): void {
  storage.setItem(classHomeTimelineRefreshKey(classId), "1");
}

export function consumeClassHomeTimelineRefresh(
  storage: RefreshStorage,
  classId: string,
): boolean {
  const key = classHomeTimelineRefreshKey(classId);
  if (storage.getItem(key) !== "1") return false;
  storage.removeItem(key);
  return true;
}
