export function memoryDiscardRedirectHref({
  classId,
  hasTimelineHint,
}: {
  classId: string;
  hasTimelineHint: boolean;
}): string | null {
  return hasTimelineHint ? `/classes/${classId}` : null;
}
