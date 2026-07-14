import { Suspense } from "react";

import { ClassHomeClient } from "./class-home-client";

export default async function ClassHomePage({
  params,
  searchParams,
}: {
  params: Promise<{ classId: string }>;
  searchParams: Promise<{ highlight?: string }>;
}) {
  const { classId } = await params;
  const { highlight } = await searchParams;
  return (
    <Suspense fallback={<p className="p-6 text-muted-foreground">Loading class…</p>}>
      <ClassHomeClient classId={classId} highlightDate={highlight} />
    </Suspense>
  );
}
